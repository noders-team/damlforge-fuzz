"""The change rules, and the fixed sequence of inputs that a random seed defines.

This module never imports forge, so the rules and the whole sequence can be
tested on a machine without DamlForge.

It owns one decision that later units rely on: what input number N of random
seed S is. Input N depends only on the seed texts in order, S, and N. It does
not depend on timing, on compile results, or on earlier inputs, so `--count N`
and `--seconds` both take a prefix of one sequence, and a later unit can
rebuild "input 1554 of random seed 1" alone.
"""

from __future__ import annotations

import ast
import itertools
import keyword
import random
import re
import warnings
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Change:
    """One change, kept for people and reports. The input's text does not need it to rebuild.

    `rule` is one of RULE_NAMES. `line` is the 1-based line number in the text
    before this change.
    """

    rule: str
    line: int


@dataclass(frozen=True, slots=True)
class Input:
    """One changed copy of one seed text.

    `number` is 1-based: `--count N` takes inputs 1 to N.
    `seed` is the position of the seed in the texts passed to input_sequence.
    `changes` has 1 to 4 entries, in the order they were made. A change whose
    rule did not fit its line is listed too, and left the text as it was.
    `changed` is False when the text equals the seed text. Such an input is
    skipped, not compiled, but it keeps its number.
    """

    number: int
    seed: int
    text: str
    changes: tuple[Change, ...]
    changed: bool


def input_sequence(texts: Sequence[str], random_seed: int) -> Iterator[Input]:
    """Inputs 1, 2, 3, ... of `random_seed`, without end.

    `texts` are the seed texts, in the fixed order cli._vy_files gives. Lines
    that rule "donor_line" inserts come only from `texts`, so a run on
    contracts/iou changes only iou.vy, with lines from iou.vy.

    Raises ValueError when `texts` is empty. Pure: no I/O and no clock.
    """
    if not texts:
        raise ValueError("input_sequence needs at least one seed text")
    texts = tuple(texts)
    # A tuple, never a set: set order of str changes with PYTHONHASHSEED, and
    # the sequence must be the same in every process.
    donor_lines = tuple(
        line for text in texts for line in text.split("\n") if line.strip()
    )
    return (_make_input(texts, donor_lines, random_seed, n) for n in itertools.count(1))


_MAX_CHANGES: Final = 4


def _make_input(
    texts: tuple[str, ...], donor_lines: tuple[str, ...], random_seed: int, number: int
) -> Input:
    # Each input has its own generator. A str seed goes through SHA-512, so it
    # is the same in every process, and a rule that draws one more number
    # shifts only its own input. The draw order below is part of the sequence.
    rng = random.Random(f"{random_seed}:{number}")
    seed = rng.randrange(len(texts))
    lines = tuple(texts[seed].split("\n"))
    changes = []
    for _ in range(rng.randint(1, _MAX_CHANGES)):
        i = rng.randrange(len(lines))
        rule = rng.choice(_RULES)
        new = rule.apply(rng, i, _Context(donor_lines, lines))
        if new is not None:
            lines = tuple(new) or ("",)
        changes.append(Change(rule.name, i + 1))
    text = "\n".join(lines)
    return Input(number, seed, text, tuple(changes), text != texts[seed])


@dataclass(frozen=True, slots=True)
class _Context:
    """What a rule may draw from besides its own line.

    `lines` is the text being changed, before this change. No line holds "\\n".
    """

    donor_lines: tuple[str, ...]
    lines: tuple[str, ...]


# A rule gets the index of the line it starts at and returns every line of the
# new text. None means the rule does not fit there, such as "operator" on a
# line with no operator.
_Apply = Callable[[random.Random, int, _Context], "list[str] | None"]

# A line rule gets only its line and returns the lines that replace it: []
# deletes it, [x, line] inserts x above it, [new] edits it.
_LineChange = Callable[[random.Random, str, _Context], "list[str] | None"]


def _line_rule(change: _LineChange) -> _Apply:
    """A rule that changes only its own line."""

    def apply(rng: random.Random, i: int, ctx: _Context) -> list[str] | None:
        new = change(rng, ctx.lines[i], ctx)
        if new is None:
            return None
        return [*ctx.lines[:i], *new, *ctx.lines[i + 1 :]]

    return apply


@dataclass(frozen=True, slots=True)
class _Rule:
    name: str
    apply: _Apply


# The word pools, from the spike. Editing one changes some inputs of every random seed.
_OPERATORS: Final = (
    "+", "-", "*", "/", "//", "%", "**", "&", "|", "^", "<<", ">>",
    "==", "!=", "<", "<=", ">", ">=",
    " and ", " or ", " in ", " not in ", " is ", " is not ",
)  # fmt: skip
_LITERALS: Final = (
    "0", "1", "-1", "2", "9223372036854775807", "9223372036854775808",
    "-9223372036854775808", "0.0", "1.5", "1e400", '""', '"x"', "True",
    "False", "None", "[]", "()", "{}", "[1, 2]", "(1, 2)",
)  # fmt: skip
_TYPES: Final = (
    "int", "str", "bool", "Party", "Decimal", "Int", "float", "list[int]",
    "Optional[int]", "GenMap[Party, int]", "TextMap[str]", "tuple[int, str]",
    "set[int]", "ContractId[int]", "None",
)  # fmt: skip
_EXPRESSIONS: Final = (
    "(x if True else y)", "[x for x in xs]", "{k: v for k, v in m}",
    "lambda: 0", "not x", "~x", "x[0]", "x[1:2]", "x.y.z", "f(*args)",
    "f(**kw)", "(a := 1)", "len(x)", "range(0, 3)", "fetch(x)",
    "create(x)", "datetime.now()", "timedelta(days=1)", "date(2020, 13, 40)",
)  # fmt: skip
_STATEMENTS: Final = (
    "pass", "return", "return None", "assert False", "assert x, 'm'",
    "x = 1", "x += 1", "del x", "raise", "break", "continue",
    "for i in range(3):\n{ind}    pass", "if x:\n{ind}    pass",
    "while True:\n{ind}    pass", "global x", "import os",
    "from forge.models import *", "from . import models",
    "from .models import x", "import math as m",
    "from forge.models import Party as P", "from models import *",
    "import models",
)  # fmt: skip

_NAME: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER: Final = re.compile(r"\d+(?:\.\d+)?")
_OPERATOR: Final = re.compile(r"==|!=|<=|>=|//|\*\*|<<|>>|[-+*/%<>&|^]")
_TOKEN: Final = re.compile(f"{_NAME.pattern}|{_NUMBER.pattern}|{_OPERATOR.pattern}")
_INDENT: Final = re.compile(r"\s*")


def _delete_line(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    return []


def _copy_line(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    return [line, line]


def _donor_line(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    """Insert a line from any seed text passed, this one included, above `line`."""
    if not ctx.donor_lines:
        return None
    return [rng.choice(ctx.donor_lines), line]


def _insert_statement(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    """Insert a statement at `line`'s indent, above it.

    A two-line statement ("for ...:" and its "pass") becomes two lines, so a
    later change in the same input can pick either one.
    """
    indent = _INDENT.match(line).group(0)
    statement = indent + rng.choice(_STATEMENTS).format(ind=indent)
    return [*statement.split("\n"), line]


def _replace_token(
    pattern: re.Pattern[str], pick: Callable[[random.Random, _Context], str]
) -> _Apply:
    """A word rule: replace one random match of `pattern` in the line with `pick(...)`."""

    def change(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
        matches = list(pattern.finditer(line))
        if not matches:
            return None
        match = rng.choice(matches)
        return [line[: match.start()] + pick(rng, ctx) + line[match.end() :]]

    return _line_rule(change)


def _a_name_in_the_text(rng: random.Random, ctx: _Context) -> str:
    # In text order, never through a set. The line being changed has a name,
    # so the list is never empty.
    return rng.choice(_NAME.findall("\n".join(ctx.lines)))


# The loop rules. They make the code shapes that break forge's loops: a ledger
# action inside an expression, a `return` inside a loop. They read the text
# through _code, so a string or a comment is never taken for code.

# A string, or a comment. A string that its line does not close ends there.
_NOT_CODE: Final = re.compile(
    r"'''[\s\S]*?(?:'''|\Z)|\"\"\"[\s\S]*?(?:\"\"\"|\Z)"
    r"|'(?:\\.|[^'\\\n])*'?|\"(?:\\.|[^\"\\\n])*\"?|#[^\n]*"
)
_ASSIGNMENT: Final = re.compile(
    r" *(?P<name>[a-z_][A-Za-z0-9_]*) *(?::[^=]+)?=(?!=) *(?P<value>.+?) *"
)
_FOR: Final = re.compile(r" *for +(?P<target>[A-Za-z_]\w*)")
_BRANCH: Final = re.compile(r" *(?:if|elif|else)\b")
_RETURN: Final = re.compile(r" *return\b")


def _code(lines: Sequence[str]) -> list[str]:
    """`lines` with each string written as quote marks and each comment as spaces.

    A match in a code line is at the same place in the real line, and is
    never in a string or a comment.
    """

    def blank(match: re.Match[str]) -> str:
        text = match.group()
        return " " * len(text) if text.startswith("#") else re.sub(r"\S", '"', text)

    return _NOT_CODE.sub(blank, "\n".join(lines)).split("\n")


def _indent(line: str) -> int:
    return len(_INDENT.match(line).group(0))


def _assignment(code: str) -> re.Match[str] | None:
    """`name = value` or `name: T = value`, in a code line."""
    match = _ASSIGNMENT.fullmatch(code)
    if match is None or keyword.iskeyword(match["name"]):
        return None
    return match


def _uses(name: str, code: str) -> list[re.Match[str]]:
    # Not an attribute such as `self.name`, and not a string prefix such as f"".
    return list(re.finditer(rf'(?<![\w.]){name}(?![\w"])', code))


def _assigns(name: str, code: str) -> bool:
    return re.match(
        rf" *(?:{name} *(?::[^=]+)?(?:[-+*/%&|^@]|//|\*\*|<<|>>)?=(?!=)|for +{name}\b)", code
    ) is not None


def _as_operand(value: str) -> str:
    """`value`, in parentheses unless it is a name or a call, such as `fetch(c).amount`."""
    try:
        # A value such as "\d" would print a SyntaxWarning in the middle of a run.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            node = ast.parse(value, mode="eval").body
    except (SyntaxError, ValueError):
        return f"({value})"
    while isinstance(node, ast.Attribute):
        node = node.value
    return value if isinstance(node, ast.Name | ast.Call) else f"({value})"


def _inline_local(rng: random.Random, i: int, ctx: _Context) -> list[str] | None:
    """Put the value of a local name in place of one use in line i: `i.amount` -> `fetch(c).amount`.

    A text rule, not a line rule: it must skip its own line by position.
    """
    code = _code(ctx.lines)
    own = _assignment(code[i])
    candidates = []
    for k, other in enumerate(code):
        assignment = _assignment(other)
        if assignment is None or k == i:
            continue
        uses = [
            use
            for use in _uses(assignment["name"], code[i])
            if own is None or use.start() != own.start("name")
        ]
        if uses:
            value = ctx.lines[k][assignment.start("value") : assignment.end("value")]
            candidates.append((uses, value))
    if not candidates:
        return None
    uses, value = rng.choice(candidates)
    use = rng.choice(uses)
    line = ctx.lines[i]
    new = line[: use.start()] + _as_operand(value) + line[use.end() :]
    return [*ctx.lines[:i], new, *ctx.lines[i + 1 :]]


def _early_return(rng: random.Random, i: int, ctx: _Context) -> list[str] | None:
    """In a loop body, insert `if v == v:` and the `return` line that follows the loop.

    It walks out of `if` and `else` blocks to the nearest loop with a `return`
    after it, so a line in an inner loop can get the function's return.
    """
    code = _code(ctx.lines)
    if not code[i].strip():
        return None
    indent = _indent(code[i])
    for j in range(i - 1, -1, -1):
        if not code[j].strip() or _indent(code[j]) >= indent:
            continue
        indent = _indent(code[j])
        loop = _FOR.match(code[j])
        if loop is None:
            if _BRANCH.match(code[j]) is None:
                return None
            continue
        back = _return_after(code, j)
        if back is not None:
            pad = " " * _indent(ctx.lines[i])
            v = loop["target"]
            test = [f"{pad}if {v} == {v}:", f"{pad}    {ctx.lines[back].strip()}"]
            return [*ctx.lines[:i], *test, *ctx.lines[i:]]
    return None


def _return_after(code: list[str], j: int) -> int | None:
    """The `return` line after the loop at line j, at the loop's indent, in the same block."""
    indent = _indent(code[j])
    for k in range(j + 1, len(code)):
        if not code[k].strip():
            continue
        if _indent(code[k]) < indent:
            return None
        if _indent(code[k]) == indent and _RETURN.match(code[k]):
            return k
    return None


def _wrap_in_loop(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    """Put a simple statement in `for _k in range(0, 2):`."""
    code = _code([line])[0].strip()
    if not code or code.endswith(":") or code.startswith("@") or _indent(line) == 0:
        return None
    return [" " * _indent(line) + "for _k in range(0, 2):", "    " + line]


def _dedent_line(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    """Move a statement 4 spaces to the left: out of an `if` or a loop."""
    if not line.startswith(" " * 8) or not _code([line])[0].strip():
        return None
    return [line[4:]]


def _inline_var(rng: random.Random, i: int, ctx: _Context) -> list[str] | None:
    """On `v = E`, put E in place of every use of v below it in its block, and delete the line."""
    code = _code(ctx.lines)
    assignment = _assignment(code[i])
    if assignment is None:
        return None
    name = assignment["name"]
    value = _as_operand(ctx.lines[i][assignment.start("value") : assignment.end("value")])
    lines = list(ctx.lines)
    used = False
    for k in range(i + 1, len(code)):
        if code[k].strip() and _indent(code[k]) < _indent(code[i]):
            break
        if _assigns(name, code[k]):
            return None
        for use in reversed(_uses(name, code[k])):
            lines[k] = lines[k][: use.start()] + value + lines[k][use.end() :]
            used = True
    if not used:
        return None
    del lines[i]
    return lines


# The import rules. They change the import lines at column 0, which forge reads
# to load a sibling .vy file and to write the Daml import lines.
_FROM_IMPORT: Final = re.compile(r"from +(?P<module>\.*[\w.]*) +import +(?P<names>[\w ,*]+?) *")
_PLAIN_IMPORT: Final = re.compile(r"import +(?P<module>[\w.]+)(?: +as +(?P<alias>\w+))? *")
# None gives `import m` and uses `m.X`. "m" is a lower-case alias.
_ALIASES: Final = ("M", "m", "Lib", None)
_MODULE_EDITS: Final = (".{}", "..{}", "pkg.{}", "forge.{}", "{}s")


def _import_name(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    """In `from m import a, b`, delete one name, or add a name from any seed."""
    match = _FROM_IMPORT.fullmatch(line)
    if match is None:
        return None
    names = [name.strip() for name in match["names"].split(",")]
    if len(names) > 1 and rng.randrange(2):
        del names[rng.randrange(len(names))]
    else:
        words = _NAME.findall("\n".join(ctx.donor_lines))
        names.append(rng.choice([word for word in words if not keyword.iskeyword(word)]))
    return [f"from {match['module']} import {', '.join(names)}"]


def _import_module(rng: random.Random, line: str, ctx: _Context) -> list[str] | None:
    """Change the module of an import line: relative, in a package, or with a typo."""
    match = _FROM_IMPORT.fullmatch(line) or _PLAIN_IMPORT.fullmatch(line)
    if match is None:
        return None
    module = rng.choice(_MODULE_EDITS).format(match["module"].lstrip("."))
    return [line[: match.start("module")] + module + line[match.end("module") :]]


def _import_form(rng: random.Random, i: int, ctx: _Context) -> list[str] | None:
    """Switch `from m import a, b` and `import m as A`, and rewrite each use: `a` <-> `A.a`."""
    code = _code(ctx.lines)
    lines = list(ctx.lines)
    edits: dict[int, list[tuple[int, int, str]]] = {}
    if (match := _FROM_IMPORT.fullmatch(lines[i])) is not None:
        names = [name.strip() for name in match["names"].split(",")]
        if match["module"].startswith(".") or not all(name.isidentifier() for name in names):
            return None
        alias = rng.choice(_ALIASES)
        prefix = alias or match["module"]
        lines[i] = f"import {match['module']}" + (f" as {alias}" if alias else "")
        for k, line in enumerate(code):
            if k != i:
                for name in names:
                    for use in _uses(name, line):
                        edits.setdefault(k, []).append((use.start(), use.end(), f"{prefix}.{name}"))
    elif (match := _PLAIN_IMPORT.fullmatch(lines[i])) is not None:
        prefix = re.escape(match["alias"] or match["module"])
        qualified = re.compile(rf"(?<![\w.]){prefix}\.(?P<name>[A-Za-z_]\w*)")
        names = []
        for k, line in enumerate(code):
            if k != i:
                for use in qualified.finditer(line):
                    names += [use["name"]] if use["name"] not in names else []
                    edits.setdefault(k, []).append((use.start(), use.end(), use["name"]))
        if not names:
            return None
        lines[i] = f"from {match['module']} import {', '.join(names)}"
    else:
        return None
    for k, spans in edits.items():
        for start, end, new in sorted(spans, reverse=True):
            lines[k] = lines[k][:start] + new + lines[k][end:]
    return lines


# The one list of rules, each equally likely. rng.choice picks by position, so
# any edit here changes some inputs of every random seed. Add a new rule at the
# end: in a test, a rule added last kept 1608 of the first 2000 inputs the same,
# and the same rule added first kept 86. README.md lists the rules, and a test
# checks that the two lists match.
_RULES: Final[tuple[_Rule, ...]] = (
    _Rule("delete_line", _line_rule(_delete_line)),
    _Rule("copy_line", _line_rule(_copy_line)),
    _Rule("donor_line", _line_rule(_donor_line)),
    _Rule("insert_statement", _line_rule(_insert_statement)),
    _Rule("literal", _replace_token(_TOKEN, lambda rng, ctx: rng.choice(_LITERALS))),
    _Rule("operator", _replace_token(_OPERATOR, lambda rng, ctx: rng.choice(_OPERATORS))),
    _Rule("type", _replace_token(_NAME, lambda rng, ctx: rng.choice(_TYPES))),
    _Rule("expression", _replace_token(_NAME, lambda rng, ctx: rng.choice(_EXPRESSIONS))),
    _Rule("name", _replace_token(_NAME, _a_name_in_the_text)),
    _Rule("delete_word", _replace_token(_TOKEN, lambda rng, ctx: "")),
    _Rule("inline_local", _inline_local),
    _Rule("early_return", _early_return),
    _Rule("wrap_in_loop", _line_rule(_wrap_in_loop)),
    _Rule("dedent_line", _line_rule(_dedent_line)),
    _Rule("inline_var", _inline_var),
    _Rule("import_name", _line_rule(_import_name)),
    _Rule("import_module", _line_rule(_import_module)),
    _Rule("import_form", _import_form),
)

RULE_NAMES: Final = tuple(rule.name for rule in _RULES)
