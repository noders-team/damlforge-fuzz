"""Run each OK input as Python and its Daml with Daml Script, on the same data, and compare.

This module imports no forge. It reads the .vy text with Python's `ast`, and
it builds and runs the Daml with dpm, through damlc.py. It owns four decisions:

- what a calls file says, and how it is checked against its seed (load_calls);
- how a call runs in Python: which inputs and calls are not compared, and the
  stand-ins for forge's names (create, fetch, template classes);
- how a call runs in Daml: one test module per input, in batch projects of
  BATCH inputs, built with `dpm build` and run with `dpm test`;
- what the difference of an input is: the first call, in file order, whose
  Daml outcome is not Python's, and its kind (DifferenceKind).

The kind comes from the ok/failed lines of `dpm test`, never from a failure
message. A batch runs one script per call, which is ok exactly when Daml
gives Python's outcome. Only the inputs with a failed script run again, with
one script per question (does the call run, is the result equal, are the
contracts equal), and the first failed question names the kind. Measured on
100 inputs of two calls each: 10.8 s with one script per call, 21.6 s with
three. So the second run costs one small `dpm test` (about 4 s) per batch
with a difference, not two more scripts for every call.
"""

from __future__ import annotations

import __future__
import ast
import contextlib
import dataclasses
import io
import json
import re
import shutil
import sys
import tempfile
import warnings
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from itertools import groupby
from pathlib import Path
from types import CodeType
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, TypeAlias, TypeVar

import yaml

from damlforge_fuzz.damlc import (
    DamlcUnavailable,
    DamlError,
    DamlSource,
    _ANSI,
    _folder,
    _folder_errors,
    _in_folder,
    _run_dpm,
    _settings,
    _unavailable,
    build_daml,
    need_dpm,
)

if TYPE_CHECKING:
    from damlforge_fuzz.compiler import Ok, Seed

BATCH: Final = 100
"""Inputs per batch project. A batch of 100 inputs of the loop seeds takes
about 18 s, and a Ctrl-C loses at most the batch that is running."""

LINES: Final = 100_000
"""The Python lines one call may run. A deterministic limit, unlike a clock, so
a run skips the same calls on every machine. `while True: pass` stops in
about 0.1 s."""

DifferenceKind: TypeAlias = Literal["result", "contracts", "daml_fails", "daml_passes"]
"""How Daml differs from Python in one call:

- "result": both run, the results differ;
- "contracts": both run, the results are equal, the contracts made differ;
- "daml_fails": Python runs, Daml fails;
- "daml_passes": Python fails (an assert), Daml runs.
"""

K = TypeVar("K")


@dataclass(frozen=True, slots=True)
class _Scalar:
    name: Literal["Party", "Decimal", "int", "bool", "None"]

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class _List:
    item: _Type

    def __str__(self) -> str:
        return f"list[{self.item}]"


@dataclass(frozen=True, slots=True)
class _ContractId:
    template: str

    def __str__(self) -> str:
        return f"ContractId[{self.template}]"


_Type: TypeAlias = _Scalar | _List | _ContractId
"""A .vy type annotation that a calls file can give a value for."""


@dataclass(frozen=True, slots=True)
class NewContract:
    """A ContractId value of a calls file: a contract that the script creates before the call."""

    template: str
    fields: tuple[tuple[str, _Type, Any], ...]


@dataclass(frozen=True, slots=True)
class Call:
    """One call of a calls file, checked against its seed.

    Each value is typed by the seed's annotation: a str (a party name), a
    Decimal, an int, a bool, a list, or a NewContract.
    """

    number: int
    """Its position in the calls file, from 1."""
    template: str | None
    """The choice's template, or None for a function."""
    name: str
    """The function or the choice."""
    contract: tuple[tuple[str, _Type, Any], ...]
    """The fields of the contract that the choice runs on. Empty for a function."""
    params: tuple[tuple[str, _Type, Any], ...]
    """The arguments, in parameter order."""
    returns: _Type
    shape_keys: tuple[str, ...]
    """The definitions whose shape an input must keep for this call to be compared."""

    @property
    def label(self) -> str:
        """'Iou.GiveAll #1' or 'total_of #3'."""
        name = self.name if self.template is None else f"{self.template}.{self.name}"
        return f"{name} #{self.number}"


@dataclass(frozen=True)
class Calls:
    """A seed's calls file, checked against the seed. load_calls makes it."""

    path: Path
    calls: tuple[Call, ...]
    parties: tuple[str, ...]
    """Every party name in the file, in first-use order. Each script allocates them all."""
    templates: Mapping[str, tuple[tuple[str, _Type], ...]]
    """The seed's templates and their fields, in file order. A choice call
    compares the contracts it makes of each of them."""
    shapes: Mapping[str, str]
    """The seed's shape of each definition that a call needs (Call.shape_keys)."""


def calls_path(vy: Path) -> Path:
    """The calls file of a .vy file: contracts/loop_give/loop_give.calls.yaml."""
    return vy.with_name(f"{vy.stem}.calls.yaml")


def load_calls(seed: Seed) -> Calls | None:
    """The calls file next to seed.path, checked against the seed's text, or None if there is none.

    Raises OSError when the file cannot be read, and ValueError, which names
    the file and the call, when the file does not fit the seed: an unknown
    function, choice, field, or parameter, a value that does not fit its
    type, or a type that a calls file cannot give.
    """
    path = calls_path(seed.path)
    if not path.is_file():
        return None
    if seed.module_name == "Test":
        raise ValueError(f"{path}: a seed with calls cannot have the Daml module name Test")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: a calls file is a list of calls")
    try:
        tree = ast.parse(seed.text)
    except SyntaxError as error:
        raise ValueError(f"{path}: Python cannot parse the seed {seed.path}: {error}") from error
    loader = _Loader(path, tree)
    calls = tuple(loader.call(number, entry) for number, entry in enumerate(raw, 1))
    return Calls(
        path,
        calls,
        tuple(loader.parties),
        loader.templates(),
        {key: loader.shapes[key] for call in calls for key in call.shape_keys},
    )


@dataclass(frozen=True, slots=True)
class CompareInput:
    """One OK input to compare: its .vy text, forge's outcome, its seed, and the seed's calls."""

    text: str
    ok: Ok
    seed: Seed
    calls: Calls


@dataclass(frozen=True, slots=True)
class Difference:
    """The first call of an input whose Daml outcome is not Python's."""

    label: ClassVar[str] = "BAD_RUN"

    kind: DifferenceKind
    call: str
    """Call.label: 'Iou.GiveAll #1'."""
    python: str
    """Python's outcome: 'returns None, makes 1 contract: Iou(...)' or 'fails: positive'."""
    test: str
    """A Daml Script module `Test` that imports forge's module and shows the
    difference: `dpm test` with it fails the script of the call."""


@dataclass(frozen=True, slots=True)
class Skipped:
    """Python ran no call of the input, so nothing was compared."""

    reasons: tuple[str, ...]
    """Why, for the whole input or for each call."""


@dataclass(frozen=True, slots=True)
class Dropped:
    """damlc rejects forge's Daml or the input's test module, so the scripts cannot run."""

    error: DamlError


@dataclass(frozen=True, slots=True)
class Compared:
    """Daml ran the calls that Python ran."""

    difference: Difference | None
    skipped: tuple[str, ...]
    """Why each call that was not compared was skipped."""


InputResult: TypeAlias = Skipped | Dropped | Compared


def run_and_compare(
    inputs: Mapping[K, CompareInput],
    verdicts: Mapping[DamlSource, DamlError | None] | None = None,
) -> Iterator[tuple[K, InputResult]]:
    """Run each input's calls in Python and in Daml, and yield each key with its result.

    Python runs first, and the inputs it skips are yielded first. Then damlc
    builds forge's Daml of the rest, except the texts in `verdicts` (damlc's
    verdicts from an earlier build), and the inputs whose Daml it rejects are
    yielded as Dropped. The rest run in batches of BATCH, one after the
    other, and a batch's results are yielded when it ends. So a
    KeyboardInterrupt loses only the batch that is running.

    Raises DamlcUnavailable when dpm is missing or fails and names no module.
    """
    planned: list[tuple[K, CompareInput, _Plan]] = []
    for key, item in inputs.items():
        plan = _plan(item)
        if isinstance(plan, Skipped):
            yield key, plan
        else:
            planned.append((key, item, plan))
    if not planned:
        return
    sources = {
        key: DamlSource(item.ok.daml, item.ok.module_name, item.seed.daml_yaml)
        for key, item, _ in planned
    }
    known = dict(verdicts or {})
    todo = dict.fromkeys(s for s in sources.values() if s not in known)
    if todo:
        known.update(build_daml(todo))
    ready = []
    for key, item, plan in planned:
        error = known[sources[key]]
        if error is None:
            ready.append((key, item, plan))
        else:
            yield key, Dropped(error)
    if not ready:
        return
    dpm = need_dpm()
    ready.sort(key=lambda entry: _test_settings(entry[1].seed.daml_yaml))
    for settings, group in groupby(
        ready, key=lambda entry: _test_settings(entry[1].seed.daml_yaml)
    ):
        entries = list(group)
        for start in range(0, len(entries), BATCH):
            yield from _run_batch(dpm, settings, entries[start : start + BATCH])


def group_daml_yaml(daml_yaml: Path) -> str:
    """The daml.yaml of a run group folder: the seed's, with `source: daml` and daml-script."""
    config = yaml.safe_load(daml_yaml.read_text(encoding="utf-8"))
    return yaml.safe_dump(_with_script({**config, "source": "daml"}), sort_keys=False)


# ---------------------------------------------------------------- calls files


_PARTY: Final = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_INT64: Final = range(-(2**63), 2**63)


class _Loader:
    """Checks the calls of one calls file against the seed's syntax tree."""

    def __init__(self, path: Path, tree: ast.Module) -> None:
        self.path = path
        self.functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
        self.template_names = [
            name
            for name, node in self.classes.items()
            if any(_decorator_name(d) == "template" for d in node.decorator_list)
        ]
        self.shapes = _shapes(tree)
        self.parties: dict[str, None] = {}
        self.where = str(path)

    def templates(self) -> dict[str, tuple[tuple[str, _Type], ...]]:
        return {name: self.fields(self.classes[name]) for name in self.template_names}

    def fail(self, message: str) -> ValueError:
        return ValueError(f"{self.where}: {message}")

    def call(self, number: int, entry: object) -> Call:
        self.where = f"{self.path}, call {number}"
        if not isinstance(entry, dict):
            raise self.fail("a call is a mapping with `function` or `choice`")
        if "function" in entry:
            allowed, name = {"function", "args"}, entry["function"]
            self.where += f" ({name})"
            node, template, contract = self.function(name), None, ()
            params = node.args.args
        elif "choice" in entry:
            allowed, name = {"choice", "contract", "args"}, entry["choice"]
            self.where += f" ({name})"
            template, node = self.choice(name)
            contract = self.values(
                f"the fields of {template}",
                entry.get("contract"),
                self.fields(self.classes[template]),
            )
            params = node.args.args[1:]
        else:
            raise self.fail("a call needs `function` or `choice`")
        if set(entry) - allowed:
            raise self.fail(f"unknown key {sorted(set(entry) - allowed)[0]!r}")
        a = node.args
        if a.posonlyargs or a.vararg or a.kwonlyargs or a.kwarg or a.defaults:
            raise self.fail(f"{node.name} must take plain parameters only")
        types = tuple((p.arg, self.annotation(p.annotation, p.arg)) for p in params)
        args = self.values(f"the parameters of {node.name}", entry.get("args", {}), types)
        returns = self.annotation(node.returns, "the return value", returns=True)
        if template is None:
            used = {
                inner.template
                for outer in (*(t for _, t in types), returns)
                for inner in _walk(outer)
                if isinstance(inner, _ContractId)
            }
            keys = (f"def {node.name}", *(f"class {name}" for name in sorted(used)))
        else:
            keys = (f"def {template}.{node.name}", *(f"class {t}" for t in self.template_names))
        return Call(number, template, node.name, contract, args, returns, keys)

    def function(self, name: object) -> ast.FunctionDef:
        node = self.functions.get(name) if isinstance(name, str) else None
        if node is None:
            raise self.fail(f"the seed has no function {name!r}")
        if any(_decorator_name(d) == "ledger_effect" for d in node.decorator_list):
            raise self.fail(
                f"{name} is a @ledger_effect function, which Daml Script cannot call. "
                "Call a choice that calls it."
            )
        return node

    def choice(self, name: object) -> tuple[str, ast.FunctionDef]:
        template, _, method = name.partition(".") if isinstance(name, str) else ("", "", "")
        if template not in self.template_names:
            raise self.fail(f"the seed has no template {template!r}")
        for node in self.classes[template].body:
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == method
                and any(_decorator_name(d) == "choice" for d in node.decorator_list)
            ):
                return template, node
        raise self.fail(f"template {template} has no choice {method!r}")

    def fields(self, node: ast.ClassDef) -> tuple[tuple[str, _Type], ...]:
        return tuple(
            (f.target.id, self.annotation(f.annotation, f"field {f.target.id} of {node.name}"))
            for f in node.body
            if isinstance(f, ast.AnnAssign) and f.value is None and isinstance(f.target, ast.Name)
        )

    def annotation(self, node: ast.expr | None, what: str, returns: bool = False) -> _Type:
        """The _Type of an annotation of the seed."""
        match node:
            case ast.Name(id="Party" | "Decimal" | "int" | "bool" as name):
                return _Scalar(name)
            case ast.Constant(value=None) if returns:
                return _Scalar("None")
            case ast.Subscript(value=ast.Name(id="list"), slice=item):
                return _List(self.annotation(item, what))
            case ast.Subscript(value=ast.Name(id="ContractId"), slice=ast.Name(id=template)) if (
                template in self.template_names
            ):
                return _ContractId(template)
        shown = "no annotation" if node is None else f"type {ast.unparse(node)}"
        raise self.fail(f"{what} has {shown}, which a calls file cannot give")

    def values(
        self, what: str, raw: object, types: Sequence[tuple[str, _Type]]
    ) -> tuple[tuple[str, _Type, Any], ...]:
        if not isinstance(raw, dict) or set(raw) != {name for name, _ in types}:
            names = ", ".join(name for name, _ in types) or "none"
            raise self.fail(f"{what} are {names}, and the call gives {_shown(raw)}")
        return tuple((name, t, self.value(t, raw[name], name)) for name, t in types)

    def value(self, t: _Type, raw: object, name: str) -> Any:
        """The call's value for `name`, of type t, or ValueError."""
        match t:
            case _Scalar("Party") if isinstance(raw, str) and _PARTY.fullmatch(raw):
                self.parties[raw] = None
                return raw
            case _Scalar("Decimal") if isinstance(raw, str | int | float) and not isinstance(
                raw, bool
            ):
                number = _decimal(raw)
                if number is not None and _decimal_text(number) is not None:
                    return number
            case _Scalar("int") if type(raw) is int and raw in _INT64:
                return raw
            case _Scalar("bool") if type(raw) is bool:
                return raw
            case _List(item) if isinstance(raw, list):
                return [self.value(item, x, name) for x in raw]
            case _ContractId(template) if isinstance(raw, dict) and raw.keys() == {
                "create",
                "with",
            }:
                if raw["create"] == template:
                    fields = self.fields(self.classes[template])
                    return NewContract(
                        template, self.values(f"the fields of {template}", raw["with"], fields)
                    )
        raise self.fail(f"{_shown(raw)} is not a {t} for {name}")


def _decorator_name(node: ast.expr) -> str | None:
    """'choice' for @choice(...) and @choice, 'template' for @template."""
    target = node.func if isinstance(node, ast.Call) else node
    return target.id if isinstance(target, ast.Name) else None


def _walk(t: _Type) -> Iterator[_Type]:
    yield t
    if isinstance(t, _List):
        yield from _walk(t.item)


def _shown(raw: object) -> str:
    return "nothing" if raw is None else json.dumps(raw, default=str)


def _shapes(tree: ast.Module) -> dict[str, str]:
    """The shape of each definition: a function's or a method's parameters and
    return annotation, and a class's fields with their types. A later
    definition of a name wins, as in Python."""
    shapes = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            shapes[f"def {node.name}"] = ast.dump(node.args) + ast.dump(
                node.returns or ast.Constant(None)
            )
        elif isinstance(node, ast.ClassDef):
            fields = [f for f in node.body if isinstance(f, ast.AnnAssign) and f.value is None]
            shapes[f"class {node.name}"] = ast.dump(ast.Module(fields, []))
            for method in node.body:
                if isinstance(method, ast.FunctionDef):
                    shapes[f"def {node.name}.{method.name}"] = ast.dump(method.args) + ast.dump(
                        method.returns or ast.Constant(None)
                    )
    return shapes


# ------------------------------------------------------------------- Python


@dataclass(frozen=True, slots=True)
class _Runs:
    """Python ran the call. The Daml literals that Daml must give."""

    result: str
    """The result, with each contract ID replaced by `Some` and its contract."""
    made: tuple[tuple[str, tuple[str, ...]], ...]
    """For each template of the seed, the contracts that the call made."""
    text: str


@dataclass(frozen=True, slots=True)
class _Fails:
    """Python failed the call with an AssertionError."""

    message: str

    @property
    def text(self) -> str:
        return f"fails: {self.message}" if self.message else "fails"


@dataclass(frozen=True, slots=True)
class _Plan:
    """The calls of one input that Python ran, with their outcomes, and the reasons for the rest."""

    outcomes: tuple[tuple[Call, _Runs | _Fails], ...]
    skipped: tuple[str, ...]


class _Unfit(Exception):
    """A Python value that does not fit the type of the seed's annotation."""


class _TooLong(Exception):
    """The call ran more than LINES lines of Python."""


@dataclass(frozen=True, slots=True)
class _Ref:
    """A contract ID in Python: a key of the call's ledger."""

    n: int


class _AnyType:
    """ContractId and the like in Python: `ContractId[Iou]` gives the same object."""

    def __getitem__(self, key: object) -> _AnyType:
        return self


_RUNS_IN_FORGE: Final = (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Pass)


def _plan(item: CompareInput) -> _Plan | Skipped:
    """Run each call of `item` in Python, or say why the input or a call is not compared."""
    try:
        tree = ast.parse(item.text)
    except (SyntaxError, ValueError) as error:
        return Skipped((f"Python cannot parse the text: {error}",))
    unfit = _statement_forge_drops(tree)
    if unfit is not None:
        return Skipped((unfit,))
    shapes = _shapes(tree)
    try:
        code = _runnable(tree)
    except SyntaxError as error:
        return Skipped((f"Python cannot compile the text: {error}",))
    outcomes, skipped = [], []
    for call in item.calls.calls:
        if any(shapes.get(key) != item.calls.shapes[key] for key in call.shape_keys):
            skipped.append(f"{call.label}: a definition it needs differs from the seed's")
            continue
        outcome = _run_call(code, call, item.calls)
        if isinstance(outcome, str):
            skipped.append(f"{call.label}: {outcome}")
        elif isinstance(outcome, _Fails) and call.template is None:
            skipped.append(
                f"{call.label}: Python fails, and Daml Script cannot catch a function's error"
            )
        else:
            outcomes.append((call, outcome))
    if not outcomes:
        return Skipped(tuple(skipped))
    return _Plan(tuple(outcomes), tuple(skipped))


def _statement_forge_drops(tree: ast.Module) -> str | None:
    """Why the input is not compared, or None.

    Python runs every statement of the module and of a class body, but forge
    writes only definitions. A module-level `assert False` fails every call in
    Python, and forge drops it: 10 false alarms in the prototype before this rule.
    """
    for node in tree.body:
        if not (isinstance(node, _RUNS_IN_FORGE) or _is_docstring(node)):
            return f"line {node.lineno}: a module-level statement, which forge does not run"
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if not (
                    isinstance(member, ast.AnnAssign | ast.FunctionDef | ast.Pass)
                    or _is_docstring(member)
                ):
                    where = f"line {member.lineno}: a statement in class {node.name}"
                    return f"{where}, which forge does not run"
    return None


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


_AS_FORGE_WRITES: Final[dict[type[ast.cmpop], ast.cmpop]] = {
    ast.Is: ast.Eq(),
    ast.IsNot: ast.NotEq(),
}


def _runnable(tree: ast.Module) -> CodeType:
    """The module as Python: no forge import, no decorator, and in a class only
    its fields without a value and its methods. Annotations are not evaluated.

    `is` becomes `==` and `is not` becomes `!=`, as forge writes them. In
    Python, `o is stop` compares two str objects, not two parties: 2 false
    alarms in 5000 inputs before this rule.
    """
    body: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "forge":
            continue
        if isinstance(node, ast.Import) and any(
            a.name.split(".")[0] == "forge" for a in node.names
        ):
            continue
        if isinstance(node, ast.FunctionDef | ast.ClassDef):
            node.decorator_list = []
        if isinstance(node, ast.ClassDef):
            node.body = [
                m for m in node.body if not (isinstance(m, ast.AnnAssign) and m.value is not None)
            ]
            node.body = node.body or [ast.Pass()]
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    member.decorator_list = []
        body.append(node)
    tree.body = body
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            node.ops = [_AS_FORGE_WRITES.get(type(op), op) for op in node.ops]
    with _quiet():
        return compile(
            tree, "<vy>", "exec", flags=__future__.annotations.compiler_flag, dont_inherit=True
        )


def _run_call(code: CodeType, call: Call, calls: Calls) -> _Runs | _Fails | str:
    """Run one call in a fresh module with a fresh ledger. A str says why it is skipped."""
    ledger: dict[_Ref, object] = {}
    made: list[object] = []
    classes: dict[str, type] = {}

    def create(contract: object) -> _Ref:
        if type(contract) not in classes.values():
            raise TypeError(f"create({contract!r}) needs a contract")
        ref = _Ref(len(ledger))
        ledger[ref] = contract
        made.append(contract)
        return ref

    def fetch(ref: _Ref) -> object:
        return ledger[ref]

    def python(t: _Type, value: Any) -> Any:
        match t, value:
            case _List(item), list():
                return [python(item, x) for x in value]
            case _ContractId(), NewContract(template=template, fields=fields):
                ref = _Ref(len(ledger))
                ledger[ref] = classes[template](**{name: python(ft, v) for name, ft, v in fields})
                return ref
        return value

    namespace: dict[str, Any] = {
        "__name__": "vy",
        "Decimal": Decimal,
        "Party": str,
        "ContractId": _AnyType(),
        "create": create,
        "fetch": fetch,
    }
    try:
        with _quiet():
            # Only definitions run here (see _statement_forge_drops), so no line budget.
            exec(code, namespace)
            for name, value in list(namespace.items()):
                if isinstance(value, type) and value.__module__ == "vy":
                    # dataclass reads the class's module from sys.modules, and "vy" is not there.
                    value.__module__ = __name__
                    classes[name] = dataclasses.dataclass(value)
        with _quiet(), _line_budget(LINES):
            args = {name: python(t, v) for name, t, v in call.params}
            if call.template is None:
                result = namespace[call.name](**args)
            else:
                cls = classes[call.template]
                contract = cls(**{name: python(t, v) for name, t, v in call.contract})
                result = getattr(cls, call.name)(contract, **args)
    except AssertionError as error:
        return _Fails(str(error))
    except Exception as error:
        return f"{type(error).__name__}: {str(error).partition(chr(10))[0]}"
    try:
        return _runs(call, calls, result, made, ledger)
    except _Unfit as unfit:
        return f"Python's outcome does not fit the seed's types: {unfit}"


def _runs(
    call: Call, calls: Calls, result: Any, made: list[object], ledger: dict[_Ref, object]
) -> _Runs:
    """Python's outcome as the Daml literals that Daml must give. Raises _Unfit."""
    literal = _Literal(
        calls, lambda ref, template: f"Some {_record(calls, template, ledger.get(ref))}"
    )
    per_template = []
    for template in calls.templates:
        mine = [c for c in made if type(c).__name__ == template]
        per_template.append((template, tuple(_record(calls, template, c) for c in mine)))
    if sum(len(cs) for _, cs in per_template) != len(made):
        raise _Unfit("the call made a contract of a class that is not a template of the seed")
    text = f"returns {_vy(result, ledger)}"
    if call.template is not None:
        text += f", makes {_contracts_text(made, ledger)}"
    return _Runs(literal(call.returns, result), tuple(per_template), text)


def _contracts_text(made: list[object], ledger: dict[_Ref, object]) -> str:
    if not made:
        return "no contract"
    shown = ", ".join(_vy(c, ledger) for c in made)
    return f"1 contract: {shown}" if len(made) == 1 else f"{len(made)} contracts: {shown}"


def _vy(value: Any, ledger: dict[_Ref, object]) -> str:
    """A Python value as .vy code would write it: alice, 4.0, [1, 2], Iou(issuer=alice, ...)."""
    if isinstance(value, list):
        return "[" + ", ".join(_vy(x, ledger) for x in value) + "]"
    if isinstance(value, _Ref):
        return f"ContractId({_vy(ledger.get(value), ledger)})"
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = ", ".join(
            f"{f.name}={_vy(getattr(value, f.name), ledger)}" for f in dataclasses.fields(value)
        )
        return f"{type(value).__name__}({fields})"
    return str(value)


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """Hide what the code prints, such as a `print` that a change rule inserts, and its warnings."""
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore")
        yield


@contextlib.contextmanager
def _line_budget(lines: int) -> Iterator[None]:
    """Raise _TooLong in the traced code after `lines` line events. Works on every OS."""
    left = lines

    def trace(frame: object, event: str, arg: object) -> object:
        nonlocal left
        if event == "line":
            left -= 1
            if left < 0:
                raise _TooLong(f"the call ran more than {lines} lines of Python")
        return trace

    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        yield
    finally:
        sys.settrace(previous)


# ------------------------------------------------------------- Daml literals


def _decimal(raw: str | int | float | Decimal) -> Decimal | None:
    try:
        number = Decimal(str(raw))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _decimal_text(number: Decimal) -> str | None:
    """A Daml Decimal literal, '1.5' or '(-2.0)', or None when Daml's Decimal
    (10 decimal places, under 10**28) cannot hold the number exactly."""
    normal = number.normalize()
    if normal.as_tuple().exponent < -10 or abs(normal) >= 10**28:
        return None
    text = f"{normal:f}"
    text = text if "." in text else f"{text}.0"
    return f"({text})" if text.startswith("-") else text


def _record(calls: Calls, template: str, contract: object) -> str:
    """'(Iou with issuer = p_alice, owner = p_bob, amount = 1.0)'. Raises _Unfit."""
    if type(contract).__name__ != template or not dataclasses.is_dataclass(contract):
        raise _Unfit(f"{contract!r} is not a contract of {template}")
    literal = _Literal(calls, lambda ref, t: _no_contract_id(ref))
    fields = ", ".join(
        f"{name} = {literal(t, getattr(contract, name, None))}"
        for name, t in calls.templates[template]
    )
    return f"({template} with {fields})"


def _no_contract_id(ref: object) -> str:
    raise _Unfit("a contract field holds a contract ID")


class _Literal:
    """Writes a Python value of a _Type as a Daml literal. `contract_id` writes a contract ID."""

    def __init__(self, calls: Calls, contract_id: Any) -> None:
        self.parties = set(calls.parties)
        self.contract_id = contract_id

    def __call__(self, t: _Type, value: Any) -> str:
        match t:
            case _Scalar("Party") if type(value) is str and value in self.parties:
                return f"p_{value}"
            case _Scalar("Decimal") if isinstance(value, Decimal | int) and not isinstance(
                value, bool
            ):
                text = _decimal_text(Decimal(value))
                if text is not None:
                    return text
            case _Scalar("int") if type(value) is int and value in _INT64:
                return f"({value})" if value < 0 else str(value)
            case _Scalar("bool") if type(value) is bool:
                return str(value)
            case _Scalar("None") if value is None:
                return "()"
            case _List(item) if isinstance(value, list):
                return "[" + ", ".join(self(item, x) for x in value) + "]"
            case _ContractId(template) if isinstance(value, _Ref | NewContract):
                return self.contract_id(value, template)
        raise _Unfit(f"{value!r} is not a {t}")


# -------------------------------------------------------------- Daml Script


def _test_module(module: str, imported: str, calls: Calls, plan: _Plan, split: bool) -> str:
    """A Daml Script module with the scripts of `plan`'s calls.

    Without `split`, one script per call, `c<n>`, that is ok exactly when Daml
    gives Python's outcome. With `split`, one script per question:
    `c<n>_runs`, `c<n>_result`, and for a choice `c<n>_contracts`, or
    `c<n>_fails` when Python fails. DifferenceKind follows from which fail.
    """
    lines = [
        f"module {module} where",
        "",
        "import Daml.Script",
        "import DA.Assert",
        "import DA.List (sortOn)",
        f"import {imported}",
    ]
    for call, outcome in plan.outcomes:
        for suffix, body in _scripts(call, outcome, calls, split):
            name = f"c{call.number}{suffix}"
            lines += ["", f"{name} : Script ()", f"{name} = do", *body]
    return "\n".join(lines) + "\n"


_KIND: Final[dict[str, DifferenceKind]] = {
    "_runs": "daml_fails",
    "_result": "result",
    "_contracts": "contracts",
    "_fails": "daml_passes",
}
"""The split scripts of a call, in the order they are asked, and the kind that a failure names."""


def _questions(call: Call, outcome: _Runs | _Fails) -> list[str]:
    """The split scripts of a call: the keys of _KIND that it asks."""
    if isinstance(outcome, _Fails):
        return ["_fails"]
    return ["_runs", "_result"] if call.template is None else ["_runs", "_result", "_contracts"]


def _scripts(
    call: Call, outcome: _Runs | _Fails, calls: Calls, split: bool
) -> list[tuple[str, list[str]]]:
    """(suffix, body) of each script of the call: one script, or one per question when `split`."""
    setup, command = _setup(call, calls)
    if isinstance(outcome, _Fails):
        return [
            ("_fails" if split else "", [*setup, f"  submitMustFail (actAs parties) do {command}"])
        ]
    if call.template is None:
        run = [f"  let result = {command}"]
    else:
        run = [f"  result <- submit (actAs parties) do {command}"]
    observe = _observe(call.returns, "result")
    if observe is None:
        result = [f"  result === {outcome.result}"]
    else:
        result = [f"  observed <- {observe}", f"  observed === {outcome.result}"]
    contracts = []
    for template, made in outcome.made if call.template is not None else ():
        before = [f"cid{n}" for n, t in _created(call) if t == template]
        contracts += [
            f"  found <- query @{template} parties",
            f"  let made = [c | (cid, c) <- found, cid `notElem` [{', '.join(before)}]]"
            if before
            else "  let made = map snd found",
            f"  sortOn show made === sortOn show [{', '.join(made)}]",
        ]
    if not split:
        return [("", [*setup, *run, *result, *contracts])]
    checks = {"_runs": ["  pure ()"], "_result": result, "_contracts": contracts}
    return [(q, [*setup, *run, *checks[q]]) for q in _questions(call, outcome)]


def _created(call: Call) -> list[tuple[int, str]]:
    """(n, template) for each contract that the script creates before the call, as cid<n>:
    cid0 is the contract that a choice runs on, and cid1, cid2, ... are in the arguments."""
    news = [new for _, t, value in call.params for new in _new_contracts(t, value)]
    first = [] if call.template is None else [(0, call.template)]
    return first + [(n, new.template) for n, new in enumerate(news, 1)]


def _new_contracts(t: _Type, value: Any) -> Iterator[NewContract]:
    if isinstance(t, _List):
        for item in value:
            yield from _new_contracts(t.item, item)
    elif isinstance(t, _ContractId):
        yield value


def _setup(call: Call, calls: Calls) -> tuple[list[str], str]:
    """The script lines before the call, and the call itself as a command or an expression."""
    lines = [f'  p_{p} <- allocateParty "{p}"' for p in calls.parties]
    lines.append(f"  let parties = [{', '.join(f'p_{p}' for p in calls.parties)}]")
    names = iter(f"cid{n}" for n, _ in _created(call))
    creates: list[str] = []

    def create(new: NewContract, template: str) -> str:
        name = next(names)
        fields = ", ".join(f"{field} = {literal(t, v)}" for field, t, v in new.fields)
        creates.append(f"  {name} <- submit (actAs parties) do createCmd {template} with {fields}")
        return name

    literal = _Literal(calls, create)
    if call.template is not None:
        create(NewContract(call.template, call.contract), call.template)
    args = [(name, literal(t, v)) for name, t, v in call.params]
    if call.template is None:
        command = " ".join([call.name, *(f"({text})" if " " in text else text for _, text in args)])
    else:
        command = f"exerciseCmd cid0 {call.name}"
        if args:
            command += " with " + ", ".join(f"{name} = {text}" for name, text in args)
    return lines + creates, command


def _observe(t: _Type, var: str, depth: int = 1) -> str | None:
    """A Script expression that gives `var` with each contract ID replaced by its
    contract, `Some c`, or None when type t holds no contract ID."""
    match t:
        case _ContractId():
            return f"queryContractId parties {var}"
        case _List(item):
            inner = _observe(item, f"x{depth}", depth + 1)
            return None if inner is None else f"mapA (\\x{depth} -> {inner}) {var}"
    return None


# ------------------------------------------------------------------ batches


_SUMMARY: Final = re.compile(
    r"^daml/I(\d{5})/Test\.daml:(c\d+(?:_[a-z]+)?): (ok|failed)", re.MULTILINE
)


def _run_batch(
    dpm: str, settings: str, batch: list[tuple[K, CompareInput, _Plan]]
) -> list[tuple[K, InputResult]]:
    """One temporary project: `dpm build`, `dpm test`, and `dpm test` again with
    split scripts for the inputs whose script failed."""
    with tempfile.TemporaryDirectory(prefix="damlforge-fuzz-") as temp:
        project = Path(temp)
        config = {**json.loads(settings), "name": "damlforge-fuzz-compare", "source": "daml"}
        (project / "daml.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        for k, (_, item, plan) in enumerate(batch):
            folder = project / "daml" / _folder(k)
            folder.mkdir(parents=True)
            daml = _in_folder(k, item.ok.daml, item.ok.module_name)
            (folder / f"{item.ok.module_name}.daml").write_text(daml, encoding="utf-8")
            _write_test(folder, k, item, plan, split=False)
        returncode, output = _run_dpm(dpm, "build", project)
        dropped = _folder_errors(output)
        if returncode != 0 and not dropped:
            raise _unavailable("build", returncode, output)
        for k in dropped:
            shutil.rmtree(project / "daml" / _folder(k))
        left = {k: entry[2] for k, entry in enumerate(batch) if k not in dropped}
        failed = _test(
            dpm, project, {k: _script_names(plan, split=False) for k, plan in left.items()}
        )
        differ = {k for k, _ in failed}
        for k in left:
            if k in differ:
                _, item, plan = batch[k]
                _write_test(project / "daml" / _folder(k), k, item, plan, split=True)
            else:
                shutil.rmtree(project / "daml" / _folder(k))
        failed_split = _test(dpm, project, {k: _script_names(left[k], split=True) for k in differ})
    results: list[tuple[K, InputResult]] = []
    for k, (key, item, plan) in enumerate(batch):
        if k in dropped:
            results.append((key, Dropped(dropped[k])))
        else:
            difference = _difference(item, plan, {name for kk, name in failed_split if kk == k})
            results.append((key, Compared(difference, plan.skipped)))
    return results


def _script_names(plan: _Plan, split: bool) -> list[str]:
    """The names of the scripts that _test_module writes for `plan`."""
    return [
        f"c{call.number}{suffix}"
        for call, outcome in plan.outcomes
        for suffix in (_questions(call, outcome) if split else [""])
    ]


def _write_test(folder: Path, k: int, item: CompareInput, plan: _Plan, split: bool) -> None:
    prefix = _folder(k)
    text = _test_module(
        f"{prefix}.Test", f"{prefix}.{item.ok.module_name}", item.calls, plan, split
    )
    (folder / "Test.daml").write_text(text, encoding="utf-8")


def _test(dpm: str, project: Path, scripts: Mapping[int, list[str]]) -> set[tuple[int, str]]:
    """Run `dpm test` and return the (k, script) pairs that failed.

    Raises DamlcUnavailable when the summary lacks a script, because then dpm
    did not run the scripts.
    """
    if not scripts:
        return set()
    returncode, output = _run_dpm(dpm, "test", project)
    found = _SUMMARY.findall(_ANSI.sub("", output))
    lines = {(int(k), name): status for k, name, status in found}
    if any((k, name) not in lines for k, names in scripts.items() for name in names):
        raise _unavailable("test", returncode, output)
    return {pair for pair, status in lines.items() if status == "failed"}


def _difference(item: CompareInput, plan: _Plan, failed: set[str]) -> Difference | None:
    """The first call, in file order, with a failed split script, and its kind."""
    for call, outcome in plan.outcomes:
        for question in _questions(call, outcome):
            if f"c{call.number}{question}" in failed:
                test = _test_module("Test", item.ok.module_name, item.calls, plan, split=True)
                return Difference(_KIND[question], call.label, outcome.text, test)
    return None


def _test_settings(daml_yaml: Path) -> str:
    """The batch key: damlc's settings with daml-script, so a seed and a saved
    run group, whose daml.yaml already has daml-script, share a batch."""
    return json.dumps(_with_script(json.loads(_settings(daml_yaml))), sort_keys=True)


def _with_script(config: dict[str, Any]) -> dict[str, Any]:
    """`config` with daml-script in its dependencies, for the test modules."""
    dependencies = list(config.get("dependencies") or [])
    if "daml-script" not in dependencies:
        dependencies.append("daml-script")
    return {**config, "dependencies": dependencies}
