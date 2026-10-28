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

"""`damlforge-fuzz check`, driven through cli.main."""

import subprocess
import sys

import pytest
from conftest import CONTRACTS, OWNER_FIELD, PROJECT, SEED_FILES, copy_iou
from planted_crash import IN_LOWER, Planted, plant

from damlforge_fuzz import ForgeLine, Stage
from damlforge_fuzz.cli import main


def test_check_on_the_contracts_folder_prints_an_ok_line_for_each_seed_and_returns_0(
    monkeypatch, capsys
):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "contracts"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "OK       emit   contracts/asset_proposal/asset_proposal.vy",
        "OK       emit   contracts/ballot/ballot.vy",
        "OK       emit   contracts/escrow/escrow.vy",
        "OK       emit   contracts/import_call/import_call.vy",
        "OK       emit   contracts/import_call/models.vy",
        "OK       emit   contracts/import_qualified/import_qualified.vy",
        "OK       emit   contracts/import_qualified/models.vy",
        "OK       emit   contracts/import_sibling/import_sibling.vy",
        "OK       emit   contracts/import_sibling/models.vy",
        "OK       emit   contracts/iou/iou.vy",
        "OK       emit   contracts/loop_count/loop_count.vy",
        "OK       emit   contracts/loop_give/loop_give.vy",
        "OK       emit   contracts/loop_many/loop_many.vy",
        "OK       emit   contracts/loop_pure/loop_pure.vy",
        "OK       emit   contracts/loop_verify/loop_verify.vy",
    ]


def test_check_prints_a_crash_line_with_exception_message_and_forge_line(
    tmp_path, monkeypatch, capsys
):
    where = ForgeLine("forge/ir/lower.py", 289)
    plant(monkeypatch, Planted("# crash", Stage.LOWER, KeyError, "BitAnd", where))
    (tmp_path / "planted.vy").write_text("# crash\n")
    monkeypatch.chdir(tmp_path)

    assert main(["check", "planted.vy"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "CRASH    lower  planted.vy  KeyError 'BitAnd' at forge/ir/lower.py:289"
    ]


def test_check_prints_a_rejected_line_with_the_df_code(tmp_path, monkeypatch, capsys):
    copy_iou(tmp_path / "owner", OWNER_FIELD, "\n    owner: owner\n", count=1)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "owner/iou.vy"]) == 1
    [line] = capsys.readouterr().out.splitlines()
    assert line.startswith("REJECTED check  owner/iou.vy  DF1213: "), line


def test_check_prints_one_line_per_file_in_argument_order(tmp_path, monkeypatch, capsys):
    plant(monkeypatch, IN_LOWER)
    iou = str(CONTRACTS / "iou" / "iou.vy")
    (tmp_path / "planted.vy").write_text(IN_LOWER.trigger)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "planted.vy", iou]) == 1
    crash, ok = capsys.readouterr().out.splitlines()
    assert crash.startswith("CRASH    lower  planted.vy  "), crash
    assert ok == f"OK       emit   {iou}"


def test_check_lists_a_file_once_when_two_arguments_cover_it(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "contracts", "contracts/iou"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == len(SEED_FILES)


def test_check_skips_hidden_folders(tmp_path, capsys):
    seeds = tmp_path / "seeds"
    (seeds / ".daml").mkdir(parents=True)
    (seeds / "a.vy").write_text("")
    (seeds / ".daml" / "b.vy").write_text("")

    assert main(["check", str(seeds)]) == 0
    assert capsys.readouterr().out.splitlines() == [f"OK       emit   {seeds / 'a.vy'}"]


def test_missing_path_returns_2_with_no_result_lines(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "contracts/iou/iou.vy", "nope.vy"]) == 2
    out, err = capsys.readouterr()
    assert out == "", "no result line should print, not even iou.vy's OK"
    assert "nope.vy" in err


def test_folder_without_vy_files_returns_2(tmp_path, capsys):
    assert main(["check", str(tmp_path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert str(tmp_path) in err


@pytest.mark.parametrize(
    ("argv", "status", "stream", "expected"),
    [
        (["--help"], 0, "stdout", "check"),
        (["check"], 2, "stderr", "usage: damlforge-fuzz check"),
        (["check", "x.vy"], 2, "stderr", "pip install damlforge"),
        (["run", "--help"], 0, "stdout", "--random-seed"),
        (["run", "--help"], 0, "stdout", "--reports DIR"),
        (["run"], 2, "stderr", "one of the arguments --seconds --count is required"),
        (["run", "--count", "5", "--seconds", "5"], 2, "stderr", "not allowed with"),
        (["run", "--count", "0"], 2, "stderr", "argument --count: '0' is not a whole number"),
        (["run", "--count", "5"], 2, "stderr", "pip install damlforge"),
        (["shrink", "--help"], 0, "stdout", "FILE"),
        (["shrink", "x.vy"], 2, "stderr", "pip install damlforge"),
        (["check", "--damlc", "x.vy"], 2, "stderr", "pip install damlforge"),
        (["run", "--help"], 0, "stdout", "--damlc"),
        (["run", "--damlc", "--count", "5"], 2, "stderr", "pip install damlforge"),
    ],
    ids=["help", "usage-error", "check", "run-help", "run-help-reports", "run-no-limit",
         "run-two-limits", "run-count-0", "run", "shrink-help", "shrink", "check-damlc",
         "run-help-damlc", "run-damlc"],  # fmt: skip
)
def test_command_works_without_forge_installed(argv, status, stream, expected):
    hide_forge = (
        "import sys; sys.modules['forge'] = None; "
        "from damlforge_fuzz.cli import main; sys.exit(main(sys.argv[1:]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", hide_forge, *argv], capture_output=True, text=True
    )
    assert result.returncode == status, result.stderr
    assert expected in getattr(result, stream)
