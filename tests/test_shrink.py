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

"""The shrinker, through shrink() and `damlforge-fuzz shrink FILE`.

The crash tests make their own crash: they delete "Mod" from forge's _BIN_OPS
table, so `a % b` crashes in lower on any forge version that has the table.
No seed uses `%`, so the planted function is the only code that can keep the
crash, and the test knows the exact lines that must come back. If forge
renames the table, monkeypatch.delitem fails in the fixture, not in an assertion.

The loop tests use HAS_PARTY, which has the loop bug b22 on DamlForge v0.0.7
and 0.0.11.
"""

import itertools
import shutil
from pathlib import Path, PurePosixPath

import forge.ir.lower
import pytest
from conftest import CONTRACTS, copy_iou

from damlforge_fuzz import (
    Crash,
    DamlSource,
    LoopCheck,
    Ok,
    Seed,
    build_daml,
    compile_and_sort,
    same_crash,
    same_loop,
    shrink,
    shrunk_path,
)
from damlforge_fuzz.cli import main

PLANTED = "def rest(a: int, b: int) -> int:\n    return a % b\n"

HAS_PARTY = """\
from forge.models import Party


def double(n: int) -> int:
    return n + n


def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
        for _k in range(0, 2):
            return True
    return False
"""
"""forge loses the `return` in the inner loop (b22) and writes `has_party ps p = False`.
That is L3, and damlc builds it. Without `return False`, forge writes `()`, which damlc rejects."""

LOST_RETURN = """\
def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
        for _k in range(0, 2):
            return True
"""


@pytest.fixture
def planted(tmp_path, monkeypatch):
    """A copy of contracts/iou/ with PLANTED before `@template`, and `%` missing from forge."""
    monkeypatch.delitem(forge.ir.lower._BIN_OPS, "Mod")
    return copy_iou(tmp_path / "iou", "@template", PLANTED + "\n\n@template", count=1)


@pytest.fixture
def has_party(tmp_path):
    """loop_pure.vy with the text HAS_PARTY, in a copy of contracts/loop_pure/ with its daml.yaml."""
    folder = shutil.copytree(CONTRACTS / "loop_pure", tmp_path / "loop_pure")
    path = folder / "loop_pure.vy"
    path.write_text(HAS_PARTY)
    return path


def crash_key(path):
    seed = Seed.load(path)
    outcome = compile_and_sort(seed.text, seed)
    assert isinstance(outcome, Crash), outcome
    return seed, outcome.key


def test_shrink_keeps_only_the_planted_function(planted):
    seed, key = crash_key(planted)

    assert shrink(seed.text, seed, same_crash(key)) == PLANTED


def test_shrinking_the_result_again_changes_nothing(planted):
    seed, key = crash_key(planted)
    once = shrink(seed.text, seed, same_crash(key))

    assert shrink(once, seed, same_crash(key)) == once


def test_shrink_returns_the_text_when_no_line_can_go(planted):
    seed, key = crash_key(planted)

    assert shrink(PLANTED, seed, same_crash(key)) == PLANTED


def test_shrink_returns_the_text_for_a_key_it_never_crashes_with(planted):
    seed, key = crash_key(planted)
    other = type(key)("KeyError", None)

    assert shrink(seed.text, seed, same_crash(other)) == seed.text


def test_shrink_keeps_the_first_loop_check_of_a_loop_input(has_party):
    seed = Seed.load(has_party)

    small = shrink(seed.text, seed, same_loop(LoopCheck.L3, None, seed))
    assert small == LOST_RETURN
    outcome = compile_and_sort(small, seed)
    assert isinstance(outcome, Ok) and outcome.loop_key == LoopCheck.L3


def test_shrinking_a_loop_input_again_changes_nothing(has_party):
    seed = Seed.load(has_party)
    once = shrink(seed.text, seed, same_loop(LoopCheck.L3, None, seed))

    assert shrink(once, seed, same_loop(LoopCheck.L3, None, seed)) == once


def test_shrink_returns_the_text_for_a_loop_check_it_never_fails(has_party):
    seed = Seed.load(has_party)

    assert shrink(seed.text, seed, same_loop(LoopCheck.L1, None, seed)) == HAS_PARTY


def test_shrink_keeps_the_damlc_verdict_of_a_loop_input(dpm, has_party):
    seed = Seed.load(has_party)

    small = shrink(seed.text, seed, same_loop(LoopCheck.L3, "builds", seed))
    assert small == LOST_RETURN + "    return False\n"
    outcome = compile_and_sort(small, seed)
    assert outcome.loop_key == LoopCheck.L3
    [(_, error)] = build_daml([DamlSource(outcome.daml, outcome.module_name, seed.daml_yaml)])
    assert error is None


def test_shrunk_path_is_a_shrunk_folder_next_to_the_file():
    assert shrunk_path(Path("groups/g02/escrow.vy")) == Path("groups/g02/shrunk/escrow.vy")
    assert shrunk_path(PurePosixPath("groups/g02/escrow.vy")) == PurePosixPath(
        "groups/g02/shrunk/escrow.vy"
    )


def test_shrink_file_writes_the_planted_function_and_prints_it(planted, capsys):
    lines_before = len(planted.read_text().splitlines())

    assert main(["shrink", str(planted)]) == 0
    out = planted.parent / "shrunk" / "iou.vy"
    assert out.read_text() == PLANTED
    assert capsys.readouterr().out == (
        f"shrunk {planted} from {lines_before} to 2 lines: {out}\n" + PLANTED
    )


def test_shrunk_file_crashes_in_the_same_group_as_its_input(planted, capsys):
    assert main(["shrink", str(planted)]) == 0
    capsys.readouterr()

    assert main(["check", str(planted), str(planted.parent / "shrunk" / "iou.vy")]) == 1
    full, small = capsys.readouterr().out.splitlines()
    assert full.startswith("CRASH    lower  "), full
    assert full.split("  ")[-1] == small.split("  ")[-1], (full, small)


def test_shrink_file_writes_a_bad_loop_file_shrunk_by_its_first_check(has_party, capsys):
    assert main(["shrink", str(has_party)]) == 0
    out = has_party.parent / "shrunk" / "loop_pure.vy"
    assert out.read_text() == LOST_RETURN
    assert capsys.readouterr().out == (
        f"shrunk {has_party} from 12 to 4 lines: {out}\n" + LOST_RETURN
    )


def test_shrink_file_damlc_keeps_damlcs_verdict_on_a_bad_loop_file(dpm, has_party, capsys):
    assert main(["shrink", "--damlc", str(has_party)]) == 0
    out = has_party.parent / "shrunk" / "loop_pure.vy"
    assert out.read_text() == LOST_RETURN + "    return False\n"
    assert capsys.readouterr().out == (
        f"shrunk {has_party} from 12 to 5 lines: {out}\n" + LOST_RETURN + "    return False\n"
    )


def test_shrink_file_damlc_refuses_a_file_without_daml_yaml(write_vy, capsys):
    path = write_vy("has_party.vy", HAS_PARTY)

    assert main(["shrink", "--damlc", str(path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"damlforge-fuzz shrink: --damlc needs a daml.yaml for {path}, and found none\n"
    assert not (path.parent / "shrunk").exists()


def test_shrink_file_on_a_file_with_no_crash_and_no_loop_bug_returns_1_and_writes_nothing(
    tmp_path, capsys
):
    iou = copy_iou(tmp_path / "iou", "@template", "@template", count=1)

    assert main(["shrink", str(iou)]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"{iou} does not crash forge and has no loop bug: OK emit\n"
    assert not (iou.parent / "shrunk").exists()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["shrink"], "usage: damlforge-fuzz shrink"),
        (["shrink", "nope.vy"], "nope.vy"),
        (["shrink", "a.vy", "b.vy"], "unrecognized arguments: b.vy"),
    ],
    ids=["no-file", "missing-file", "two-files"],
)
def test_shrink_usage_errors_return_2(argv, expected, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    try:
        status = main(argv)
    except SystemExit as exit:
        status = exit.code
    assert status == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert expected in err


def test_shrink_file_refuses_a_folder(capsys):
    assert main(["shrink", str(CONTRACTS / "iou")]) == 2
    assert "is a folder" in capsys.readouterr().err


def test_shrink_file_refuses_a_file_in_a_shrunk_folder(planted, capsys):
    assert main(["shrink", str(planted)]) == 0
    capsys.readouterr()
    shrunk = planted.parent / "shrunk" / "iou.vy"

    assert main(["shrink", str(shrunk)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"damlforge-fuzz shrink: {shrunk} is already a shrunk file\n"
    assert not (shrunk.parent / "shrunk").exists()


def test_ctrl_c_during_shrink_file_returns_130_and_writes_nothing(
    planted, monkeypatch, capsys
):
    calls = itertools.count(1)

    def interrupted_at_call_5(text, seed):
        if next(calls) == 5:
            raise KeyboardInterrupt
        return compile_and_sort(text, seed)

    monkeypatch.setattr("damlforge_fuzz.shrinker.compile_and_sort", interrupted_at_call_5)

    assert main(["shrink", str(planted)]) == 130
    assert capsys.readouterr().out == ""
    assert not (planted.parent / "shrunk").exists()
