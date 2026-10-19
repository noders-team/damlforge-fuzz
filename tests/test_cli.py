"""`damlforge-fuzz check`, driven through cli.main."""

import re
import subprocess
import sys

import pytest
from conftest import BITAND, CONTRACTS, OWNER_FIELD, PROJECT, copy_iou

from damlforge_fuzz.cli import main


def test_check_on_the_contracts_folder_prints_four_ok_lines_and_returns_0(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "contracts"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "OK       emit   contracts/asset_proposal/asset_proposal.vy",
        "OK       emit   contracts/ballot/ballot.vy",
        "OK       emit   contracts/escrow/escrow.vy",
        "OK       emit   contracts/iou/iou.vy",
    ]


def test_check_prints_a_crash_line_with_exception_message_and_forge_line(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "bitand.vy").write_text(BITAND)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "bitand.vy"]) == 1
    [line] = capsys.readouterr().out.splitlines()
    assert re.fullmatch(
        r"CRASH    lower  bitand\.vy  KeyError 'BitAnd' at forge/ir/lower\.py:\d+", line
    ), line


def test_check_prints_a_rejected_line_with_the_df_code(tmp_path, monkeypatch, capsys):
    copy_iou(tmp_path / "owner", OWNER_FIELD, "\n    owner: owner\n", count=1)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "owner/iou.vy"]) == 1
    [line] = capsys.readouterr().out.splitlines()
    assert line.startswith("REJECTED check  owner/iou.vy  DF1213: "), line


def test_check_prints_one_line_per_file_in_argument_order(tmp_path, monkeypatch, capsys):
    iou = str(CONTRACTS / "iou" / "iou.vy")
    (tmp_path / "bitand.vy").write_text(BITAND)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "bitand.vy", iou]) == 1
    crash, ok = capsys.readouterr().out.splitlines()
    assert crash.startswith("CRASH    lower  bitand.vy  "), crash
    assert ok == f"OK       emit   {iou}"


def test_check_lists_a_file_once_when_two_arguments_cover_it(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "contracts", "contracts/iou"]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 4


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
        (["check", "x.vy"], 2, "stderr", "Install DamlForge first"),
        (["run", "--help"], 0, "stdout", "--random-seed"),
        (["run", "--help"], 0, "stdout", "--reports DIR"),
        (["run"], 2, "stderr", "one of the arguments --seconds --count is required"),
        (["run", "--count", "5", "--seconds", "5"], 2, "stderr", "not allowed with"),
        (["run", "--count", "0"], 2, "stderr", "argument --count: '0' is not a whole number"),
        (["run", "--count", "5"], 2, "stderr", "Install DamlForge first"),
        (["shrink", "--help"], 0, "stdout", "FILE"),
        (["shrink", "x.vy"], 2, "stderr", "Install DamlForge first"),
        (["check", "--damlc", "x.vy"], 2, "stderr", "Install DamlForge first"),
        (["run", "--help"], 0, "stdout", "--damlc"),
        (["run", "--damlc", "--count", "5"], 2, "stderr", "Install DamlForge first"),
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
