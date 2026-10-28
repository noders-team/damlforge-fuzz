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

"""Forge crashes that a test plants, so that no test of the fuzzer needs a real forge bug.

Each DamlForge release fixes crashes: 0.0.13 rejects `count & 1`, which
crashed earlier versions in lower. A test that needs a crash plants one with
plant(). The planted crash raises in a frame whose code has the path of a
forge file, at the line and in the stage that the test chose. compile_and_sort sorts it as it sorts a real
crash, by the stage that was running and the innermost forge frame of the
traceback. So the test controls the exception, the message, the stage, the
forge file, and the line, on any forge version.

A text crashes when one of its lines is the trigger of a planted crash. The
shrinker keeps that line, because without it the text no longer crashes.
"""

from dataclasses import dataclass
from pathlib import Path

import forge
import pytest

import damlforge_fuzz.compiler
from damlforge_fuzz import ForgeLine, Stage

FORGE_FOLDER = Path(forge.__file__).resolve().parent.parent
"""The folder that holds the forge package. A ForgeLine's file is relative to it."""

_STAGE_FUNCTION = {
    Stage.PARSE: "parse_to_ast",
    Stage.CHECK: "analyze_module",
    Stage.LOWER: "lower_module",
    Stage.EMIT: "generate_daml",
}
"""The name in damlforge_fuzz.compiler of the forge function that runs each stage."""


@dataclass(frozen=True)
class Planted:
    """A forge crash in `stage` for each text that has the line `trigger`, at any indent.

    It raises exception(message) at `where`, before forge runs the stage, so
    the text must get through the stages before it. The fuzzer reads only the
    path of `where.file`, so the file need not exist in every forge version.
    """

    trigger: str
    stage: Stage
    exception: type[Exception]
    message: str
    where: ForgeLine


IN_LOWER = Planted(
    "# crash in lower", Stage.LOWER, KeyError, "planted", ForgeLine("forge/ir/lower.py", 30)
)
"""One crash. A text that holds only the trigger line gets to lower on any forge version."""

IN_RUNS = (
    Planted("pass", Stage.CHECK, KeyError, "planted in check",
            ForgeLine("forge/ir/lower.py", 40)),
    Planted("for _k in range(0, 2):", Stage.PARSE, IndexError, "planted in parse",
            ForgeLine("forge/ast/parse.py", 50)),
)  # fmt: skip
"""Two crashes, in two stages, for runs over the seeds in contracts/.

The insert_statement rule writes `pass` lines, and the wrap_in_loop rule
writes the other trigger, so a run of a few hundred inputs gets both crashes.
No seed has either line, so every seed compiles as before.
"""


def plant(monkeypatch: pytest.MonkeyPatch, *crashes: Planted) -> None:
    """Make compile_and_sort crash as `crashes` say, until `monkeypatch` is undone.

    Wraps the forge functions in damlforge_fuzz.compiler, the only module that
    calls them. A text with no trigger compiles as before.
    """
    # The later stages get forge's syntax tree, so they look at the text that parse_to_ast got.
    compiling = ""

    def wrap(stage: Stage, real):
        def run_stage(*args, **kwargs):
            nonlocal compiling
            if stage is Stage.PARSE:
                compiling = args[0]
            lines = {line.strip() for line in compiling.splitlines()}
            for crash in crashes:
                if crash.stage is stage and crash.trigger in lines:
                    _raise_in_forge(crash.exception(crash.message), crash.where)
            return real(*args, **kwargs)

        return run_stage

    for stage, name in _STAGE_FUNCTION.items():
        real = getattr(damlforge_fuzz.compiler, name)
        monkeypatch.setattr(damlforge_fuzz.compiler, name, wrap(stage, real))


def _raise_in_forge(error: Exception, where: ForgeLine) -> None:
    """Raise `error` from library code that line `where.line` of the forge file `where.file` calls.

    As in a real crash, other forge code calls that line, here forge/__init__.py.
    So the crash is at `where` only when the fuzzer takes the innermost forge frame.
    """

    def library():
        raise error

    line = compile("\n" * (where.line - 1) + "library()", str(FORGE_FOLDER / where.file), "exec")
    caller = compile("exec(line, {'library': library})", forge.__file__, "exec")
    exec(caller, {"line": line, "library": library})
