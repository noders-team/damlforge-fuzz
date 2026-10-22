"""The loop check, on saved pairs of a .vy text and forge's Daml for it, and on live forge.

The pairs are in tests/loops/, with the checks each one must give in
EXPECTED.tsv. The tests on the pairs do not run forge, so a forge fix does not
change them. The live tests show when forge writes other Daml today. The run
tests check relations, as test_report.py does, so they hold on any forge version.
"""

import collections
import contextlib
import io
import json
import re
from pathlib import Path

import pytest
from conftest import PROJECT, SEED_FILES

from damlforge_fuzz import (
    LOOP_CHECK_TEXT,
    DamlcUnavailable,
    DamlSource,
    LoopBug,
    LoopCheck,
    Ok,
    Seed,
    build_daml,
    compile_and_sort,
    find_loop_bugs,
)
from damlforge_fuzz.cli import main

LOOPS = Path(__file__).parent / "loops"
EXPECTED = {
    name: expected
    for name, expected, _ in (
        line.split("\t")
        for line in (LOOPS / "EXPECTED.tsv").read_text().splitlines()
        if not line.startswith("#")
    )
}


def pair(name):
    return (LOOPS / f"{name}.vy").read_text(), (LOOPS / f"{name}.daml").read_text()


@pytest.mark.parametrize("name", EXPECTED)
def test_each_saved_pair_gives_exactly_its_checks(name):
    assert " ".join(bug.check for bug in find_loop_bugs(*pair(name))) == EXPECTED[name]


def test_b21_gives_l3_on_the_line_of_the_choice_that_lost_its_return():
    assert find_loop_bugs(*pair("b21_return_in_create_loop")) == (
        LoopBug(
            LoopCheck.L3,
            14,
            "the return in a loop of choice GiveUntil at Daml line 14 is lost "
            "(1 loop with a return, 0 early-return helpers)",
        ),
    )


def test_b19_gives_l2_and_l4_on_the_fetch_in_the_pure_fold():
    assert find_loop_bugs(*pair("b19_fetch_in_if_test")) == (
        LoopBug(LoopCheck.L2, 22, "fetch at Daml line 22 in the pure foldl of line 20"),
        LoopBug(LoopCheck.L4, 22, "fetch at Daml line 22 is used as a value, not bound with <-"),
    )


@pytest.mark.parametrize("name", ["fp_l3_toplevel_for", "class_level_for", "dead_loop"])
def test_l3_counts_only_a_loop_of_a_function_that_can_run(name):
    # A return in a def inside a module-level loop, a loop in a class body, and
    # a loop after a return: none of them is a lost return.
    assert find_loop_bugs(*pair(name)) == ()


HAS = "    def has(self, ps: list[Party]) -> bool:\n"
CHOICE = "    @choice(controller=owner, consuming=False)\n"
LOST_IN_HAS = (
    LoopBug(
        LoopCheck.L3,
        11,
        "the return in a loop of choice Has at Daml line 11 is lost "
        "(1 loop with a return, 0 early-return helpers)",
    ),
)


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (HAS, ()),
        ("    @ledger_effect\n" + HAS, ()),
        ("    @checked_fetch\n" + CHOICE + HAS, ()),
        ("    @view\n" + CHOICE + HAS, ()),
        ("    @view\n" + CHOICE + HAS.replace("bool", "list[bool]"), LOST_IN_HAS),
        (CHOICE + HAS, LOST_IN_HAS),
    ],
    ids=["undecorated", "ledger_effect", "checked_fetch", "view", "view-list-return", "choice"],
)
def test_l3_reads_a_method_only_when_forge_writes_it_as_a_choice(method, expected):
    # The Daml's choice Has comes from the def `Has`, which has no loop. The method
    # `has` has the same Daml name, so it is choice Has only when forge writes it as a choice.
    vy, daml = pair("method_named_like_choice")
    assert find_loop_bugs(vy.replace(HAS, method), daml) == expected


def test_each_loop_with_a_return_needs_its_own_helper():
    # has_party has _damlforge_loop1. Choice GiveUntil calls no helper.
    assert find_loop_bugs(*pair("two_fns")) == (
        LoopBug(
            LoopCheck.L3,
            22,
            "the return in a loop of choice GiveUntil at Daml line 22 is lost "
            "(1 loop with a return, 0 early-return helpers)",
        ),
    )


def test_an_action_name_that_is_passed_on_is_not_run_but_get_time_always_runs():
    # `owner = create,` passes a value, and `observer [fetch]` names a field.
    assert find_loop_bugs(*pair("value_create")) == ()
    assert find_loop_bugs(*pair("field_named_fetch")) == ()
    # getTime takes no argument, so `(getTime).terms` runs it as a value.
    assert find_loop_bugs(*pair("gettime_value")) == (
        LoopBug(LoopCheck.L4, 40, "getTime at Daml line 40 is used as a value, not bound with <-"),
    )


def test_the_vy_text_is_read_like_forge_reads_it():
    # `for q: Party in ps:` is forge syntax that Python's ast rejects.
    vy, daml = pair("annot_for")
    assert find_loop_bugs(vy, daml) == ()
    assert [bug.check for bug in find_loop_bugs(vy, daml.replace("_damlforge_loop1", "f"))] == [
        LoopCheck.L3
    ]


DEEP_FOR = "def f(xs: list[int]) -> int:\n" + "".join(
    " " * k + "for x in xs:\n" for k in range(1, 130)
)


@pytest.mark.parametrize(
    "vy", ["", "\x00", "def f(:\n", "  x\n y\n", DEEP_FOR, "(" * 1000],
    ids=["empty", "nul", "broken", "bad-indent", "deep", "parens"],
)  # fmt: skip
def test_a_vy_text_that_forge_cannot_compile_gives_no_l3_and_does_not_raise(vy):
    _, daml = pair("b21_return_in_create_loop")
    assert find_loop_bugs(vy, daml) == ()


@pytest.mark.parametrize(
    "daml", ["", "\x00", '"open string', "(" * 1000, "do\n" * 3000, "  fetch\n" * 50],
    ids=["empty", "nul", "open-string", "parens", "do-lines", "indented"],
)  # fmt: skip
def test_a_daml_text_that_forge_cannot_write_does_not_raise(daml):
    vy, _ = pair("b21_return_in_create_loop")
    assert find_loop_bugs(vy, daml) == ()


def test_every_check_has_a_text_and_the_readme_shows_it():
    assert list(LOOP_CHECK_TEXT) == list(LoopCheck)
    readme = (PROJECT / "README.md").read_text()
    table = readme.split("### Loop check", 1)[1].split("\n\n", 3)[2]
    assert table.splitlines()[2:] == [
        f"| `{check}` | {text} |" for check, text in LOOP_CHECK_TEXT.items()
    ]


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda path: path.stem)
def test_every_seed_is_ok_with_no_loop_bug(path):
    seed = Seed.load(path)
    outcome = compile_and_sort(seed.text, seed)
    assert isinstance(outcome, Ok)
    assert (outcome.loop_bugs, outcome.loop_key) == ((), None)


def test_each_loop_seed_has_at_most_one_foldla_loop():
    """forge imports foldlA for the whole module, so a second such loop hides L1 in the other."""
    loops = {}
    for path in SEED_FILES:
        if "loop_" in path.name:
            daml = compile_and_sort(path.read_text(), Seed.load(path)).daml
            loops[path.stem] = len(re.findall(r"^(?!import ).*\bfoldlA\b", daml, re.MULTILINE))
    assert loops == {
        "loop_count": 1, "loop_give": 1, "loop_many": 1, "loop_pure": 0, "loop_verify": 1
    }  # fmt: skip


BUG_PROGRAMS = {
    "b17_create_append": "L1: foldlA at Daml line 20 with no import DA.Action",
    "b18_fetch_in_sum": "L1: foldlA at Daml line 20 with no import DA.Action",
    "b19_fetch_in_if_test": "L2 L4: fetch at Daml line 22 in the pure foldl of line 20",
    "b20_fetch_in_plain_function": "L2 L4: fetch at Daml line 9 in the pure foldl of line 7",
    "b21_return_in_create_loop": "L3: the return in a loop of choice GiveUntil at Daml line 14 "
    "is lost (1 loop with a return, 0 early-return helpers)",
    "b22_return_in_inner_loop": "L3: the return in a loop of function first_positive "
    "at Daml line 3 is lost (2 loops with a return, 0 early-return helpers)",
}
"""Each bug program in bugs/loops/: every check it fails, and its first bug."""

B23 = "OK       emit   bugs/loops/b23_pass_in_loop.vy"
"""b23 loses an assert in a loop, but no loop check finds it. Only --compare shows it."""


@pytest.mark.parametrize("name", BUG_PROGRAMS)
def test_each_bug_program_is_ok_with_its_loop_bugs(name, fixture_forge):
    seed = Seed.load(PROJECT / "bugs" / "loops" / f"{name}.vy")
    outcome = compile_and_sort(seed.text, seed)
    assert isinstance(outcome, Ok)
    checks = " ".join(bug.check for bug in outcome.loop_bugs)
    assert f"{checks}: {outcome.loop_bugs[0].detail}" == BUG_PROGRAMS[name]
    assert outcome.loop_key == checks.split()[0]


@pytest.mark.parametrize("name", EXPECTED)
def test_forge_still_writes_the_saved_daml_and_its_ok_carries_the_loop_bugs(name, fixture_forge):
    seed = Seed.load(LOOPS / f"{name}.vy")
    vy, daml = pair(name)
    assert compile_and_sort(seed.text, seed) == Ok(daml, seed.module_name, find_loop_bugs(vy, daml))


LOOP_SEEDS = [str(path.parent.relative_to(PROJECT)) for path in SEED_FILES if "loop_" in path.name]
REPORT_LINE = re.compile(r"\d+ crash groups?, report in (.+)")


def run(reports, *argv):
    """main(["run", *argv, "--reports", reports]) in PROJECT: status, stdout lines, folder, report.json."""
    out = io.StringIO()
    with pytest.MonkeyPatch.context() as patch, contextlib.redirect_stdout(out):
        patch.chdir(PROJECT)
        status = main(["run", *argv, "--reports", str(reports)])
    lines = out.getvalue().splitlines()
    folder = PROJECT / REPORT_LINE.fullmatch(lines[-1]).group(1)
    return status, lines, folder, json.loads((folder / "report.json").read_text())


def loop_groups(doc):
    return [group for group in doc["groups"] if group["kind"] == "bad_loop"]


def label(group):
    return "BAD_IMP" if group["check"].startswith("I") else "BAD_LOOP"


@pytest.fixture(scope="module")
def loop_run(tmp_path_factory):
    """`run contracts/loop_* --count 20000 --random-seed 1`, with the current change rules.

    DamlForge 0.0.12 triggers the loop check far less often than earlier versions, so
    this needs many more inputs than before to still catch one loop group.
    """
    return run(
        tmp_path_factory.mktemp("reports"), *LOOP_SEEDS, "--count", "20000", "--random-seed", "1"
    )


@pytest.fixture(scope="module")
def loop_run_damlc(dpm, tmp_path_factory):
    """The same run with --damlc."""
    reports = tmp_path_factory.mktemp("reports")
    return run(reports, *LOOP_SEEDS, "--count", "20000", "--random-seed", "1", "--damlc")


def test_a_run_on_the_loop_seeds_makes_one_loop_group_per_first_check(loop_run):
    _, _, folder, doc = loop_run
    loops = loop_groups(doc)

    assert any(g["check"].startswith("L") for g in loops), "20000 inputs should give a loop bug"
    for family, series in [("L", "l"), ("I", "i")]:
        own = [g for g in loops if g["check"].startswith(family)]
        assert [g["id"] for g in own] == [f"{series}{n:02d}" for n in range(1, len(own) + 1)]
        firsts = [g["first_seen"]["input"] for g in own]
        assert firsts == sorted(firsts)
    assert len({g["check"] for g in loops}) == len(loops)
    for group in loops:
        assert set(group) == {
            "id", "kind", "check", "checks", "message", "daml_line", "damlc", "damlc_error",
            "count", "first_seen", "seed", "input", "input_file", "daml", "daml_file",
            "shrunk", "shrunk_file", "shrunk_daml", "shrunk_daml_file",
        }  # fmt: skip
        assert group["checks"][0] == group["check"]
        assert group["checks"] == sorted(group["checks"])
        assert set(group["checks"]) <= {check.value for check in LoopCheck}
        assert (group["damlc"], group["damlc_error"]) == (None, None)
        assert type(group["count"]) is int and group["count"] >= 1
        assert group["input_file"] == f"groups/{group['id']}/{Path(group['seed']).name}"
        module = re.fullmatch(r"module (\w+) where", group["daml"].splitlines()[0]).group(1)
        assert group["daml_file"] == f"groups/{group['id']}/{module}.daml"
        assert (folder / group["input_file"]).read_text() == group["input"]
        assert (folder / group["daml_file"]).read_text() == group["daml"]
        seed_yaml = (PROJECT / group["seed"]).parent / "daml.yaml"
        assert (
            folder / "groups" / group["id"] / "daml.yaml"
        ).read_bytes() == seed_yaml.read_bytes()
        shrunk = f"groups/{group['id']}/shrunk"
        assert group["shrunk_file"] == f"{shrunk}/{Path(group['seed']).name}"
        assert group["shrunk_daml_file"] == f"{shrunk}/{module}.daml"
        assert (folder / group["shrunk_file"]).read_text() == group["shrunk"]
        assert (folder / group["shrunk_daml_file"]).read_text() == group["shrunk_daml"]


def test_each_shrunk_loop_input_is_shorter_and_made_of_its_inputs_lines(loop_run):
    _, _, _, doc = loop_run

    for group in loop_groups(doc):
        full = group["input"].splitlines(keepends=True)
        small = group["shrunk"].splitlines(keepends=True)
        assert len(small) < len(full), group["id"]
        rest = iter(full)
        assert all(line in rest for line in small), f"{group['id']}: not a subsequence"


def test_check_shows_each_shrunk_loop_input_in_its_group(loop_run, capsys):
    _, _, folder, doc = loop_run

    for group in loop_groups(doc):
        path = folder / group["shrunk_file"]
        seed = Seed.load(path)
        outcome = compile_and_sort(seed.text, seed)
        assert isinstance(outcome, Ok) and outcome.daml == group["shrunk_daml"], group["id"]
        bugs = outcome.loop_bugs
        assert bugs[0].check == group["check"], group["id"]
        assert main(["check", str(path)]) == 1
        assert capsys.readouterr().out == (
            f"{bugs[0].label:<9}emit   {path}  {' '.join(bug.check for bug in bugs)}: {bugs[0].detail}\n"
        )


def test_each_saved_loop_input_gives_its_group_again(loop_run):
    _, _, folder, doc = loop_run

    for group in loop_groups(doc):
        seed = Seed.load(folder / group["input_file"])
        outcome = compile_and_sort(seed.text, seed)
        assert isinstance(outcome, Ok) and outcome.daml == group["daml"], group["id"]
        first = outcome.loop_bugs[0]
        assert [bug.check for bug in outcome.loop_bugs] == group["checks"], group["id"]
        assert (first.detail, first.daml_line) == (group["message"], group["daml_line"])


def test_report_md_explains_the_loop_check_and_lists_every_loop_group(loop_run):
    _, _, folder, doc = loop_run
    md = (folder / "report.md").read_text().splitlines()
    loops = loop_groups(doc)

    assert f"## {len(loops)} loop group{'' if len(loops) == 1 else 's'}" in md
    for check in {check for group in loops for check in group["checks"]}:
        assert f"- `{check}`: {LOOP_CHECK_TEXT[check]}" in md
    for group in loops:
        [row] = [line for line in md if line.startswith(f"| {group['id']} |")]
        name, daml = Path(group["input_file"]).name, Path(group["daml_file"]).name
        lines = f"{len(group['shrunk'].splitlines())} of {len(group['input'].splitlines())} lines"
        assert row == (
            f"| {group['id']} | {group['check']} | {' '.join(group['checks'])} | "
            f"{group['count']} | - | {group['seed']} | input {group['first_seen']['input']}, "
            f"{group['first_seen']['second']} s | [{name}]({group['input_file']}) | "
            f"[{daml}]({group['daml_file']}) | [{lines}]({group['shrunk_file']}) |"
        )
    section = "\n".join(md).split("\n## Shrunk loop inputs\n", 1)[1]
    for group in loops:
        assert (
            f"\n### {group['id']}: {group['check']}\n\n```python\n{group['shrunk']}```\n\n"
            f"```daml\n{group['shrunk_daml'].rstrip()}\n```\n"
        ) in section + "\n", group["id"]


def test_with_damlc_each_loop_group_has_the_verdict_a_fresh_build_gives(loop_run_damlc):
    _, _, _, doc = loop_run_damlc
    loops = loop_groups(doc)
    sources = {
        group["id"]: DamlSource(
            group["daml"],
            Path(group["daml_file"]).stem,
            (PROJECT / group["seed"]).parent / "daml.yaml",
        )
        for group in loops
    }

    verdicts = dict(build_daml(set(sources.values())))
    for group in loops:
        error = verdicts[sources[group["id"]]]
        expected = ("builds", None) if error is None else ("rejects", error.message)
        assert (group["damlc"], group["damlc_error"]) == expected, group["id"]
    assert len({(g["check"], g["damlc"]) for g in loops}) == len(loops)


def test_with_damlc_report_md_shows_each_loop_groups_verdict(loop_run_damlc):
    _, _, folder, doc = loop_run_damlc
    md = (folder / "report.md").read_text().splitlines()
    cells = []
    for group in loop_groups(doc):
        [row] = [line for line in md if line.startswith(f"| {group['id']} |")]
        [bug] = [line for line in md if line.startswith(f"- {group['id']}, ")]
        damlc = "" if group["damlc"] == "builds" else f". damlc: `{group['damlc_error']}`"
        cells.append(row.split(" | ")[4])
        assert cells[-1] == group["damlc"], group["id"]
        assert bug == (
            f"- {group['id']}, {Path(group['daml_file']).name} line {group['daml_line']}: "
            f"`{group['message']}`{damlc}"
        )
        assert f"### {group['id']}: {group['check']}, damlc {group['damlc']}" in md
    assert set(cells) == {"builds", "rejects"}


def test_check_damlc_shows_each_shrunk_loop_input_with_its_groups_verdict(loop_run_damlc, capsys):
    _, _, folder, doc = loop_run_damlc

    for group in loop_groups(doc):
        path = folder / group["shrunk_file"]
        assert main(["check", "--damlc", str(path)]) == 1
        out = capsys.readouterr().out
        assert out.startswith(f"{label(group):<9}emit   {path}  {group['check']}"), out
        if group["damlc"] == "builds":
            assert out.endswith("; damlc builds\n"), out
        else:
            assert "; damlc rejects: " in out, out


def test_dpm_failing_while_a_loop_group_shrinks_returns_2_after_the_report(
    dpm, tmp_path, monkeypatch, capsys
):
    def dpm_fails(sources):
        raise DamlcUnavailable("dpm build exited with 1")

    monkeypatch.setattr("damlforge_fuzz.shrinker.build_daml", dpm_fails)

    status, lines, folder, doc = run(
        tmp_path, *LOOP_SEEDS, "--count", "150", "--random-seed", "1", "--damlc"
    )
    assert status == 2
    assert capsys.readouterr().err == "damlforge-fuzz run: damlc: dpm build exited with 1\n"
    assert len(lines) == 5
    crash = [group for group in doc["groups"] if group["kind"] == "crash"]
    assert crash and all(group["shrunk"] is not None for group in crash)
    loops = loop_groups(doc)
    assert loops and all(group["damlc"] is not None for group in loops)
    assert [group["shrunk"] for group in loops] == [None] * len(loops)
    assert not list(folder.glob("groups/l*/shrunk"))


def test_with_damlc_the_loop_groups_split_the_same_inputs_by_verdict(loop_run, loop_run_damlc):
    plain, damlc = loop_groups(loop_run[3]), loop_groups(loop_run_damlc[3])

    def per_check(groups):
        counts = collections.Counter()
        for group in groups:
            counts[group["check"]] += group["count"]
        return counts

    assert per_check(damlc) == per_check(plain)
    for group in plain:
        first = min(
            (g for g in damlc if g["check"] == group["check"]),
            key=lambda g: g["first_seen"]["input"],
        )
        assert first["first_seen"]["input"] == group["first_seen"]["input"]


def test_groups_of_each_kind_from_one_seed_have_their_own_folder(loop_run_damlc):
    _, _, folder, doc = loop_run_damlc
    kinds = collections.defaultdict(set)
    for group in doc["groups"]:
        kinds[group["seed"]].add(group["kind"])
        assert group["input_file"] == f"groups/{group['id']}/{Path(group['seed']).name}"
        assert (folder / group["input_file"]).read_text() == group["input"]

    assert any(found == {"crash", "bad_daml", "bad_loop"} for found in kinds.values()), kinds
    files = [group["input_file"] for group in doc["groups"]]
    assert len(set(files)) == len(files)


def loops_line(groups):
    inputs = sum(group["count"] for group in groups)
    return (
        f"loops: {inputs} input{'' if inputs == 1 else 's'} with loop findings, "
        f"{len(groups)} loop group{'' if len(groups) == 1 else 's'}"
    )


def test_the_loops_line_comes_before_the_last_line_and_counts_the_loop_groups(
    loop_run, loop_run_damlc
):
    status, lines, _, doc = loop_run
    assert len(lines) == 4 and lines[2] == loops_line(loop_groups(doc))
    assert status == 1

    _, lines, _, doc = loop_run_damlc
    builds = sum(group["damlc"] == "builds" for group in loop_groups(doc))
    assert len(lines) == 5 and lines[2].startswith("damlc: ")
    assert lines[3] == (
        f"{loops_line(loop_groups(doc))}, {builds} build{'s' if builds == 1 else ''} with damlc"
    )


def test_a_run_whose_only_finding_is_a_loop_bug_returns_1(tmp_path, monkeypatch):
    bug = LoopBug(LoopCheck.L4, 5, "fetch at Daml line 5 is used as a value, not bound with <-")
    monkeypatch.setattr(
        "damlforge_fuzz.runner.compile_and_sort", lambda text, seed: Ok("", "Iou", (bug,))
    )

    status, lines, _, doc = run(tmp_path, "contracts/iou", "--count", "50", "--random-seed", "1")
    ok = int(re.search(r", (\d+) OK,", lines[1]).group(1))
    assert ", 0 crash, " in lines[1]
    assert lines[2] == f"loops: {ok} inputs with loop findings, 1 loop group"
    assert [(g["id"], g["check"], g["count"]) for g in doc["groups"]] == [("l01", "L4", ok)]
    assert status == 1


def test_check_prints_bad_loop_for_each_bug_program_and_returns_1(
    fixture_forge, monkeypatch, capsys
):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "bugs/loops"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        f"BAD_LOOP emit   bugs/loops/{name}.vy  {bugs}" for name, bugs in BUG_PROGRAMS.items()
    ] + [B23]


def test_check_damlc_ends_each_bad_loop_line_with_damlcs_verdict(
    dpm, fixture_forge, monkeypatch, capsys
):
    monkeypatch.chdir(PROJECT)
    no_foldl_a = "damlc rejects: Variable not in scope: foldlA"
    no_field = (
        "damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ "
        "on value of type ‘Update"
    )
    verdicts = [no_foldl_a, no_foldl_a, no_field, no_field, "damlc builds", "damlc builds"]

    assert main(["check", "--damlc", "bugs/loops"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        f"BAD_LOOP emit   bugs/loops/{name}.vy  {bugs}; {verdict}"
        for (name, bugs), verdict in zip(BUG_PROGRAMS.items(), verdicts, strict=True)
    ] + [B23]


def test_a_seed_with_a_loop_bug_stops_the_run_before_input_1(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)
    reports = tmp_path / "reports"

    status = main(
        ["run", "bugs/loops/b17_create_append.vy", "--count", "10", "--reports", str(reports)]
    )
    out, err = capsys.readouterr()
    assert (status, out) == (2, "")
    assert err == (
        "damlforge-fuzz run: the loop check finds a bug in seed bugs/loops/b17_create_append.vy: "
        "L1: foldlA at Daml line 20 with no import DA.Action\n"
    )
    assert not reports.exists()


def test_check_shows_each_saved_loop_group_again(loop_run, capsys):
    _, _, folder, doc = loop_run

    for group in loop_groups(doc):
        path = folder / group["input_file"]
        assert main(["check", str(path)]) == 1
        assert capsys.readouterr().out == (
            f"{label(group):<9}emit   {path}  {' '.join(group['checks'])}: {group['message']}\n"
        )


def test_check_damlc_shows_each_saved_loop_group_again_with_its_verdict(loop_run_damlc, capsys):
    _, _, folder, doc = loop_run_damlc

    for group in loop_groups(doc):
        path = folder / group["input_file"]
        verdict = (
            "damlc builds"
            if group["damlc"] == "builds"
            else f"damlc rejects: {group['damlc_error']}"
        )
        assert main(["check", "--damlc", str(path)]) == 1
        assert capsys.readouterr().out == (
            f"{label(group):<9}emit   {path}  {' '.join(group['checks'])}: {group['message']}; {verdict}\n"
        )
