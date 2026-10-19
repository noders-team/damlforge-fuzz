"""`damlforge-fuzz check`, driven through cli.main."""

import re
import subprocess
import sys

import pytest
from conftest import CONTRACTS, FLOORDIV, OWNER_FIELD, PROJECT, copy_iou

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
    (tmp_path / "floordiv.vy").write_text(FLOORDIV)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "floordiv.vy"]) == 1
    [line] = capsys.readouterr().out.splitlines()
    assert re.fullmatch(
        r"CRASH    lower  floordiv\.vy  KeyError 'FloorDiv' at forge/ir/lower\.py:\d+", line
    ), line


def test_check_prints_a_rejected_line_with_the_df_code(tmp_path, monkeypatch, capsys):
    copy_iou(tmp_path / "owner", OWNER_FIELD, "\n    owner: owner\n", count=1)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "owner/iou.vy"]) == 1
    [line] = capsys.readouterr().out.splitlines()
    assert line.startswith("REJECTED check  owner/iou.vy  DF1213: "), line


def test_check_prints_one_line_per_file_in_argument_order(tmp_path, monkeypatch, capsys):
    iou = str(CONTRACTS / "iou" / "iou.vy")
    (tmp_path / "floordiv.vy").write_text(FLOORDIV)
    monkeypatch.chdir(tmp_path)

    assert main(["check", "floordiv.vy", iou]) == 1
    crash, ok = capsys.readouterr().out.splitlines()
    assert crash.startswith("CRASH    lower  floordiv.vy  "), crash
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
    ],
    ids=["help", "usage-error", "check"],
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
