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

"""Bugs that a test plants in forge's own Daml, so that it does not wait for forge to make one.

A test of what the fuzzer does with a loop bug or a difference (BAD_LOOP and
BAD_RUN lines, exit codes, groups, report.md, damlc verdicts, shrinking) needs
Daml that is wrong. Each DamlForge release fixes some of forge's own bugs, so a
test that waits for forge to write wrong Daml fails, or checks nothing, on a
later release. plant() wraps forge's generate_daml: it calls the real function
and then edits the Daml that forge wrote. The bug is there on every forge
version, and the test knows which bug it is.

The saved pairs in tests/loops/ test the loop check itself on Daml that forge
really wrote.
"""

import re
import zlib
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

import damlforge_fuzz.compiler
from damlforge_fuzz import Seed, compile_and_sort


def plant(
    patch: pytest.MonkeyPatch, edit: Callable[[str], str | None], spare: Iterable[Path] = ()
) -> None:
    """Make compile_and_sort see edit(daml) wherever forge writes `daml`.

    When edit returns None, forge crashes in emit instead: generate_daml runs
    again with no IR, so the exception comes from forge's own code. The Daml
    of each .vy file in `spare` stays as forge writes it. A run spares its
    seeds, so its seed checks pass and only the inputs carry the bug.
    """
    spared = {compile_and_sort(seed.text, seed).daml for seed in map(Seed.load, spare)}
    real = damlforge_fuzz.compiler.generate_daml

    def planted(ir, **kwargs):
        daml, source_map = real(ir, **kwargs)
        if daml in spared:
            return daml, source_map
        daml = edit(daml)
        return real(None, **kwargs) if daml is None else (daml, source_map)

    patch.setattr(damlforge_fuzz.compiler, "generate_daml", planted)


def no_foldla_import(daml: str) -> str:
    """L1, the shape of b17: the Daml without its `import DA.Action` line. damlc rejects it."""
    return re.sub(r"^import DA\.Action\b.*\n", "", daml, flags=re.MULTILINE)


def hidden_loop_helpers(daml: str) -> str:
    """L3 on each loop with a return: the early-return helpers get another name. damlc builds it."""
    return daml.replace("_damlforge_loop", "_planted_loop")


def lost_inner_return(daml: str) -> str:
    """L3 on a loop with a return in a loop, the shape of b22: the second helper gets another name.

    A text with one such loop has one helper, and keeps it. damlc builds it.
    """
    return daml.replace("_damlforge_loop2", "_planted_loop2")


def unit_for_no_return(daml: str) -> str:
    """Each `error "..."` is `()`. damlc rejects it in a function with a result.

    forge writes such an `error` where a function ends with no return, and
    DamlForge v0.0.11 wrote `()` there.
    """
    return re.sub(r'\berror "[^"]*"', "()", daml)


def loop_bugs(daml: str) -> str:
    """L1 where the Daml has foldlA, and L3 where it has an early-return helper."""
    return hidden_loop_helpers(no_foldla_import(daml))


def crash_or_loop_bugs(daml: str) -> str | None:
    """A forge crash for one Daml text in four, by a checksum, and loop_bugs for the rest.

    So the inputs of one seed give a crash group and loop groups.
    """
    return None if zlib.crc32(daml.encode()) % 4 == 0 else loop_bugs(daml)


def bad_daml(daml: str) -> str:
    """Daml that damlc rejects: a definition of the wrong type at the end."""
    return daml + '\nplanted : Int\nplanted = "planted"\n'


def name_not_in_scope(daml: str) -> str:
    """Daml that damlc rejects with another error than bad_daml: a name that no module defines."""
    return daml + "\nplanted : Int\nplanted = notInScope\n"


def import_without_its_last_name(daml: str) -> str:
    """I4: an import line with a list of names loses the last one. damlc rejects a use of it."""
    return re.sub(r"^(import [\w.]+ \(.*), [\w']+\)$", r"\1)", daml, flags=re.MULTILINE)


def swapped_equality(daml: str) -> str:
    """Each `==` is `/=`, and each `/=` is `==`. damlc builds it, and it runs differently."""
    return re.sub(r"==|/=", lambda match: "/=" if match[0] == "==" else "==", daml)
