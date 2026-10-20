"""The loop check, on saved pairs of a .vy text and forge's Daml for it, and on live forge.

The pairs are in tests/loops/, with the checks each one must give in
EXPECTED.tsv. The tests on the pairs do not run forge, so a forge fix does not
change them. The live tests at the end show when forge writes other Daml today.
"""

import re
from pathlib import Path

import pytest
from conftest import PROJECT, SEED_FILES

from damlforge_fuzz import (
    FORGE_VERSION,
    LOOP_CHECK_TEXT,
    LoopBug,
    LoopCheck,
    Ok,
    Seed,
    compile_and_sort,
    find_loop_bugs,
)

LOOPS = Path(__file__).parent / "loops"
EXPECTED = {
    name: expected
    for name, expected, _ in (
        line.split("\t")
        for line in (LOOPS / "EXPECTED.tsv").read_text().splitlines()
        if not line.startswith("#")
    )
}


FIXTURE_FORGE = re.search(r"DamlForge v([\d.]+)", (LOOPS / "EXPECTED.tsv").read_text()).group(1)
"""The forge version that wrote the Daml in tests/loops/."""


def pair(name):
    return (LOOPS / f"{name}.vy").read_text(), (LOOPS / f"{name}.daml").read_text()


def version(text):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


@pytest.fixture
def fixture_forge():
    """Skip a test of forge's own output on a forge older than the one that wrote tests/loops/.

    An older forge, such as v0.0.7, writes other Daml and has other loop bugs.
    A newer forge must still write the saved Daml, so a change in forge fails
    these tests and shows which saved Daml to write again.
    """
    if version(FORGE_VERSION) < version(FIXTURE_FORGE):
        pytest.skip(
            f"tests/loops/ holds the Daml of DamlForge {FIXTURE_FORGE}, not {FORGE_VERSION}"
        )


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


def test_every_check_has_a_text():
    assert list(LOOP_CHECK_TEXT) == list(LoopCheck)


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda path: path.stem)
def test_every_seed_is_ok_with_no_loop_bug(path):
    seed = Seed.load(path)
    outcome = compile_and_sort(seed.text, seed)
    assert isinstance(outcome, Ok)
    assert (outcome.loop_bugs, outcome.loop_key) == ((), None)


BUG_PROGRAMS = {
    "b17_create_append": "L1",
    "b18_fetch_in_sum": "L1",
    "b19_fetch_in_if_test": "L2 L4",
    "b20_fetch_in_plain_function": "L2 L4",
    "b21_return_in_create_loop": "L3",
}


@pytest.mark.parametrize("name", BUG_PROGRAMS)
def test_each_bug_program_is_ok_with_its_loop_checks(name, fixture_forge):
    seed = Seed.load(PROJECT / "bugs" / "loops" / f"{name}.vy")
    outcome = compile_and_sort(seed.text, seed)
    assert isinstance(outcome, Ok)
    assert " ".join(bug.check for bug in outcome.loop_bugs) == BUG_PROGRAMS[name]
    assert outcome.loop_key == BUG_PROGRAMS[name].split()[0]


@pytest.mark.parametrize("name", EXPECTED)
def test_forge_still_writes_the_saved_daml_and_its_ok_carries_the_loop_bugs(name, fixture_forge):
    seed = Seed.load(LOOPS / f"{name}.vy")
    vy, daml = pair(name)
    assert compile_and_sort(seed.text, seed) == Ok(daml, seed.module_name, find_loop_bugs(vy, daml))
