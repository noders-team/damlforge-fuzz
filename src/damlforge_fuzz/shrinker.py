# Copyright 2026 Noders Team
# Author: Ruslan Glaznyov <ruslan.glaznyov@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shrink an input: delete lines while it stays in the same group.

This module imports the compiler, so it loads forge. It owns three decisions:

- which deletions the shrinker tries, and in what order (see shrink());
- what keeps a text in its group: same_crash() for a crash group, same_loop()
  for a loop group;
- where a shrunk file goes: shrunk_path(). Report.write and
  `damlforge-fuzz shrink FILE` both use it. A shrunk file sits in a `shrunk/`
  folder next to its full input, under the same file name. The same name
  keeps the Daml module name (escrow.vy -> Escrow), and Seed.load walks up
  from shrunk/ to the full input's daml.yaml, so `damlforge-fuzz check`
  compiles the shrunk file with the settings the shrinker used.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import PurePath
from typing import TypeAlias, TypeVar

from damlforge_fuzz.compiler import Crash, CrashKey, Ok, Outcome, Seed, compile_and_sort
from damlforge_fuzz.damlc import DamlcVerdict, build_daml
from damlforge_fuzz.loopcheck import LoopCheck

P = TypeVar("P", bound=PurePath)

Keep: TypeAlias = Callable[[Outcome], bool]
"""True when a candidate's outcome is still in the group that is being shrunk."""


def shrink(text: str, seed: Seed, keep: Keep) -> str:
    """The shortest text found by deleting whole lines of `text` whose outcome `keep` accepts.

    Each candidate compiles as compile_and_sort(candidate, seed): the same file
    name, daml.yaml settings, and folder as the run that found the input.

    Contract, for any text, seed, and keep:

    - The result's lines are a subsequence of `text`'s lines, each kept byte
      for byte with its line ending. No line is edited.
    - keep(compile_and_sort(result, seed)) is true, or the result is `text`
      itself: no deletion passed `keep`, or `text` never did. A `keep` that
      `text` does not pass gives `text` back, not an exception.
    - Never empty when `text` is not empty.
    - Deterministic and silent when `keep` is, because compile_and_sort is.
      No file I/O, except the dpm builds of a same_loop() with a damlc verdict.
    - Idempotent when `keep` is deterministic: the last round below deleted
      nothing, and a second call starts with that same round.
    - Raises only what compile_and_sort and `keep` raise, such as
      KeyboardInterrupt and DamlcUnavailable.

    Algorithm. Repeat rounds until a round deletes nothing. A deletion is kept
    when lines remain and `keep` accepts their outcome. Each round:

    1. Coarse: aligned blocks of n/2, n/4, ..., 2 lines (n is the current line
       count), one sweep per size, from the last block to the first.
    2. Fine: from the last line to the first, try three deletions and keep the
       first that works: the line with every following line indented deeper
       (blank lines included), the line alone, the line and the next line.

    The fine pass follows Python's indentation, so a whole `def` with its body
    goes in one step even when no 1- or 2-line window can remove it. The coarse
    pass makes long inputs cheap: a 1242-line input shrank in 44 compiles.
    Every round but the last deletes a line, so the compile count is bounded
    by the input's length. There is no compile budget and no cache of
    compiles: on 11 real groups, every candidate text was new, and the most
    compiles one group took was 102 (0.12 s).
    """
    lines = text.splitlines(keepends=True)
    while True:
        before = len(lines)
        lines = _fine(_coarse(lines, seed, keep), seed, keep)
        if len(lines) == before:
            return "".join(lines)


def same_crash(key: CrashKey) -> Keep:
    """Keeps a Crash with key `key`: the crash group of `key`."""
    return lambda outcome: isinstance(outcome, Crash) and outcome.key == key


def same_loop(check: LoopCheck, damlc: DamlcVerdict, seed: Seed) -> Keep:
    """Keeps an Ok whose first loop check (Ok.loop_key) is `check`: a loop group.

    With `damlc` "builds" or "rejects", it also keeps damlc's verdict on the
    Ok's Daml. Each Daml text gets one `dpm build` (about 0.7 s) with
    seed.daml_yaml, so the seed needs a daml.yaml. The returned function keeps
    each verdict by Daml text. With `damlc` None, it builds nothing.

    Raises DamlcUnavailable as build_daml does.
    """
    verdicts: dict[str, DamlcVerdict] = {}

    def keep(outcome: Outcome) -> bool:
        if not isinstance(outcome, Ok) or outcome.loop_key != check:
            return False
        if damlc is None:
            return True
        if outcome.daml not in verdicts:
            source = seed.daml_source(outcome.daml, outcome.module_name)
            [(_, error)] = build_daml([source])
            verdicts[outcome.daml] = "builds" if error is None else "rejects"
        return verdicts[outcome.daml] == damlc

    return keep


def shrunk_path(path: P) -> P:
    """Where the shrunk copy of `path` goes: groups/g02/escrow.vy -> groups/g02/shrunk/escrow.vy.

    Works on Path (the CLI) and PurePosixPath (report.json's `/` paths) alike.
    """
    return path.parent / "shrunk" / path.name


def _coarse(lines: list[str], seed: Seed, keep: Keep) -> list[str]:
    size = len(lines) // 2
    while size >= 2:
        end = len(lines)
        while end > 0:
            start = max(0, end - size)
            trial = lines[:start] + lines[end:]
            if _keeps(trial, seed, keep):
                lines = trial
            end = start
        size //= 2
    return lines


def _fine(lines: list[str], seed: Seed, keep: Keep) -> list[str]:
    i = len(lines) - 1
    while i >= 0:
        for end in dict.fromkeys((_body_end(lines, i), i + 1, i + 2)):
            if end > len(lines):
                continue
            trial = lines[:i] + lines[end:]
            if _keeps(trial, seed, keep):
                lines = trial
                break
        i = min(i, len(lines)) - 1
    return lines


def _body_end(lines: list[str], i: int) -> int:
    """The index after line i's indented body: the following lines that are blank or deeper."""
    indent = _indent(lines[i])
    end = i + 1
    while end < len(lines) and (not lines[end].strip() or _indent(lines[end]) > indent):
        end += 1
    return end


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _keeps(lines: list[str], seed: Seed, keep: Keep) -> bool:
    return bool(lines) and keep(compile_and_sort("".join(lines), seed))
