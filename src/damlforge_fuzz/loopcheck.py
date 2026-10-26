"""The loop check: four ways a loop in forge's Daml is wrong, read from the Daml and the .vy text.

This module imports no forge and no other damlforge_fuzz module, like damlc.py
and mutate.py. It owns two decisions:

- what each check L1 to L4 finds (LoopCheck, LOOP_CHECK_TEXT);
- how one .vy text and forge's Daml for it give findings (find_loop_bugs).

compile_and_sort calls find_loop_bugs for every OK outcome and keeps the result
in Ok.loop_bugs, so `check`, `run`, the seed check, and a later shrinker all read
one value. The check needs no damlc.

The Daml is read as forge writes it: one statement or binding per line, two
spaces per level, `do` at the end of the line that opens a do block. The .vy
text is read with Python's tokenize, the same tokenizer forge's pre-parser
runs, so every text that forge compiles to OK can be read here, including
forge syntax that Python's ast rejects (`struct`, `for x: T in xs:`).
"""

from __future__ import annotations

import enum
import io
import re
import tokenize
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from keyword import iskeyword
from typing import Final


class LoopCheck(enum.StrEnum):
    """One loop check. Members are in check order: a text's first check names its loop group."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    # The import checks, in importcheck.py.
    I1 = "I1"
    I2 = "I2"
    I3 = "I3"
    I4 = "I4"


LOOP_CHECK_TEXT: Final[dict[LoopCheck, str]] = {
    LoopCheck.L1: "forge writes `foldlA`, the fold for a loop with a ledger action, "
    "but does not import it from `DA.Action`. damlc rejects the Daml.",
    LoopCheck.L2: "forge writes the pure fold `foldl` for a loop whose body has a ledger "
    "action, such as `fetch` or `create`. A ledger action needs `foldlA` in an `Update`.",
    LoopCheck.L3: "A `return` in a loop of the .vy code has no early-return helper "
    "(`_damlforge_loopN`) in the Daml, so the return is lost: the loop goes on, "
    "or the function returns another value. damlc can build this Daml.",
    LoopCheck.L4: "A ledger action, in a loop or not, is used as a value: it is not bound "
    "with `<-` and is not a statement of a `do` block, so the code gets an `Update`, "
    "not its result.",
    LoopCheck.I1: "The Daml uses a qualified name, such as `Map.insert`, `M.Note`, or a type "
    "used as a value, `Party.amount`, but no import line binds its qualifier. "
    "A lower-case qualifier, such as `models.double`, counts only when the `.vy` text "
    "binds that name to a module, as `import models` does. damlc rejects the Daml.",
    LoopCheck.I2: "An import line of the Daml has an alias that is not a Daml module name, "
    "such as `import qualified Models as m`. damlc rejects the Daml.",
    LoopCheck.I3: "The Daml selects an upper-case name, such as an enum value or a choice, "
    "from an expression: `(M.Kind).CASH`. Daml has no such syntax, so damlc rejects the Daml.",
    LoopCheck.I4: "The .vy code imports a name from a sibling module or a stub, but the Daml "
    "has no import of that module, or its import does not list the name.",
}
"""What each check finds, in plain English, for report.md and the README."""


@dataclass(frozen=True, slots=True)
class LoopBug:
    """One check that failed on one Daml text: where in the Daml, and what was found."""

    check: LoopCheck
    daml_line: int
    """1-based line in forge's Daml: the use of the action or foldlA, or the
    first line of the definition that lost its return (L3)."""
    detail: str
    """One line that names the Daml line, such as "fetch at Daml line 22 in the pure foldl of line 20"."""

    @property
    def label(self) -> str:
        return "BAD_IMP" if self.check.startswith("I") else "BAD_LOOP"


def find_loop_bugs(vy: str, daml: str) -> tuple[LoopBug, ...]:
    """The loop checks that `daml`, forge's Daml for the .vy text `vy`, fails.

    At most one finding per check, the first one in the Daml, in check order
    (L1, L2, L3, L4). Empty when no check fails. Pure, deterministic, and total:
    it never raises for any two strings. When `vy` cannot be tokenized, L3 is
    not checked; forge tokenizes the same text, so that never happens for a
    text forge compiled.
    """
    code = _Daml.read(daml)
    ledger = code.ledger_names()
    found = (_l1(code), _l2(code, ledger), _l3(vy, code), _l4(code, ledger))
    return tuple(finding for finding in found if finding is not None)


_PRIMITIVES: Final = {
    "fetch": True,
    "create": True,
    "exercise": True,
    "archive": True,
    "getTime": False,
}
"""The Update actions forge writes for the .vy builtins, and whether each takes an
argument. Each local function whose type ends in `Update ...` is a ledger action
too (ledger_names)."""


def _l1(code: _Daml) -> LoopBug | None:
    use = next(code.uses("foldlA"), None)
    if use is None or code.imports_foldlA():
        return None
    return LoopBug(
        LoopCheck.L1, use.line + 1, f"foldlA at Daml line {use.line + 1} with no import DA.Action"
    )


def _l2(code: _Daml, ledger: dict[str, bool]) -> LoopBug | None:
    for fold in code.uses("foldl"):
        for token in code.fold_body(fold):
            if code.runs(token, ledger):
                return LoopBug(
                    LoopCheck.L2,
                    token.line + 1,
                    f"{token.text} at Daml line {token.line + 1} in the pure foldl of line {fold.line + 1}",
                )
    return None


def _l4(code: _Daml, ledger: dict[str, bool]) -> LoopBug | None:
    allowed = code.action_positions()
    for token in code.tokens:
        if token.index not in allowed and code.runs(token, ledger):
            return LoopBug(
                LoopCheck.L4,
                token.line + 1,
                f"{token.text} at Daml line {token.line + 1} is used as a value, not bound with <-",
            )
    return None


def _l3(vy: str, code: _Daml) -> LoopBug | None:
    for function in _vy_functions(vy):
        if not function.returning_loops:
            continue
        where = code.definition(function.owner, function.name)
        if where is None:
            # forge wrote no Daml for this function at all. That loses more
            # than a return, and it is not a loop translation.
            continue
        helpers = code.helpers_from(where)
        if len(helpers) < function.returning_loops:
            what = (
                f"function {function.name}"
                if function.owner is None
                else f"choice {_choice_name(function.name)}"
            )
            return LoopBug(
                LoopCheck.L3,
                where.start + 1,
                f"the return in a loop of {what} at Daml line {where.start + 1} is lost "
                f"({_count(function.returning_loops, 'loop')} with a return, "
                f"{_count(len(helpers), 'early-return helper')})",
            )
    return None


# The Daml side.

_TOKEN: Final = re.compile(
    r"""(?P<id>[A-Za-z_][\w']*)|(?P<str>"[^"]*")|(?P<num>\d[\w.]*)"""
    r"""|(?P<op>[!#$%&*+./<=>?@\\^|~:-]+)|(?P<punct>[()\[\],;{}`])"""
)
_SYMBOL: Final = frozenset("!#$%&*+./<=>?@\\^|~:-")
_HELPER: Final = re.compile(r"_damlforge_loop\d+")
_IMPORT: Final = re.compile(r"import\s+(qualified\s+)?([\w.]+)(.*)")
_CONSUMING: Final = ("nonconsuming", "preconsuming", "postconsuming")
_NOT_AN_ARGUMENT: Final = frozenset({"=", ":", ",", ")", "]", "}", "->"})
"""What follows a name that is passed on, not applied: `fetch : Party`, `[fetch]`, `owner = create,`."""


@dataclass(frozen=True, slots=True)
class _Token:
    text: str
    kind: str
    line: int
    """0-based line in the Daml."""
    col: int
    index: int
    """Position in _Daml.tokens."""


@dataclass(frozen=True, slots=True)
class _Lines:
    """Lines start to end - 1 of the Daml."""

    start: int
    end: int


@dataclass(slots=True)
class _Daml:
    """forge's Daml with strings blanked and comments removed, cut into tokens per line."""

    lines: list[str]
    """The lines with string text blanked and comments removed."""
    tokens: list[_Token]
    by_line: list[list[_Token]]
    indent: list[int | None]
    """Leading spaces of each line, None for a blank line."""
    items: dict[str, _Lines] = field(default_factory=dict)
    """Top-level items by key: a function or helper name, or "template T"."""
    in_type: set[int] = field(default_factory=set)
    """Indexes of the tokens inside a type: after `:` up to the end of its bracket,
    a `,` or `=` at its depth, or the end of the line."""

    @classmethod
    def read(cls, daml: str) -> _Daml:
        lines = [_blank(raw) for raw in daml.split("\n")]
        tokens: list[_Token] = []
        by_line: list[list[_Token]] = []
        indent: list[int | None] = []
        for number, line in enumerate(lines):
            here = []
            for match in _TOKEN.finditer(line):
                token = _Token(match.group(), match.lastgroup, number, match.start(), len(tokens))
                tokens.append(token)
                here.append(token)
            by_line.append(here)
            indent.append(len(line) - len(line.lstrip()) if here else None)
        code = cls(lines, tokens, by_line, indent)
        code.items = code._top_level_items()
        code.in_type = {t.index for line in by_line for t in _type_tokens(line)}
        return code

    def uses(self, name: str) -> Iterator[_Token]:
        return (t for t in self.tokens if t.text == name and self.is_value(t))

    def is_value(self, token: _Token) -> bool:
        """True when `token` names a value in an expression. False for a field or a
        qualified name (`x.fetch`, `M.fetch`), a binding or record label (`create = ...`),
        and a name inside a type (`ContractId create`, `(x : T)`)."""
        if token.index in self.in_type:
            return False
        after = self.tokens[token.index + 1] if token.index + 1 < len(self.tokens) else None
        if after is not None and after.line == token.line and after.text == "=":
            return False
        if token.index == 0:
            return True
        before = self.tokens[token.index - 1]
        return not (
            before.line == token.line
            and before.text.endswith(".")
            and before.col + len(before.text) == token.col
        )

    def runs(self, token: _Token, ledger: dict[str, bool]) -> bool:
        """True when `token` is a ledger action of `ledger` that the code runs.

        An action that takes an argument runs only when it is applied: something
        follows it on its line, and that is not one of _NOT_AN_ARGUMENT. In
        `observer [fetch]` and `owner = create,` the name is a field or a value
        named like the action. An action that takes no argument, such as
        getTime, runs at each use: `((getTime).terms).deadline`.
        """
        if token.text not in ledger or not self.is_value(token):
            return False
        if not ledger[token.text]:
            return True
        after = self.tokens[token.index + 1] if token.index + 1 < len(self.tokens) else None
        return after is not None and after.line == token.line and after.text not in _NOT_AN_ARGUMENT

    def fold_body(self, fold: _Token) -> Iterator[_Token]:
        """The tokens of the lambda of `fold`, not of its start value and its list.

        forge writes the fold name at the end of its line, the lambda head on
        the next line, the lambda body deeper, and then the start value and the
        list at the head's indent. For any other layout: the tokens after
        `fold` on its line and on every following deeper line.
        """
        rest = [t for t in self.by_line[fold.line] if t.col > fold.col]
        deeper = []
        for line in range(fold.line + 1, len(self.by_line)):
            if self.indent[line] is None:
                continue
            if self.indent[line] <= self.indent[fold.line]:
                break
            deeper.append(line)
        if rest or not deeper:
            yield from rest
            yield from (t for line in deeper for t in self.by_line[line])
            return
        head = deeper[0]
        yield from self.by_line[head]
        yield from (
            t
            for line in deeper[1:]
            if self.indent[line] > self.indent[head]
            for t in self.by_line[line]
        )

    def ledger_names(self) -> dict[str, bool]:
        """The primitives, and every name whose type signature here ends in `Update ...`,
        each with whether it takes an argument."""
        names = dict(_PRIMITIVES)
        for line in self.by_line:
            if len(line) > 2 and line[0].kind == "id" and line[1].text == ":":
                head, takes_argument = _result(line[2:])
                if head == "Update":
                    names[line[0].text] = takes_argument
        return names

    def imports_foldlA(self) -> bool:
        """True when an import line brings the bare name foldlA from DA.Action into scope."""
        for line in self.lines:
            match = _IMPORT.fullmatch(line.rstrip())
            if match is None or match.group(1) or match.group(2) != "DA.Action":
                continue
            rest = match.group(3)
            names = set(re.findall(r"[A-Za-z_][\w']*", rest))
            if rest.startswith("("):
                if "foldlA" in names:
                    return True
            elif rest.startswith("hiding"):
                if "foldlA" not in names:
                    return True
            elif "qualified" not in names:
                return True
        return False

    def action_positions(self) -> set[int]:
        """Indexes of the tokens where an Update action is run, not used as a value.

        These are the first token of each statement of a do block, the token
        after `<-`, and the token after `do` on the same line. A do block is
        the lines at the column of the first token after `do`, until a line
        with less indent. Also the definition heads: the first token of a
        type signature (`verify : ...`) and of an equation (`verify cids p = do`).
        """
        allowed: set[int] = set()
        columns: list[int] = []
        opening = False
        for number, line in enumerate(self.by_line):
            if not line:
                continue
            column = self.indent[number]
            while columns and column < columns[-1]:
                columns.pop()
            if opening:
                columns.append(column)
                opening = False
            if (columns and column == columns[-1]) or _defines(line):
                allowed.add(line[0].index)
            for k, token in enumerate(line):
                if token.text == "<-" and token.index + 1 < len(self.tokens):
                    allowed.add(token.index + 1)
                elif token.text == "do":
                    if k + 1 < len(line):
                        allowed.add(line[k + 1].index)
                        columns.append(line[k + 1].col)
                    else:
                        opening = True
        return allowed

    def definition(self, owner: str | None, name: str) -> _Lines | None:
        """The Daml lines of the .vy function `name`: a top-level function, or a
        choice of template `owner`. None when forge wrote no such definition."""
        if owner is None:
            return self.items.get(name)
        template = self.items.get(f"template {owner}")
        if template is None:
            return None
        head = ["choice", _choice_name(name), ":"]
        for number in range(template.start, template.end):
            texts = [t.text for t in self.by_line[number][:4]]
            if texts[:1] and texts[0] in _CONSUMING:
                texts = texts[1:]
            if texts[:3] == head:
                end = number + 1
                while end < template.end and (
                    self.indent[end] is None or self.indent[end] > self.indent[number]
                ):
                    end += 1
                return _Lines(number, end)
        return None

    def helpers_from(self, lines: _Lines) -> set[str]:
        """The early-return helpers `lines` calls, directly or through another helper."""
        found: set[str] = set()
        todo = [lines]
        while todo:
            part = todo.pop()
            for number in range(part.start, part.end):
                for token in self.by_line[number]:
                    if _HELPER.fullmatch(token.text) and token.text not in found:
                        found.add(token.text)
                        if (body := self.items.get(token.text)) is not None:
                            todo.append(body)
        return found

    def _top_level_items(self) -> dict[str, _Lines]:
        """Each top-level item: a column-0 line and the deeper lines below it.
        Equations of one name (`f : T`, `f x = ...`) are one item."""
        items: dict[str, _Lines] = {}
        key, start = None, 0
        for number, line in enumerate(self.by_line):
            if not line or self.indent[number] != 0:
                continue
            here = (
                f"template {line[1].text}"
                if line[0].text == "template" and len(line) > 1
                else line[0].text
            )
            if here != key:
                if key is not None:
                    items.setdefault(key, _Lines(start, number))
                key, start = here, number
        if key is not None:
            items.setdefault(key, _Lines(start, len(self.by_line)))
        return items


def _blank(line: str) -> str:
    """`line` with the text of each string literal blanked and a `--` comment removed.

    Columns do not move, so a token's column is its column in forge's Daml.
    """
    if '"' not in line and "--" not in line:
        return line
    out = []
    i, n = 0, len(line)
    while i < n:
        c = line[i]
        if c == '"':
            j = i + 1
            while j < n and line[j] != '"':
                j += 2 if line[j] == "\\" else 1
            if j >= n:
                out.append(" " * (n - i))
                break
            out.append('"' + " " * (j - i - 1) + '"')
            i = j + 1
            continue
        if line.startswith("--", i) and (i == 0 or line[i - 1] not in _SYMBOL):
            end = i
            while end < n and line[end] == "-":
                end += 1
            if end == n or line[end] not in _SYMBOL:
                break
        out.append(c)
        i += 1
    return "".join(out)


def _type_tokens(line: Sequence[_Token]) -> Iterator[_Token]:
    """The tokens of `line` that are part of a type: `[ContractId Iou]` in `cids : [ContractId Iou]`."""
    depth, type_depth = 0, None
    for token in line:
        if token.text in ("(", "[", "{"):
            depth += 1
        elif token.text in (")", "]", "}"):
            depth -= 1
            if type_depth is not None and depth < type_depth:
                type_depth = None
        elif type_depth is not None and depth == type_depth and token.text in (",", "="):
            type_depth = None
        elif token.text == ":" and type_depth is None:
            type_depth = depth
            continue
        if type_depth is not None:
            yield token


def _defines(line: Sequence[_Token]) -> bool:
    """True for a type signature (`f : T`) or an equation (`f x y = ...`): the first
    token names what the line defines, it does not use it."""
    if line[0].kind != "id":
        return False
    if len(line) > 1 and line[1].text == ":":
        return True
    depth = 0
    for token in line[1:]:
        if token.text in ("(", "[", "{"):
            depth += 1
        elif token.text in (")", "]", "}"):
            depth -= 1
        elif token.text == "=" and depth == 0:
            return True
    return False


def _result(type_tokens: Sequence[_Token]) -> tuple[str | None, bool]:
    """The first name of a type's result, and whether the type takes an argument:
    `[Party] -> Update (ContractId Iou)` -> ("Update", True), `Update Time` -> ("Update", False)."""
    depth, start = 0, 0
    for k, token in enumerate(type_tokens):
        if token.text in ("(", "["):
            depth += 1
        elif token.text in (")", "]"):
            depth -= 1
        elif token.text == "->" and depth == 0:
            start = k + 1
    return (type_tokens[start].text if start < len(type_tokens) else None), start > 0


def _choice_name(name: str) -> str:
    """forge's Daml name for the choice method `name`: the first letter in upper case."""
    return name[:1].upper() + name[1:]


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


# The .vy side.


@dataclass(slots=True)
class _Statement:
    """One logical line of the .vy text, and the indented block after it, if any."""

    tokens: list[tokenize.TokenInfo]
    body: list[_Statement]

    @property
    def keyword(self) -> str | None:
        """The first name of the line, after `async`: "def", "for", ... None for `@decorator`."""
        k = self._start
        return self.tokens[k].string if k < len(self.tokens) and self._is_name(k) else None

    @property
    def name(self) -> str | None:
        """The name after `def` or `class`."""
        k = self._start + 1
        return self.tokens[k].string if k < len(self.tokens) and self._is_name(k) else None

    @property
    def _start(self) -> int:
        return 1 if self.tokens and self.tokens[0].string == "async" else 0

    def _is_name(self, k: int) -> bool:
        return self.tokens[k].type == tokenize.NAME


@dataclass(frozen=True, slots=True)
class _VyFunction:
    owner: str | None
    """The class of a choice, or None for a function outside a class."""
    name: str
    returning_loops: int
    """`for` statements of this function with a `return` in their body, nested
    loops counted, functions and classes inside them not counted."""


def _vy_functions(vy: str) -> list[_VyFunction]:
    """Every function and every choice of the .vy text, in text order. Empty when the text
    cannot be tokenized."""
    if "\x00" in vy:
        # forge refuses a NUL byte before it tokenizes, and Python 3.12's
        # tokenize raises SystemError on one.
        return []
    try:
        raw = list(tokenize.tokenize(io.BytesIO(vy.encode("utf-8")).readline))
    except (tokenize.TokenError, SyntaxError, ValueError):
        return []
    skip = (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING)
    statements, _ = _block([t for t in raw if t.type not in skip], 0)
    found: list[_VyFunction] = []
    _visit(statements, None, False, found)
    return found


def _block(tokens: list[tokenize.TokenInfo], i: int) -> tuple[list[_Statement], int]:
    """The statements from tokens[i] to the DEDENT that ends the block, and the index after it."""
    statements = []
    while i < len(tokens) and tokens[i].type not in (tokenize.DEDENT, tokenize.ENDMARKER):
        j = i
        while tokens[j].type not in (tokenize.NEWLINE, tokenize.ENDMARKER):
            j += 1
        statement = _Statement(tokens[i:j], [])
        i = j + 1 if tokens[j].type == tokenize.NEWLINE else j
        if i < len(tokens) and tokens[i].type == tokenize.INDENT:
            statement.body, i = _block(tokens, i + 1)
            i += 1
        statements.append(statement)
    return statements, i


def _visit(
    statements: list[_Statement], owner: str | None, in_function: bool, found: list[_VyFunction]
) -> int:
    """Walk one block: add each function and each choice in it to `found`, in text
    order, and return how many `for` statements of the enclosing function in this
    block hold a `return`.

    In a function, the statements after a `return` in the same block never run,
    and forge writes no Daml for them. Outside a function forge ignores a
    `return` and writes what follows, so the walk goes on there.
    """
    loops = 0
    decorators: list[_Statement] = []
    for statement in statements:
        keyword = statement.keyword
        if keyword == "return" and in_function:
            break
        if keyword == "def" and statement.name is not None:
            position = len(found)
            returning = _visit(statement.body, None, True, found)
            if owner is None or _is_choice(decorators, statement):
                found.insert(position, _VyFunction(owner, statement.name, returning))
        elif keyword == "class" and statement.name is not None:
            _visit(statement.body, statement.name, False, found)
        else:
            if keyword == "for" and in_function and _returns(statement):
                loops += 1
            loops += _visit(statement.body, owner, in_function, found)
        decorators = [*decorators, statement] if statement.tokens[0].string == "@" else []
    return loops


def _is_choice(decorators: list[_Statement], definition: _Statement) -> bool:
    """True when forge writes the `def` in a class, under these decorator lines, as a choice.

    forge's lower_template reads a def in a class as the first that fits of:
    `__init__`, `@checked_fetch`, `@view` with a one-name return type, and
    `@choice(...)`. It drops any other def, such as an undecorated or a
    `@ledger_effect` method.
    """
    names = [d.tokens[1].string for d in decorators if len(d.tokens) > 1]
    texts = [t.string for t in definition.tokens]
    returns = texts.index("->") + 1 if "->" in texts else len(texts)
    one_name_return = (
        texts[returns + 1 : returns + 2] == [":"]
        and texts[returns].isidentifier()
        and not iskeyword(texts[returns])
    )
    if definition.name == "__init__" or "checked_fetch" in names:
        return False
    if "view" in names and one_name_return:
        return False
    return any([t.string for t in d.tokens[1:3]] == ["choice", "("] for d in decorators)


def _returns(statement: _Statement) -> bool:
    """True when the statement, or a statement in its body, is or holds a `return`.

    `return` is a keyword, so a NAME token "return" is a return statement. A
    `def` or `class` inside the body is a new scope: its returns do not count.
    """
    if any(t.type == tokenize.NAME and t.string == "return" for t in statement.tokens):
        return True
    return any(_returns(s) for s in statement.body if s.keyword not in ("def", "class"))
