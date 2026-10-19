"""`damlforge-fuzz run`, driven through cli.main, and the fuzz loop behind it."""

import re

from conftest import CONTRACTS, PROJECT

from damlforge_fuzz import Count, Seed, fuzz
from damlforge_fuzz.cli import main

FINAL_LINE = re.compile(
    r"random seed (\d+): (\d+) inputs, (\d+) OK, (\d+) rejected, (\d+) crash, (\d+) skipped"
)


def run(capsys, *argv):
    """main(["run", *argv]) and its stdout lines."""
    status = main(["run", *argv])
    return status, capsys.readouterr().out.splitlines()


def test_a_counted_run_prints_the_random_seed_and_counts_that_add_up(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    status, (start, final) = run(capsys, "contracts/iou", "--count", "300", "--random-seed", "1")
    assert start == "random seed 1, 1 seed, 300 inputs"
    seed, inputs, ok, rejected, crash, skipped = map(int, FINAL_LINE.fullmatch(final).groups())
    assert (seed, inputs) == (1, 300)
    assert ok + rejected + crash + skipped == 300
    assert status == (1 if crash else 0)


def test_two_runs_with_the_same_random_seed_print_the_same_lines(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    first = run(capsys, "--count", "500", "--random-seed", "1")
    second = run(capsys, "--count", "500", "--random-seed", "1")
    assert first == second


def test_a_run_without_random_seed_prints_one_that_repeats_it(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    status, lines = run(capsys, "contracts/iou", "--count", "300")
    random_seed = re.fullmatch(r"random seed (\d+), 1 seed, 300 inputs", lines[0]).group(1)
    assert run(capsys, "contracts/iou", "--count", "300", "--random-seed", random_seed) == (
        status,
        [f"random seed {random_seed}, 1 seed, 300 inputs", lines[1]],
    )


def test_a_timed_run_repeats_when_its_input_count_is_passed_as_count(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    status, (start, final) = run(capsys, "contracts/iou", "--seconds", "1", "--random-seed", "3")
    assert start == "random seed 3, 1 seed, 1 second"
    inputs = FINAL_LINE.fullmatch(final).group(2)
    assert int(inputs) > 0
    assert run(capsys, "contracts/iou", "--count", inputs, "--random-seed", "3") == (
        status,
        [f"random seed 3, 1 seed, {inputs} inputs", final],
    )


def test_no_seed_folder_means_every_seed_in_contracts(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    _, lines = run(capsys, "--count", "1", "--random-seed", "1")
    assert lines[0] == "random seed 1, 4 seeds, 1 input"


def test_a_run_on_iou_compiles_only_changed_copies_of_iou():
    iou = Seed.load(CONTRACTS / "iou" / "iou.vy")
    ballot_only = set((CONTRACTS / "ballot" / "ballot.vy").read_text().splitlines()) - set(
        iou.text.splitlines()
    )

    tried = list(fuzz([iou], 1, Count(300)))
    assert {t.seed.path for t in tried} == {CONTRACTS / "iou" / "iou.vy"}
    assert not any(line in t.input.text.splitlines() for t in tried for line in ballot_only)
    assert all((t.outcome is None) == (not t.input.changed) for t in tried)


def test_a_missing_seed_folder_returns_2_and_prints_nothing(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["run", "nope", "--count", "1"]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert "nope" in err
