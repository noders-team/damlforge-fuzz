"""The damlc step: damlc.py's parser and key, build_daml, `check --damlc`, and `run --damlc`.

The damlc messages below are SDK 3.5.2's, the SDK in contracts/*/daml.yaml,
not results of one forge version. No test names a count or a key that one
forge version gives. The bad Daml comes from a hand-written module, or from a
forge bug the test plants. Tests that build need the `dpm` fixture, which
skips them when dpm or the SDK is missing.
"""

import contextlib
import io
import itertools
import json
import re
import shutil
import subprocess
from pathlib import Path

import forge.semantics.analysis.typecheck
import pytest
from conftest import BITAND, CONTRACTS, PROJECT, copy_iou, hide_dpm

from damlforge_fuzz import (
    DamlcUnavailable,
    DamlError,
    DamlSource,
    LoopBug,
    LoopCheck,
    Ok,
    Seed,
    build_daml,
    compile_and_sort,
    input_sequence,
)
from damlforge_fuzz.cli import main
from damlforge_fuzz.damlc import _errors, _key
from damlforge_fuzz.report import BAD_DAML_TEXT

IOU_YAML = CONTRACTS / "iou" / "daml.yaml"
BAD_IOU = "module Iou where\n\nfuzzBad = str 1\n"
GOOD_IOU = "module Iou where\n\nfuzzOk : Int\nfuzzOk = 1\n"

DPM_OUTPUT = (
    "Running single package build of damlforge-fuzz-batch as no multi-package.yaml was found.\n"
    "\n"
    "2026-10-19 17:33:18.97 [INFO]  [build] \n"
    "Compiling damlforge-fuzz-batch to a DAR.\n"
    "File:     daml/I00000/Ballot.daml\n"
    "Hidden:   no\n"
    "Range:    44:17-44:96\n"
    "Source:   typecheck\n"
    "Severity: DsError\n"
    "Message: \n"
    "\x1b[0;91mdaml/I00000/Ballot.daml:44:17: error:\n"
    "    • Constructor ‘Ballot’ does not have the required strict field(s): owner\n"
    "    • In the first argument of ‘create’, namely\n"
    "           ....\x1b[0m\n"
    "File:     daml/I00001/Iou.daml\n"
    "Hidden:   no\n"
    "Range:    30:64-30:75\n"
    "Source:   typecheck\n"
    "Severity: DsError\n"
    "Message: \n"
    "\x1b[0;91mdaml/I00001/Iou.daml:30:64: error:\n"
    "    • Possible Daml-specific reason for the following type error:\n"
    "      Tried to access nonexistent field ‘_1’ with type ‘Party’ on value of type ‘r0’\n"
    "    • Ambiguous type variable ‘r0’ arising from a use of ‘getField’\x1b[0m\n"
    "File:     daml/I00001/Iou.daml\n"
    "Hidden:   no\n"
    "Range:    30:65-30:71\n"
    "Source:   typecheck\n"
    "Severity: DsError\n"
    "Message: \n"
    "\x1b[0;91mdaml/I00001/Iou.daml:30:65: error:\n"
    '    • No instance for (GetField "x" Iou r0)\x1b[0m\n'
    "File:     daml/I00002/Ballot.daml\n"
    "Hidden:   no\n"
    "Range:    27:5-27:14\n"
    "Source:   parser\n"
    "Severity: DsError\n"
    "Message: \n"
    "\x1b[0;91mDuplicate field name organizer. Original definition at "
    "daml/I00002/Ballot.daml:26:5-13.\x1b[0m\n"
    "File:     daml/I00003/Iou.daml\n"
    "Hidden:   no\n"
    "Range:    1:1-2:1\n"
    "Source:   Daml-LF typechecker\n"
    "Severity: DsError\n"
    "Message: \n"
    "\x1b[0;91mname collision between choice I00003.Iou:Iou.Currency and field "
    "I00003.Iou:Iou.currency\x1b[0m\n"
    "File:     daml/I00004/Iou.daml\n"
    "Hidden:   no\n"
    "Range:    7:1-7:22\n"
    "Source:   typecheck\n"
    "Severity: DsWarning\n"
    "Message: \n"
    "\x1b[0;93mdaml/I00004/Iou.daml:7:1: warning:\n"
    "    The import of ‘DA.List’ is redundant\x1b[0m\n"
    "File:     daml/I00005/Iou.daml\n"
    "Hidden:   no\n"
    "Range:    3:11-3:14\n"
    "Source:   typecheck\n"
    "Severity: DsError\n"
    "Message: \n"
    "\x1b[0;91mdaml/I00005/Iou.daml:3:11: error: Variable not in scope: str : Int -> t\x1b[0m\n"
    "ERROR: Creation of DAR file failed.\n"
)
"""Real `dpm build` output (SDK 3.5.2) of a batch, with long GHC context lines cut."""


def test_errors_reads_the_first_line_of_each_error_block_and_skips_warnings():
    assert list(_errors(DPM_OUTPUT)) == [
        ("daml/I00000/Ballot.daml", DamlError(
            "Constructor ‘Ballot’ does not have the required strict field(s): owner", "typecheck", 44
        )),
        ("daml/I00001/Iou.daml", DamlError(
            "Tried to access nonexistent field ‘_1’ with type ‘Party’ on value of type ‘r0’",
            "typecheck", 30,
        )),
        ("daml/I00001/Iou.daml", DamlError("No instance for (GetField \"x\" Iou r0)", "typecheck", 30)),
        ("daml/I00002/Ballot.daml", DamlError(
            "Duplicate field name organizer. Original definition at Ballot.daml:26:5-13.", "parser", 27
        )),
        ("daml/I00003/Iou.daml", DamlError(
            "name collision between choice Iou:Iou.Currency and field Iou:Iou.currency",
            "Daml-LF typechecker", 1,
        )),
        ("daml/I00005/Iou.daml", DamlError("Variable not in scope: str : Int -> t", "typecheck", 3)),
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("message", "key"),
    [
        ("Variable not in scope: str : Int -> t", "Variable not in scope: …"),
        ("Variable not in scope: x : [a0]", "Variable not in scope: …"),
        ("Not in scope: ‘float’", "Not in scope: ‘…’"),
        ("Constructor ‘Ballot’ does not have the required strict field(s): owner",
         "Constructor ‘…’ does not have the required strict field(s): …"),
        ("Duplicate field name organizer. Original definition at Ballot.daml:26:5-13.",
         "Duplicate field name …. Original definition at …."),
        ("No instance for (IsParties Bool)", "No instance for (IsParties …)"),
        ("Couldn't match expected type ‘Map k0 Bool’", "Couldn't match expected type ‘…’"),
        ("Couldn't match type ‘Iou’ with ‘ContractId Iou’", "Couldn't match type ‘…’ with ‘…’"),
        ("Couldn't match type ‘(ContractId", "Couldn't match type ‘…’"),
        ("name collision between choice Iou:Iou.Currency and field Iou:Iou.currency",
         "name collision between choice … and field …"),
        ("Failure to process Daml program, this feature is not currently supported.",
         "Failure to process Daml program, this feature is not currently supported."),
    ],
)  # fmt: skip
def test_key_masks_the_names_that_come_from_the_input(message, key):
    assert _key(message) == key
    assert str(DamlError(message, "typecheck", 1).key) == key


def test_build_daml_without_dpm_raises_damlc_unavailable(tmp_path, monkeypatch):
    hide_dpm(monkeypatch, tmp_path)

    with pytest.raises(DamlcUnavailable, match=r"^dpm not found on PATH or at ~/\.dpm/bin/dpm$"):
        list(build_daml([DamlSource(GOOD_IOU, "Iou", IOU_YAML)]))


def test_run_damlc_without_dpm_returns_2_before_input_1(tmp_path, monkeypatch, capsys):
    hide_dpm(monkeypatch, tmp_path)
    monkeypatch.chdir(PROJECT)
    reports = tmp_path / "reports"

    assert main(["run", "--damlc", "--count", "5", "--reports", str(reports)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "damlforge-fuzz run: dpm not found on PATH or at ~/.dpm/bin/dpm\n"
    assert not reports.exists()


def test_check_damlc_refuses_a_file_without_daml_yaml(write_vy, capsys):
    path = write_vy("a.vy", "")

    assert main(["check", "--damlc", str(path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"damlforge-fuzz check: --damlc needs a daml.yaml for {path}, and found none\n"


@pytest.fixture
def planted(tmp_path, monkeypatch):
    """A copy of iou.vy that uses str(self.amount), with forge made to write `str` for it.

    DamlForge v0.0.10 writes `show self.amount`, which damlc builds; v0.0.7
    writes `str self.amount` on its own, which is the bug the plan's check
    looks for. On a forge with the conversion table, the test plants that bug
    by making the table say "str" for Decimal.
    """
    if hasattr(forge.semantics.analysis.typecheck, "_TEXT_CONVERSION"):
        conversions = forge.semantics.analysis.typecheck._TEXT_CONVERSION[1]
        monkeypatch.setitem(conversions, "Decimal", "str")
    path = copy_iou(
        tmp_path / "iou",
        '"split amount must be less than the full amount"',
        "str(self.amount)",
        count=1,
    )
    seed = Seed.load(path)
    ok = compile_and_sort(seed.text, seed)
    assert isinstance(ok, Ok) and re.search(r"assertMsg \(?str self\.amount", ok.daml), ok
    return path


def test_plan_check_1_str_amount_is_bad_daml(dpm, planted, capsys):
    assert main(["check", "--damlc", str(planted)]) == 1
    [line] = capsys.readouterr().out.splitlines()
    assert line.startswith(f"BAD_DAML emit   {planted}  Variable not in scope: str : "), line


def test_plan_check_2_the_seeds_build(dpm, monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "--damlc", "contracts"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "OK       emit   contracts/asset_proposal/asset_proposal.vy",
        "OK       emit   contracts/ballot/ballot.vy",
        "OK       emit   contracts/escrow/escrow.vy",
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


def test_check_damlc_keeps_the_other_results_and_their_order(dpm, planted, capsys):
    crash = planted.parent / "bitand.vy"
    crash.write_text(BITAND)
    iou = CONTRACTS / "iou" / "iou.vy"

    assert main(["check", "--damlc", str(iou), str(planted), str(crash)]) == 1
    ok, bad, other = capsys.readouterr().out.splitlines()
    assert ok == f"OK       emit   {iou}"
    assert bad.startswith(f"BAD_DAML emit   {planted}  "), bad
    assert other.startswith(f"CRASH    lower  {crash}  "), other


def test_two_texts_of_one_module_name_get_their_own_verdicts(dpm):
    good, bad = DamlSource(GOOD_IOU, "Iou", IOU_YAML), DamlSource(BAD_IOU, "Iou", IOU_YAML)

    assert dict(build_daml([good, bad])) == {
        good: None,
        bad: DamlError("Variable not in scope: str : Int -> t", "typecheck", 3),
    }


def test_a_verdict_does_not_depend_on_the_batch(dpm, monkeypatch):
    sources = [
        DamlSource(GOOD_IOU, "Iou", IOU_YAML),
        DamlSource(BAD_IOU, "Iou", IOU_YAML),
        DamlSource(GOOD_IOU.replace("1", "2"), "Iou", IOU_YAML),
        DamlSource(BAD_IOU.replace("1", "2"), "Iou", IOU_YAML),
        DamlSource("module Iou where\n\nx = = 1\n", "Iou", IOU_YAML),
    ]
    together = dict(build_daml(sources))
    monkeypatch.setattr("damlforge_fuzz.damlc.BATCH", 2)

    assert dict(build_daml(sources)) == together
    assert [verdict is None for verdict in together.values()] == [True, False, True, False, False]


def test_an_sdk_that_is_not_installed_is_not_bad_daml(dpm, tmp_path):
    yaml = tmp_path / "daml.yaml"
    yaml.write_text(IOU_YAML.read_text().replace("sdk-version: 3.5.2", "sdk-version: 0.0.1"))

    with pytest.raises(DamlcUnavailable, match=r"dpm install 0\.0\.1"):
        list(build_daml([DamlSource(GOOD_IOU, "Iou", yaml)]))


FINAL_LINE = re.compile(r"random seed \d+: \d+ inputs, (\d+) OK, .*")
DAMLC_LINE = re.compile(r"damlc: (\d+) Daml texts?, (\d+) bad, (\d+) bad Daml groups?")
REPORT_LINE = re.compile(r"(\d+) crash groups?, report in (.+)")


def run(reports, *argv):
    """main(["run", *argv, "--reports", reports]) in PROJECT: status, stdout lines, report.json."""
    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(out):
        patch.chdir(PROJECT)
        status = main(["run", *argv, "--reports", str(reports)])
    lines = out.getvalue().splitlines()
    folder = Path(REPORT_LINE.fullmatch(lines[-1]).group(2))
    return status, lines, folder, json.loads((folder / "report.json").read_text())


@pytest.fixture(scope="module")
def runs(dpm, tmp_path_factory):
    """`run --count 300 --random-seed 1`, with and without --damlc."""
    reports = tmp_path_factory.mktemp("reports")
    with_damlc = run(reports, "--count", "300", "--random-seed", "1", "--damlc")
    without = run(reports, "--count", "300", "--random-seed", "1")
    assert [g for g in with_damlc[3]["groups"] if g["kind"] == "bad_daml"], (
        "300 inputs should give forge Daml that damlc rejects at least once"
    )
    return with_damlc, without


def bad_groups(doc):
    return [group for group in doc["groups"] if group["kind"] == "bad_daml"]


def test_damlc_adds_one_line_and_changes_no_other(runs):
    (status, lines, folder, doc), (_, plain, plain_folder, plain_doc) = runs

    assert len(lines) == 5 and len(plain) == 4
    assert lines[:2] == plain[:2]
    assert lines[4] == plain[3].replace(str(plain_folder), str(folder))
    loops = [group for group in doc["groups"] if group["kind"] == "bad_loop"]
    builds = sum(group["damlc"] == "builds" for group in loops)
    assert lines[3] == plain[2].split(", ")[0] + (
        f", {len(loops)} loop group{'' if len(loops) == 1 else 's'}, "
        f"{builds} build{'s' if builds == 1 else ''} with damlc"
    )
    checked, bad, groups = map(int, DAMLC_LINE.fullmatch(lines[2]).groups())
    damlc = doc["damlc"]
    assert (checked, bad, groups) == (
        damlc["checked_texts"],
        damlc["bad_texts"],
        len(bad_groups(doc)),
    )
    assert (
        0 < damlc["bad_texts"] <= damlc["checked_texts"] <= int(FINAL_LINE.fullmatch(lines[1])[1])
    )
    assert damlc["interrupted"] is False and damlc["seconds"] > 0
    assert doc["totals"] == plain_doc["totals"]
    assert status == 1


def test_bad_inputs_is_the_sum_of_the_bad_daml_group_counts(runs):
    (_, _, _, doc), _ = runs

    assert doc["damlc"]["bad_inputs"] == sum(group["count"] for group in bad_groups(doc))
    assert doc["damlc"]["bad_texts"] <= doc["damlc"]["bad_inputs"] <= doc["totals"]["ok"]


def without_second(group):
    return {**group, "first_seen": group["first_seen"]["input"]}


def test_crash_groups_come_first_and_bad_daml_ids_follow_the_first_input(runs):
    (_, _, folder, doc), (_, _, _, plain_doc) = runs
    kinds = [group["kind"] for group in doc["groups"]]
    bad = bad_groups(doc)

    assert kinds == sorted(kinds, key=["crash", "bad_daml", "bad_loop"].index)
    assert [without_second(g) for g in doc["groups"] if g["kind"] == "crash"] == [
        without_second(g) for g in plain_doc["groups"] if g["kind"] == "crash"
    ]
    assert [g["id"] for g in bad] == [f"d{n:02d}" for n in range(1, len(bad) + 1)]
    firsts = [g["first_seen"]["input"] for g in bad]
    assert firsts == sorted(firsts) and len(set(firsts)) == len(firsts)
    assert len({g["key"] for g in bad}) == len(bad)
    texts = [(PROJECT / seed).read_text() for seed in doc["run"]["seeds"]]
    for group in bad:
        assert set(group) == {
            "id", "kind", "key", "message", "damlc_stage", "daml_line", "count", "first_seen",
            "seed", "input", "input_file", "daml", "daml_file",
        }  # fmt: skip
        made = next(
            itertools.islice(input_sequence(texts, 1), group["first_seen"]["input"] - 1, None)
        )
        assert group["input"] == made.text
        assert group["key"] == _key(group["message"])
        assert group["daml"].splitlines()[0] == f"module {Path(group['daml_file']).stem} where"


def test_each_bad_daml_folder_builds_with_the_same_error(runs, dpm):
    (_, _, folder, doc), _ = runs

    for group in bad_groups(doc):
        saved = folder / "groups" / group["id"]
        seed_yaml = (PROJECT / group["seed"]).parent / "daml.yaml"
        assert (saved / "daml.yaml").read_bytes() == seed_yaml.read_bytes()
        assert (folder / group["input_file"]).read_text() == group["input"]
        assert (folder / group["daml_file"]).read_text() == group["daml"]
        copy = shutil.copytree(saved, folder.parent / "rebuild" / group["id"])
        result = subprocess.run([dpm, "build"], cwd=copy, capture_output=True, text=True)
        assert result.returncode != 0, group["id"]
        _, first = next(_errors(result.stdout + result.stderr))
        assert (first.message, first.line) == (group["message"], group["daml_line"]), group["id"]


def test_each_saved_bad_daml_input_is_bad_daml_again_with_check(runs, capsys):
    (_, _, folder, doc), _ = runs

    for group in bad_groups(doc):
        path = folder / group["input_file"]
        assert main(["check", "--damlc", str(path)]) == 1
        out = capsys.readouterr().out
        # A loop bug names the cause, so check prints BAD_LOOP with damlc's error at the end.
        assert out == f"BAD_DAML emit   {path}  {group['message']}\n" or (
            out.startswith(f"BAD_LOOP emit   {path}  ")
            and out.endswith(f"; damlc rejects: {group['message']}\n")
        ), out


def test_report_md_explains_bad_daml_and_lists_every_group(runs):
    (_, _, folder, doc), _ = runs
    md = (folder / "report.md").read_text()
    lines = md.splitlines()
    bad = bad_groups(doc)

    assert BAD_DAML_TEXT in lines
    assert f"## {len(bad)} bad Daml group{'' if len(bad) == 1 else 's'}" in lines
    for group in bad:
        [row] = [line for line in lines if line.startswith(f"| {group['id']} |")]
        assert row.startswith(f"| {group['id']} | {group['count']} | "), row
        assert row.endswith(f"[{Path(group['daml_file']).name}]({group['daml_file']}) |"), row
        assert group["message"] in md


def test_two_damlc_runs_with_one_random_seed_write_the_same_report(dpm, tmp_path):
    def stable(doc):
        del doc["run"]["started"], doc["timeline"], doc["damlc"]["seconds"]
        for group in doc["groups"]:
            del group["first_seen"]["second"]
        return doc

    first = run(tmp_path, "contracts/iou", "--count", "200", "--random-seed", "3", "--damlc")
    second = run(tmp_path, "contracts/iou", "--count", "200", "--random-seed", "3", "--damlc")
    assert first[1][:3] == second[1][:3]
    assert stable(first[3]) == stable(second[3])


def test_ctrl_c_during_damlc_keeps_the_finished_batches(dpm, tmp_path, monkeypatch):
    real = build_daml

    def interrupted_after_one_batch(sources):
        yield from itertools.islice(real(sources), 5)
        raise KeyboardInterrupt

    monkeypatch.setattr("damlforge_fuzz.damlc.BATCH", 5)
    monkeypatch.setattr("damlforge_fuzz.report.build_daml", interrupted_after_one_batch)

    status, lines, folder, doc = run(tmp_path, "--count", "300", "--random-seed", "1", "--damlc")
    assert status == 130
    assert len(lines) == 5
    assert doc["run"]["interrupted"] is True
    assert doc["damlc"]["interrupted"] is True
    assert doc["damlc"]["checked_texts"] == 5
    assert lines[2].startswith("damlc: 5 Daml texts, ")
    crash = [group for group in doc["groups"] if group["kind"] == "crash"]
    assert crash and all(group["shrunk"] is not None for group in crash)
    assert (
        "Ctrl-C stopped damlc, so some texts were not built." in (folder / "report.md").read_text()
    )


def test_ctrl_c_during_damlc_leaves_an_unbuilt_loop_group_not_built(dpm, tmp_path, monkeypatch):
    bug = LoopBug(LoopCheck.L4, 5, "fetch at Daml line 5 is used as a value, not bound with <-")
    monkeypatch.setattr(
        "damlforge_fuzz.runner.compile_and_sort", lambda text, seed: Ok("", "Iou", (bug,))
    )

    def ctrl_c(sources):
        raise KeyboardInterrupt

    monkeypatch.setattr("damlforge_fuzz.report.build_daml", ctrl_c)

    status, lines, folder, doc = run(
        tmp_path, "contracts/iou", "--count", "50", "--random-seed", "1", "--damlc"
    )
    ok = int(FINAL_LINE.fullmatch(lines[1])[1])
    assert status == 130
    assert lines[2:4] == [
        "damlc: 0 Daml texts, 0 bad, 0 bad Daml groups",
        f"loops: {ok} inputs with loop findings, 1 loop group, 0 build with damlc",
    ]
    assert [(g["id"], g["damlc"], g["damlc_error"]) for g in doc["groups"]] == [("l01", None, None)]
    md = (folder / "report.md").read_text().splitlines()
    [row] = [line for line in md if line.startswith("| l01 |")]
    assert row.split(" | ")[:5] == ["| l01", "L4", "L4", str(ok), "not built"]
