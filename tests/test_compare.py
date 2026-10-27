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

"""The compare step: calls files, the Python side, `check --compare`, and `run --compare`.

Tests that run Daml need the `dpm` fixture. The tests that name a difference
that one forge version makes, such as the lost assert of b23 in bugs/loops/,
also need `fixture_forge`, as the bug programs in test_loopcheck.py do. The run
tests check relations, so they hold on any forge version.
"""

import contextlib
import io
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import CONTRACTS, PROJECT, hide_dpm

from damlforge_fuzz import (
    Count,
    CompareInput,
    DamlError,
    DamlSource,
    Dropped,
    Ok,
    Report,
    Seed,
    Skipped,
    fuzz,
    load_calls,
    run_and_compare,
)
from damlforge_fuzz.cli import main
from damlforge_fuzz.report import BAD_RUN_TEXT


def copy_seed(
    folder: Path, name: str, old: str = "", new: str = "", calls: str | None = None
) -> Path:
    shutil.copytree(CONTRACTS / name, folder)
    vy = folder / f"{name}.vy"
    text = vy.read_text()
    assert text.count(old) == 1 or old == "", f"{name}.vy should contain {old!r} once"
    vy.write_text(text.replace(old, new, 1) if old else text)
    if calls is not None:
        (folder / f"{name}.calls.yaml").write_text(calls)
    return vy


GIVE = "  contract: {issuer: alice, owner: alice, amount: '1.0'}\n"


@pytest.mark.parametrize(
    ("name", "calls", "error"),
    [
        (
            "loop_give",
            f"- choice: Iou.GiveAll\n{GIVE}  args: {{owners: [alice], stop: stop, n: 1}}\n",
            ", call 1 (Iou.GiveAll): the parameters of GiveAll are owners, stop, "
            'and the call gives {"owners": ["alice"], "stop": "stop", "n": 1}',
        ),
        (
            "loop_give",
            f"- choice: Iou.GiveAll\n{GIVE}  args: {{owners: alice, stop: stop}}\n",
            ', call 1 (Iou.GiveAll): "alice" is not a list[Party] for owners',
        ),
        (
            "loop_give",
            f"- choice: Iou.Take\n{GIVE}  args: {{}}\n",
            ", call 1 (Iou.Take): template Iou has no choice 'Take'",
        ),
        (
            "loop_give",
            "- function: give\n  args: {}\n",
            ", call 1 (give): the seed has no function 'give'",
        ),
        (
            "loop_give",
            "- choice: Iou.GiveAll\n"
            "  contract: {issuer: alice, owner: alice, amount: '1.00000000001'}\n"
            "  args: {owners: [alice], stop: stop}\n",
            ', call 1 (Iou.GiveAll): "1.00000000001" is not a Decimal for amount',
        ),
        ("loop_give", "choice: Iou.GiveAll\n", ": a calls file is a list of calls"),
    ],
    ids=[
        "unknown-parameter",
        "wrong-type",
        "unknown-choice",
        "unknown-function",
        "11-decimal-places",
        "not-a-list",
    ],  # fmt: skip
)
def test_a_calls_file_that_does_not_fit_its_seed_is_a_usage_error(
    name, calls, error, tmp_path, capsys
):
    vy = copy_seed(tmp_path / name, name, calls=calls)

    assert main(["check", "--compare", str(vy)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err == f"damlforge-fuzz check: {vy.with_name(f'{name}.calls.yaml')}{error}\n"


def test_run_compare_needs_a_seed_with_a_calls_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)
    reports = tmp_path / "reports"

    assert (
        main(["run", "contracts/iou", "--compare", "--count", "5", "--reports", str(reports)]) == 2
    )
    out, err = capsys.readouterr()
    assert out == ""
    assert err == (
        "damlforge-fuzz run: --compare needs a calls file next to a seed, such as "
        "contracts/loop_give/loop_give.calls.yaml, and found none\n"
    )
    assert not reports.exists()


def test_run_compare_without_dpm_returns_2_before_input_1(tmp_path, monkeypatch, capsys):
    hide_dpm(monkeypatch, tmp_path)
    monkeypatch.chdir(PROJECT)
    reports = tmp_path / "reports"

    assert (
        main(["run", "contracts/loop_give", "--compare", "--count", "5", "--reports", str(reports)])
        == 2
    )
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "damlforge-fuzz run: dpm not found on PATH or at ~/.dpm/bin/dpm\n"
    assert not reports.exists()


MANY = Seed.load(CONTRACTS / "loop_many" / "loop_many.vy")


@pytest.mark.parametrize(
    ("old", "new", "reasons"),
    [
        (
            "return cids\n",
            "return cids\nassert False\n",
            ("line 21: a module-level statement, which forge does not run",),
        ),
        (
            "    amount: Decimal\n",
            "    amount: Decimal\n    x = 1\n",
            ("line 9: a statement in class Iou, which forge does not run",),
        ),
        (
            "owners: list[Party]",
            "owners: list[int]",
            ("Iou.Many #1: a definition it needs differs from the seed's",),
        ),
        (
            "        return cids",
            "        while True:\n            pass\n        return cids",
            ("Iou.Many #1: _TooLong: the call ran more than 100000 lines of Python",),
        ),
        (
            "cids.append(cid)",
            "cids.append(cid, cid)",
            ("Iou.Many #1: TypeError: list.append() takes exactly one argument (2 given)",),
        ),
        (
            "return cids",
            "return 1",
            (
                "Iou.Many #1: Python's outcome does not fit the seed's types: "
                "1 is not a list[ContractId[Iou]]",
            ),
        ),
    ],
    ids=[
        "module-statement",
        "class-statement",
        "changed-parameter",
        "endless-loop",
        "python-error",
        "unfit-result",
    ],  # fmt: skip
)
def test_python_skips_an_input_that_it_cannot_compare(old, new, reasons):
    assert MANY.text.count(old) == 1
    text = MANY.text.replace(old, new)
    item = CompareInput(text, Ok("", "LoopMany"), MANY, load_calls(MANY))

    assert list(run_and_compare({"input": item})) == [("input", Skipped(reasons))]


def test_a_daml_text_that_damlc_rejected_drops_the_input_without_a_build(tmp_path, monkeypatch):
    hide_dpm(monkeypatch, tmp_path)
    ok = Ok("module LoopMany where\n", "LoopMany")
    error = DamlError("Variable not in scope: foldlA", "typecheck", 3)
    verdicts = {DamlSource(ok.daml, ok.module_name, MANY.daml_yaml): error}
    item = CompareInput(MANY.text, ok, MANY, load_calls(MANY))

    assert list(run_and_compare({"input": item}, verdicts)) == [("input", Dropped(error))]


def test_ctrl_c_during_compare_keeps_the_finished_results(tmp_path, monkeypatch):
    seed = Seed.load(CONTRACTS / "loop_give" / "loop_give.vy")
    report = Report.open(
        [seed], 1, Count(300), tmp_path, compare={str(seed.path): load_calls(seed)}
    )
    for tried in fuzz([seed], 1, Count(300)):
        report.add(tried)

    def two_then_ctrl_c(inputs, verdicts):
        for key in list(inputs)[:2]:
            yield key, Skipped(("python",))
        raise KeyboardInterrupt

    monkeypatch.setattr("damlforge_fuzz.report.run_and_compare", two_then_ctrl_c)
    with pytest.raises(KeyboardInterrupt):
        report.run_and_compare()
    first = report.compare
    monkeypatch.setattr(
        "damlforge_fuzz.report.run_and_compare",
        lambda inputs, verdicts: ((key, Skipped(("python",))) for key in inputs),
    )
    report.run_and_compare()

    assert (first.compared, first.dropped, first.interrupted) == (0, 0, True)
    assert 2 <= first.skipped < report.totals.ok
    assert report.compare.skipped == report.totals.ok
    report.write()
    md = (report.folder / "report.md").read_text().splitlines()
    assert "Ctrl-C stopped the compare step, so some inputs were not compared." in md


LOOP_SEEDS = sorted(str(path.relative_to(PROJECT)) for path in CONTRACTS.glob("loop_*"))
FINAL_LINE = re.compile(r"random seed \d+: \d+ inputs, (\d+) OK, .*")
REPORT_LINE = re.compile(r"(\d+) crash groups?, report in (.+)")


@pytest.fixture(scope="module")
def compare_run(dpm, tmp_path_factory):
    """`run contracts/loop_* --count 136 --random-seed 251 --compare`: status,
    stdout lines, run folder, report.json."""
    reports = tmp_path_factory.mktemp("reports")
    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(out):
        patch.chdir(PROJECT)
        status = main(
            ["run", *LOOP_SEEDS, "--count", "136", "--random-seed", "251", "--compare"]
            + ["--reports", str(reports)]
        )
    lines = out.getvalue().splitlines()
    folder = Path(REPORT_LINE.fullmatch(lines[-1]).group(2))
    doc = json.loads((folder / "report.json").read_text())
    assert run_groups(doc), "136 inputs of random seed 251 should differ at least once"
    return status, lines, folder, doc


def run_groups(doc):
    return [group for group in doc["groups"] if group["kind"] == "bad_run"]


def test_compare_prints_one_line_after_the_loops_line_and_counts_every_ok_input(compare_run):
    status, lines, _, doc = compare_run
    groups = run_groups(doc)
    compare = doc["compare"]

    assert status == 1
    assert len(lines) == 5 and lines[2].startswith("loops: ")
    differ = "differs" if compare["differ"] == 1 else "differ"
    assert lines[3] == (
        f"compare: {compare['compared']} inputs compared, {compare['differ']} {differ}, "
        f"{len(groups)} run group{'' if len(groups) == 1 else 's'}"
    )
    ok = int(FINAL_LINE.fullmatch(lines[1])[1])
    assert compare["compared"] + compare["skipped"] + compare["dropped"] == ok
    assert compare["differ"] == sum(group["count"] for group in groups)
    assert compare["interrupted"] is False and compare["seconds"] > 0


def test_each_run_group_folder_is_a_daml_project_whose_test_fails_on_the_call(compare_run, dpm):
    _, _, folder, doc = compare_run
    script = {
        "result": "result",
        "contracts": "contracts",
        "daml_fails": "runs",
        "daml_passes": "fails",
    }

    for group in run_groups(doc):
        saved = folder / "groups" / group["id"]
        assert set(group) == {
            "id", "kind", "difference", "call", "loop_check", "python", "count", "first_seen",
            "seed", "input", "input_file", "calls_file", "daml", "daml_file", "test", "test_file",
        }  # fmt: skip
        seed = PROJECT / group["seed"]
        assert group["input_file"] == f"groups/{group['id']}/{seed.name}"
        assert (folder / group["input_file"]).read_text() == group["input"]
        assert group["calls_file"] == f"groups/{group['id']}/{seed.stem}.calls.yaml"
        assert (folder / group["calls_file"]).read_bytes() == (
            seed.with_name(f"{seed.stem}.calls.yaml").read_bytes()
        )
        assert (folder / group["daml_file"]).read_text() == group["daml"]
        assert (folder / group["test_file"]).read_text() == group["test"]
        assert "source: daml\n" in (saved / "daml.yaml").read_text()
        result = subprocess.run([dpm, "test"], cwd=saved, capture_output=True, text=True)
        number = group["call"].rpartition("#")[2]
        failed = re.findall(r"^daml/Test\.daml:(\w+): failed", result.stdout + result.stderr, re.M)
        assert f"c{number}_{script[group['difference']]}" in failed, group["id"]


def test_check_compare_prints_bad_run_for_the_bug_programs_and_each_saved_run_group(
    compare_run, fixture_forge, tmp_path, monkeypatch, capsys
):
    _, _, folder, doc = compare_run
    groups = run_groups(doc)
    same = copy_seed(tmp_path / "is", "loop_give", "if o != stop:", "if o is not stop:")
    issuer = "signatory: list[Party] = [issuer]"
    owner = issuer.replace("[issuer]", "[owner]")
    signed_by_owner = copy_seed(tmp_path / "owner", "loop_many", issuer, owner)
    saved = [folder / group["input_file"] for group in groups]
    bugs = ["b21_return_in_create_loop", "b22_return_in_inner_loop", "b23_pass_in_loop"]
    monkeypatch.chdir(PROJECT)

    paths = [*(f"bugs/loops/{name}.vy" for name in bugs), same, signed_by_owner, "contracts/iou"]
    paths += saved
    assert main(["check", "--compare", *map(str, paths)]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "BAD_RUN  emit   bugs/loops/b21_return_in_create_loop.vy  contracts in Iou.GiveUntil #1: "
        "returns None, makes 1 contract: Iou(issuer=issuer, owner=alice, amount=1.0); "
        "loop check L3",
        "BAD_RUN  emit   bugs/loops/b22_return_in_inner_loop.vy  result in first_positive #1: "
        "returns 3; loop check L3",
        "BAD_RUN  emit   bugs/loops/b23_pass_in_loop.vy  daml_passes in Iou.Check #2: "
        "fails: positive",
        f"OK       emit   {same}",
        f"OK       emit   {signed_by_owner}",
        "OK       emit   contracts/iou/iou.vy",
    ] + [
        f"BAD_RUN  emit   {path}  {g['difference']} in {g['call']}: {g['python']}"
        + ("" if g["loop_check"] is None else f"; loop check {g['loop_check']}")
        for path, g in zip(saved, groups, strict=True)
    ]


def test_report_md_explains_bad_run_and_lists_every_run_group(compare_run):
    _, _, folder, doc = compare_run
    md = (folder / "report.md").read_text().splitlines()
    groups = run_groups(doc)

    assert BAD_RUN_TEXT in md
    assert f"## {len(groups)} run group{'' if len(groups) == 1 else 's'}" in md
    for group in groups:
        [row] = [line for line in md if line.startswith(f"| {group['id']} |")]
        assert row.startswith(f"| {group['id']} | {group['difference']} | {group['call']} | "), row
        assert f"Run `dpm test` in groups/{group['id']} to see what Daml does." in "\n".join(md)
