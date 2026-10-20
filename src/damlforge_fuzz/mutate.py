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

import itertools
import random
import re
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
    "from forge.models import *",
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
)

RULE_NAMES: Final = tuple(rule.name for rule in _RULES)
