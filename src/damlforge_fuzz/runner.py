"""The fuzz loop: take inputs from the sequence, compile each one, and count what happened.

This module imports the compiler, so it loads forge. It owns the stop rule (a
count or a deadline), the skip rule, and how an outcome is counted. It prints
nothing. cli.py prints.
"""

from __future__ import annotations

import itertools
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from damlforge_fuzz.compiler import Crash, Ok, Outcome, Rejected, Seed, compile_and_sort
from damlforge_fuzz.mutate import Input, input_sequence


@dataclass(frozen=True, slots=True)
class Count:
    """Stop after inputs 1 to n. The same random seed gives the same inputs on every machine."""

    n: int


@dataclass(frozen=True, slots=True)
class Seconds:
    """Stop before the first input that would start after `s` seconds.

    How many inputs fit depends on the machine, so a timed run does not repeat.
    Its input count, passed as Count, repeats it.
    """

    s: float


Limit: TypeAlias = Count | Seconds


@dataclass(frozen=True, slots=True)
class Tried:
    """One input of a run and what happened to it.

    `outcome` is None exactly when `input.changed` is False: the changes left
    the seed text as it was, so the input was skipped and not compiled.
    """

    input: Input
    seed: Seed
    outcome: Outcome | None


def fuzz(seeds: Sequence[Seed], random_seed: int, limit: Limit) -> Iterator[Tried]:
    """Inputs 1, 2, ... of `random_seed` over `seeds`, each compiled as its seed's file.

    The inputs are input_sequence([seed.text for seed in seeds], random_seed),
    whatever the limit and whatever forge returns. Lazy: an input is made and
    compiled only when the caller asks for the next one, so the deadline is
    checked before a compile, never after, and stopping early (Ctrl-C, break)
    loses nothing already yielded.

    With no seeds, the first next() raises ValueError.
    """
    sequence = input_sequence([seed.text for seed in seeds], random_seed)
    match limit:
        case Count(n):
            inputs = itertools.islice(sequence, n)
        case Seconds(s):
            inputs = _until(time.monotonic() + s, sequence)
    for item in inputs:
        seed = seeds[item.seed]
        yield Tried(item, seed, compile_and_sort(item.text, seed) if item.changed else None)


def _until(deadline: float, sequence: Iterator[Input]) -> Iterator[Input]:
    while time.monotonic() < deadline:
        yield next(sequence)


@dataclass(slots=True)
class Totals:
    """The counts a run prints. inputs == ok + rejected + crash + skipped after every add()."""

    inputs: int = 0
    ok: int = 0
    rejected: int = 0
    crash: int = 0
    skipped: int = 0

    def add(self, tried: Tried) -> None:
        self.inputs += 1
        match tried.outcome:
            case None:
                self.skipped += 1
            case Ok():
                self.ok += 1
            case Rejected():
                self.rejected += 1
            case Crash():
                self.crash += 1
