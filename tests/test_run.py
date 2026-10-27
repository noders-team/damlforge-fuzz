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

"""`damlforge-fuzz run`, driven through cli.main, and the fuzz loop behind it."""

import re

import pytest
from conftest import CONTRACTS, PROJECT

from damlforge_fuzz import Count, Seed, fuzz
from damlforge_fuzz.cli import main

FINAL_LINE = re.compile(
    r"random seed (\d+): (\d+) inputs, (\d+) OK, (\d+) rejected, (\d+) crash, (\d+) skipped"
)


@pytest.fixture
def run(tmp_path, capsys):
    """main(["run", *argv, "--reports", tmp_path]): its status and its first two stdout lines.

    The third line names a run folder, which differs between runs.
    """

    def run(*argv):
        status = main(["run", *argv, "--reports", str(tmp_path)])
        return status, capsys.readouterr().out.splitlines()[:2]

    return run


def test_a_counted_run_prints_the_random_seed_and_counts_that_add_up(monkeypatch, run):
    monkeypatch.chdir(PROJECT)

    status, (start, final) = run("contracts/iou", "--count", "300", "--random-seed", "1")
    assert start == "random seed 1, 1 seed, 300 inputs"
    seed, inputs, ok, rejected, crash, skipped = map(int, FINAL_LINE.fullmatch(final).groups())
    assert (seed, inputs) == (1, 300)
    assert ok + rejected + crash + skipped == 300
    assert status == (1 if crash else 0)


def test_two_runs_with_the_same_random_seed_print_the_same_lines(monkeypatch, run):
    monkeypatch.chdir(PROJECT)

    first = run("--count", "500", "--random-seed", "1")
    second = run("--count", "500", "--random-seed", "1")
    assert first == second


def test_a_run_without_random_seed_prints_one_that_repeats_it(monkeypatch, run):
    monkeypatch.chdir(PROJECT)

    status, lines = run("contracts/iou", "--count", "300")
    random_seed = re.fullmatch(r"random seed (\d+), 1 seed, 300 inputs", lines[0]).group(1)
    assert run("contracts/iou", "--count", "300", "--random-seed", random_seed) == (
        status,
        [f"random seed {random_seed}, 1 seed, 300 inputs", lines[1]],
    )


def test_a_timed_run_repeats_when_its_input_count_is_passed_as_count(monkeypatch, run):
    monkeypatch.chdir(PROJECT)

    status, (start, final) = run("contracts/iou", "--seconds", "1", "--random-seed", "3")
    assert start == "random seed 3, 1 seed, 1 second"
    inputs = FINAL_LINE.fullmatch(final).group(2)
    assert int(inputs) > 0
    assert run("contracts/iou", "--count", inputs, "--random-seed", "3") == (
        status,
        [f"random seed 3, 1 seed, {inputs} inputs", final],
    )


def test_no_seed_folder_means_every_seed_in_contracts(monkeypatch, run):
    monkeypatch.chdir(PROJECT)

    _, lines = run("--count", "1", "--random-seed", "1")
    assert lines[0] == "random seed 1, 15 seeds, 1 input"


def test_a_run_on_iou_compiles_only_changed_copies_of_iou():
    iou = Seed.load(CONTRACTS / "iou" / "iou.vy")
    ballot_only = set((CONTRACTS / "ballot" / "ballot.vy").read_text().splitlines()) - set(
        iou.text.splitlines()
    )

    tried = list(fuzz([iou], 1, Count(300)))
    assert {t.seed.path for t in tried} == {CONTRACTS / "iou" / "iou.vy"}
    assert not any(line in t.input.text.splitlines() for t in tried for line in ballot_only)
    assert all((t.outcome is None) == (not t.input.changed) for t in tried)


def test_a_missing_seed_folder_returns_2_and_prints_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["run", "nope", "--count", "1", "--reports", str(tmp_path)]) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert "nope" in err
    assert list(tmp_path.iterdir()) == []
