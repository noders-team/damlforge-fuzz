"""The run folder that `damlforge-fuzz run` writes: report.json, report.md, and groups/.

No test names a crash that one DamlForge version gives, such as an exception,
a forge line, or a group count. forge fixes bugs between versions (v0.0.10
compiles `a // b`), and such a test would break on the next fix. The tests
check relations instead: the report against the printed lines, against
`check`, and against the input sequence.
"""

import contextlib
import datetime
import io
import itertools
import json
import re
import time
from pathlib import Path

import forge
import pytest
from conftest import CONTRACTS, PROJECT, SEED_FILES

from damlforge_fuzz import (
    STAGE_TEXT,
    Count,
    Crash,
    FirstSeen,
    ForgeLine,
    Group,
    Ok,
    Report,
    Seed,
    Stage,
    compile_and_sort,
    fuzz,
    input_sequence,
    shrink,
)
from damlforge_fuzz.cli import main

FINAL_LINE = re.compile(
    r"random seed (\d+): (\d+) inputs, (\d+) OK, (\d+) rejected, (\d+) crash, (\d+) skipped"
)
REPORT_LINE = re.compile(r"(\d+) crash groups?, report in (.+)")
SEEDS = [
    "contracts/asset_proposal/asset_proposal.vy",
    "contracts/ballot/ballot.vy",
    "contracts/escrow/escrow.vy",
    "contracts/import_call/import_call.vy",
    "contracts/import_call/models.vy",
    "contracts/import_qualified/import_qualified.vy",
    "contracts/import_qualified/models.vy",
    "contracts/import_sibling/import_sibling.vy",
    "contracts/import_sibling/models.vy",
    "contracts/iou/iou.vy",
    "contracts/loop_count/loop_count.vy",
    "contracts/loop_give/loop_give.vy",
    "contracts/loop_many/loop_many.vy",
    "contracts/loop_pure/loop_pure.vy",
    "contracts/loop_verify/loop_verify.vy",
]
COUNTS = ["inputs", "ok", "rejected", "crash", "skipped"]


def run(capsys, reports, *argv):
    """main(["run", *argv, "--reports", reports]): status, stdout lines, run folder, report.json."""
    status = main(["run", *argv, "--reports", str(reports)])
    return _result(status, capsys.readouterr().out)


def _result(status, out):
    lines = out.splitlines()
    folder = Path(REPORT_LINE.fullmatch(lines[-1]).group(2))
    return status, lines, folder, json.loads((folder / "report.json").read_text())


def _groups(n):
    return "1 crash group" if n == 1 else f"{n} crash groups"


def crash(doc):
    return [group for group in doc["groups"] if group["kind"] == "crash"]


@pytest.fixture(scope="module")
def counted(tmp_path_factory):
    """One `run --count 1000 --random-seed 1` over contracts/, shared by the read-only tests.

    The first crash is at input 588 (scripts/measure_test_counts.py measures it again).
    """
    reports = tmp_path_factory.mktemp("reports")
    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(out):
        patch.chdir(PROJECT)
        status = main(["run", "--count", "1000", "--random-seed", "1", "--reports", str(reports)])
    result = _result(status, out.getvalue())
    assert result[3]["groups"], "1000 inputs should crash forge at least once"
    return result


def test_report_json_has_every_field_with_its_type(counted):
    status, lines, folder, doc = counted

    assert set(doc) == {"schema", "run", "totals", "timeline", "damlc", "compare", "groups"}
    assert doc["schema"] == 1
    assert doc["damlc"] is None, "a run without --damlc has no damlc step"
    assert doc["compare"] is None, "a run without --compare has no compare step"
    run = doc["run"]
    assert set(run) == {
        "started", "random_seed", "seconds", "count", "seeds", "forge_version", "interrupted"
    }  # fmt: skip
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", run["started"])
    assert (run["random_seed"], run["seconds"], run["count"]) == (1, None, 1000)
    assert run["seeds"] == SEEDS
    assert run["forge_version"] == forge.__version__
    assert run["interrupted"] is False
    assert set(doc["totals"]) == set(COUNTS)
    assert all(type(value) is int for value in doc["totals"].values())
    for tick in doc["timeline"]:
        assert set(tick) == {"second", *COUNTS}
        assert all(type(value) is int for value in tick.values())
    assert {group["kind"] for group in doc["groups"]} <= {"crash", "bad_loop"}
    for group in crash(doc):
        assert set(group) == {
            "id", "kind", "exception", "where", "stage", "message", "count", "first_seen",
            "seed", "input", "input_file", "shrunk", "shrunk_file",
        }  # fmt: skip
        assert re.fullmatch(r"\w+", group["exception"])
        assert group["where"] is None or re.fullmatch(r"forge/[\w/]+\.py:\d+", group["where"])
        assert group["stage"] in {stage.value for stage in Stage}
        assert type(group["message"]) is str
        assert type(group["count"]) is int and group["count"] >= 1
        assert set(group["first_seen"]) == {"second", "input"}
        assert type(group["first_seen"]["input"]) is int
        assert type(group["first_seen"]["second"]) in (int, float)
        assert group["seed"] in SEEDS
        assert group["input_file"] == f"groups/{group['id']}/{Path(group['seed']).name}"
        assert type(group["shrunk"]) is str
        assert group["shrunk_file"] == f"groups/{group['id']}/shrunk/{Path(group['seed']).name}"


def test_group_counts_add_up_to_the_printed_crash_count(counted):
    status, (start, final, loops_line, report_line), folder, doc = counted

    assert start == "random seed 1, 15 seeds, 1000 inputs"
    printed = dict(zip(COUNTS, map(int, FINAL_LINE.fullmatch(final).groups()[1:])))
    assert printed == doc["totals"]
    assert sum(group["count"] for group in crash(doc)) == printed["crash"]
    assert status == 1
    loops = [group for group in doc["groups"] if group["kind"] == "bad_loop"]
    inputs = sum(group["count"] for group in loops)
    assert loops_line == (
        f"loops: {inputs} input{'' if inputs == 1 else 's'} with loop findings, "
        f"{len(loops)} loop group{'' if len(loops) == 1 else 's'}"
    )
    assert report_line == f"{_groups(len(crash(doc)))}, report in {folder}"


def test_each_saved_input_crashes_again_in_its_group(counted, capsys):
    _, _, folder, doc = counted

    for group in crash(doc):
        path = str(folder / group["input_file"])
        assert main(["check", path]) == 1
        [line] = capsys.readouterr().out.splitlines()
        assert line.startswith(f"CRASH    {group['stage']:<7}{path}  {group['exception']}"), line
        if group["where"] is not None:
            assert line.endswith(f" at {group['where']}"), line


def test_each_shrunk_input_crashes_again_in_its_group(counted, capsys):
    _, _, folder, doc = counted

    for group in crash(doc):
        path = str(folder / group["shrunk_file"])
        assert main(["check", path]) == 1
        [line] = capsys.readouterr().out.splitlines()
        assert line.startswith(f"CRASH    {group['stage']:<7}{path}  {group['exception']}"), line
        if group["where"] is not None:
            assert line.endswith(f" at {group['where']}"), line


def test_each_shrunk_input_is_shorter_and_made_of_its_inputs_lines(counted):
    _, _, folder, doc = counted

    for group in crash(doc):
        full = group["input"].splitlines(keepends=True)
        small = group["shrunk"].splitlines(keepends=True)
        # The shrinker never returns an empty text, so a 1-line input cannot get shorter.
        assert len(full) > 1, group["id"]
        assert len(small) < len(full), group["id"]
        rest = iter(full)
        assert all(line in rest for line in small), f"{group['id']}: not a subsequence"
        assert (folder / group["shrunk_file"]).read_text() == group["shrunk"]


def test_each_saved_input_is_the_input_its_random_seed_and_number_make(counted):
    _, _, folder, doc = counted
    texts = [(PROJECT / seed).read_text() for seed in doc["run"]["seeds"]]

    for group in doc["groups"]:
        number = group["first_seen"]["input"]
        made = next(itertools.islice(input_sequence(texts, 1), number - 1, None))
        assert (made.number, SEEDS[made.seed]) == (number, group["seed"])
        assert group["input"] == made.text
        saved = folder / group["input_file"]
        assert saved.read_text() == made.text
        seed_yaml = (PROJECT / group["seed"]).parent / "daml.yaml"
        assert (saved.parent / "daml.yaml").read_bytes() == seed_yaml.read_bytes()


def test_group_ids_follow_the_first_input_and_the_timeline_ends_at_the_totals(counted):
    _, _, folder, doc = counted

    # Loop groups (checks L1 to L4) and import groups (I1 to I4) are numbered apart.
    series_of = [("crash", "", "g"), ("bad_loop", "L", "l"), ("bad_loop", "I", "i")]
    for kind, family, series in series_of:
        groups = [
            g for g in doc["groups"] if g["kind"] == kind and g.get("check", "").startswith(family)
        ]
        assert [g["id"] for g in groups] == [f"{series}{n:02d}" for n in range(1, len(groups) + 1)]
        firsts = [g["first_seen"]["input"] for g in groups]
        assert firsts == sorted(firsts)
        assert len(set(firsts)) == len(firsts)
    assert sorted(path.name for path in (folder / "groups").iterdir()) == sorted(
        g["id"] for g in doc["groups"]
    )
    assert [tick["second"] for tick in doc["timeline"]] == list(
        range(1, len(doc["timeline"]) + 1)
    )
    assert {key: doc["timeline"][-1][key] for key in COUNTS} == doc["totals"]


def test_report_md_lists_every_group(counted):
    _, _, folder, doc = counted
    md = (folder / "report.md").read_text().splitlines()

    assert md[0] == f"# damlforge-fuzz run {doc['run']['started']}"
    assert f"## {_groups(len(crash(doc)))}" in md
    for group in crash(doc):
        [row] = [line for line in md if line.startswith(f"| {group['id']} |")]
        name = Path(group["input_file"]).name
        assert row.startswith(f"| {group['id']} | {group['count']} | {group['exception']}")
        shrunk = f"{len(group['shrunk'].splitlines())} of {len(group['input'].splitlines())} lines"
        assert row.endswith(
            f" | [{name}]({group['input_file']}) | [{shrunk}]({group['shrunk_file']}) |"
        ), row


def test_report_md_explains_exactly_the_stages_of_its_groups_in_pipeline_order(counted):
    _, _, folder, doc = counted
    md = (folder / "report.md").read_text()

    present = {group["stage"] for group in crash(doc)}
    expected = [f"- `{stage}`: {STAGE_TEXT[stage]}" for stage in Stage if stage in present]
    section = md.split("\n## Stages\n\n", 1)[1].split("\n\n", 1)[0]
    assert section.splitlines() == expected


def test_report_md_shows_each_shrunk_input_in_a_code_block(counted):
    _, _, folder, doc = counted
    md = (folder / "report.md").read_text()

    shrunk_inputs = md.split("\n## Shrunk inputs\n", 1)[1]
    for group in crash(doc):
        assert f"```python\n{group['shrunk']}```\n" in shrunk_inputs, group["id"]


def test_two_counted_runs_with_one_random_seed_write_the_same_report(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(PROJECT)

    def stable(doc):
        del doc["run"]["started"], doc["timeline"]
        for group in doc["groups"]:
            del group["first_seen"]["second"]
        return doc

    first = run(capsys, tmp_path, "contracts/iou", "--count", "300", "--random-seed", "2")
    second = run(capsys, tmp_path, "contracts/iou", "--count", "300", "--random-seed", "2")
    assert first[2] != second[2]
    assert stable(first[3]) == stable(second[3])


def test_the_run_folder_is_named_after_the_start_and_never_reused(tmp_path, monkeypatch, capsys):
    start = datetime.datetime(2026, 10, 19, 13, 50, 0, tzinfo=datetime.UTC)
    monkeypatch.setattr("damlforge_fuzz.report._now", lambda: start)
    monkeypatch.chdir(PROJECT)

    folders = [
        run(capsys, tmp_path, "contracts/iou", "--count", "1", "--random-seed", "1")[2]
        for _ in range(3)
    ]
    assert folders == [
        tmp_path / "2026-10-19T13-50-00Z",
        tmp_path / "2026-10-19T13-50-00Z-2",
        tmp_path / "2026-10-19T13-50-00Z-3",
    ]
    doc = json.loads((folders[2] / "report.json").read_text())
    assert doc["run"]["started"] == "2026-10-19T13:50:00Z"


@pytest.mark.parametrize(
    ("outcome", "status", "last_line"),
    [
        (Ok("", "Iou"), 0, "0 crash groups, report in {}"),
        (Crash(Stage.LOWER, "KeyError", "'x'", ForgeLine("forge/x.py", 1)), 1,
         "1 crash group, report in {}"),
    ],
    ids=["no-crash", "one-key"],
)  # fmt: skip
def test_the_last_line_counts_the_crash_groups(
    outcome, status, last_line, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr("damlforge_fuzz.runner.compile_and_sort", lambda text, seed: outcome)
    monkeypatch.chdir(PROJECT)

    result_status, lines, folder, doc = run(
        capsys, tmp_path, "contracts/iou", "--count", "50", "--random-seed", "1"
    )
    assert result_status == status
    assert lines[-1] == last_line.format(folder)
    assert len(doc["groups"]) == status


def test_a_reports_path_that_is_a_file_returns_2_and_prints_nothing(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "taken").write_text("")
    monkeypatch.chdir(PROJECT)

    assert main(["run", "--count", "1", "--reports", str(tmp_path / "taken")]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert "taken" in err


def test_ctrl_c_writes_the_report_for_the_inputs_so_far(tmp_path, monkeypatch, capsys):
    # The first crash is at compile call 423 (scripts/measure_test_counts.py).
    calls = itertools.count(1)

    def interrupted_at_call_430(text, seed):
        if next(calls) == 430:
            raise KeyboardInterrupt
        return compile_and_sort(text, seed)

    monkeypatch.setattr("damlforge_fuzz.runner.compile_and_sort", interrupted_at_call_430)
    monkeypatch.chdir(PROJECT)

    status, (_, final, _, _), folder, doc = run(
        capsys, tmp_path, "--count", "1000", "--random-seed", "1"
    )
    assert status == 130
    assert doc["run"]["interrupted"] is True
    printed = dict(zip(COUNTS, map(int, FINAL_LINE.fullmatch(final).groups()[1:])))
    assert printed == doc["totals"]
    assert printed["inputs"] - printed["skipped"] == 429
    assert sum(group["count"] for group in crash(doc)) == printed["crash"]
    assert "- Stopped early by Ctrl-C. The report covers the inputs so far." in (
        (folder / "report.md").read_text().splitlines()
    )
    assert crash(doc), "429 inputs should crash forge at least once"
    for group in crash(doc):
        assert (folder / group["shrunk_file"]).read_text() == group["shrunk"]


def test_ctrl_c_while_shrinking_keeps_the_groups_shrunk_so_far(tmp_path, monkeypatch, capsys):
    calls = itertools.count(1)

    def interrupted_in_group_2(text, seed, keep):
        if next(calls) == 2:
            raise KeyboardInterrupt
        return shrink(text, seed, keep)

    monkeypatch.setattr("damlforge_fuzz.report.shrink", interrupted_in_group_2)
    monkeypatch.chdir(PROJECT)

    # The third crash group starts at input 1498 (scripts/measure_test_counts.py).
    status, lines, folder, doc = run(capsys, tmp_path, "--count", "2000", "--random-seed", "1")
    assert status == 130
    assert len(lines) == 4
    assert doc["run"]["interrupted"] is True
    first, *rest = crash(doc)
    assert rest, "2000 inputs should crash forge in at least three groups"
    assert (folder / first["shrunk_file"]).read_text() == first["shrunk"]
    assert [(g["shrunk"], g["shrunk_file"]) for g in rest] == [(None, None)] * len(rest)
    # A shrunk folder also holds the seed's sibling .vy files, so count folders, not files.
    assert sorted(p.parent.name for p in folder.glob("groups/*/shrunk")) == [first["id"]]
    md = (folder / "report.md").read_text().splitlines()
    assert all(
        line.endswith(" | not shrunk |") for line in md if line.startswith(("| g02 |", "| g03 |"))
    )


def test_ctrl_c_in_a_loop_group_leaves_it_not_shrunk_and_a_second_shrink_finishes_it(
    tmp_path, monkeypatch
):
    # The second check group starts at input 16460 (scripts/measure_test_counts.py).
    seeds = [Seed.load(path) for path in SEED_FILES if "loop_" in path.name]
    report = Report.open(seeds, 1, Count(17000), tmp_path)
    for tried in fuzz(seeds, 1, Count(17000)):
        report.add(tried)
    calls = itertools.count(1)

    def interrupted_in_loop_group_2(text, seed, keep):
        if next(calls) == len(report.groups) + 2:
            raise KeyboardInterrupt
        return shrink(text, seed, keep)

    monkeypatch.setattr("damlforge_fuzz.report.shrink", interrupted_in_loop_group_2)
    with pytest.raises(KeyboardInterrupt):
        report.shrink()
    monkeypatch.undo()

    first, second, *rest = report.loop_groups()
    assert first.shrunk is not None and first.shrunk_daml is not None
    assert (second.shrunk, second.shrunk_file, second.shrunk_daml, second.shrunk_daml_file) == (
        None, None, None, None
    )  # fmt: skip
    report.write()
    assert sorted(p.name for p in (report.folder / "groups" / first.id / "shrunk").iterdir()) == [
        Path(first.daml_file).name, Path(first.input_file).name
    ]  # fmt: skip
    assert not (report.folder / "groups" / second.id / "shrunk").exists()
    [row] = [line for line in report.markdown().splitlines() if line.startswith(f"| {second.id} |")]
    assert row.endswith(" | not shrunk |"), row

    report.shrink()
    again, second, *rest = report.loop_groups()
    assert (again.shrunk, again.shrunk_daml) == (first.shrunk, first.shrunk_daml)
    for group in [second, *rest]:
        assert len(group.shrunk.splitlines()) < len(group.input.splitlines()), group.id
        assert group.shrunk_file == f"groups/{group.id}/shrunk/{Path(group.seed).name}"
        outcome = compile_and_sort(group.shrunk, Seed.load(Path(group.seed)))
        assert (outcome.daml, outcome.loop_key) == (group.shrunk_daml, group.check), group.id


def test_the_timeline_has_one_tick_per_second(tmp_path, monkeypatch, capsys):
    def slow(text, seed):
        time.sleep(0.25)
        return Ok("", seed.module_name)

    monkeypatch.setattr("damlforge_fuzz.runner.compile_and_sort", slow)
    monkeypatch.chdir(PROJECT)

    _, _, _, doc = run(capsys, tmp_path, "contracts/iou", "--count", "10", "--random-seed", "1")
    timeline = doc["timeline"]
    assert len(timeline) >= 2
    assert [tick["second"] for tick in timeline] == list(range(1, len(timeline) + 1))
    for before, after in itertools.pairwise(timeline):
        assert all(before[key] <= after[key] for key in COUNTS)
    assert {key: timeline[-1][key] for key in COUNTS} == doc["totals"]


def test_writing_again_leaves_no_stale_group_folder(tmp_path):
    # The first group on iou alone starts at input 604 (scripts/measure_test_counts.py).
    seed = Seed.load(CONTRACTS / "iou" / "iou.vy")
    report = Report.open([seed], 1, Count(1000), tmp_path)
    for tried in fuzz([seed], 1, Count(1000)):
        report.add(tried)
    report.write()
    (report.folder / "groups" / "g99").mkdir(parents=True)

    report.write()
    assert sorted(path.name for path in (report.folder / "groups").iterdir()) == [
        group.id for group in [*report.groups.values(), *report.loop_groups()]
    ]


def test_report_md_fences_a_shrunk_input_longer_than_its_backticks(tmp_path):
    seed = Seed.load(CONTRACTS / "iou" / "iou.vy")
    report = Report.open([seed], 1, Count(1), tmp_path)
    key = Crash(Stage.LOWER, "KeyError", "'x'", ForgeLine("forge/x.py", 1)).key
    report.groups[key] = Group(
        "g01", "crash", "KeyError", "forge/x.py:1", Stage.LOWER, "'x'", 1, FirstSeen(0.0, 1),
        "contracts/iou/iou.vy", "a\nb = '```'\n", "groups/g01/iou.vy",
        shrunk="b = '```'\n", shrunk_file="groups/g01/shrunk/iou.vy",
    )  # fmt: skip

    md = report.markdown()
    assert "\n````python\nb = '```'\n````\n" in md
    assert "| [1 of 2 lines](groups/g01/shrunk/iou.vy) |" in md
