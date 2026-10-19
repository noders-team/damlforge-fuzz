"""The change rules and the input sequence. These tests need no forge."""

import os
import subprocess
import sys
from itertools import islice

import re

import pytest
from conftest import PROJECT, SEED_FILES

from damlforge_fuzz import RULE_NAMES, Change, Input, input_sequence

SEED_TEXTS = [path.read_text() for path in SEED_FILES]

DIGEST_OF_THE_FIRST_2000 = """
import hashlib, sys
from itertools import islice
from pathlib import Path
sys.modules["forge"] = None
from damlforge_fuzz import input_sequence
texts = [Path(p).read_text() for p in sys.argv[1:]]
digest = hashlib.sha256()
for i in islice(input_sequence(texts, 1), 2000):
    digest.update(repr(i).encode())
print(digest.hexdigest())
"""


def first(count, texts, random_seed=1):
    return list(islice(input_sequence(texts, random_seed), count))


def first_with_changes(texts, changes):
    """The first input of random seed 1 whose list of changes is `changes`."""
    return next(i for i in islice(input_sequence(texts, 1), 5000) if i.changes == changes)


def test_the_sequence_is_the_same_in_another_process_with_another_hash_seed():
    digests = set()
    for hash_seed in ("1", "2"):
        result = subprocess.run(
            [sys.executable, "-c", DIGEST_OF_THE_FIRST_2000, *map(str, SEED_FILES)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            check=True,
        )
        digests.add(result.stdout)
    assert len(digests) == 1, digests


def test_input_1_of_random_seed_1_on_a_two_line_text():
    assert next(input_sequence(["a = 1\nb = 2"], 1)) == Input(
        number=1,
        seed=0,
        text="raise\nb = 1\nb = 2",
        changes=(Change("name", 1), Change("name", 1), Change("insert_statement", 1)),
        changed=True,
    )


def test_another_random_seed_gives_another_sequence():
    one = [i.text for i in first(20, SEED_TEXTS, random_seed=1)]
    two = [i.text for i in first(20, SEED_TEXTS, random_seed=2)]
    assert one != two


def test_inputs_are_numbered_from_1_with_1_to_4_changes_by_known_rules():
    inputs = first(2000, SEED_TEXTS)
    assert [i.number for i in inputs] == list(range(1, 2001))
    assert {len(i.changes) for i in inputs} == {1, 2, 3, 4}
    assert {c.rule for i in inputs for c in i.changes} == set(RULE_NAMES)


def test_an_input_is_changed_exactly_when_its_text_differs_from_its_seed():
    inputs = first(2000, SEED_TEXTS)
    assert all(i.changed == (i.text != SEED_TEXTS[i.seed]) for i in inputs)
    assert {i.changed for i in inputs} == {True, False}


def test_every_rule_changes_some_text_on_its_own():
    single = [i for i in first(2000, SEED_TEXTS) if len(i.changes) == 1]
    changed_by = {i.changes[0].rule for i in single if i.changed}
    assert changed_by == set(RULE_NAMES)


def test_delete_line_and_copy_line_on_a_three_line_text():
    text = "a = 1\nb = 2\nc = 3"
    assert first_with_changes([text], (Change("delete_line", 2),)).text == "a = 1\nc = 3"
    assert first_with_changes([text], (Change("copy_line", 3),)).text == "a = 1\nb = 2\nc = 3\nc = 3"


def test_deleting_the_only_line_leaves_an_empty_text():
    deleted = first_with_changes(["x"], (Change("delete_line", 1),))
    assert (deleted.text, deleted.changed) == ("", True)


def test_donor_lines_come_only_from_the_texts_passed():
    alpha = "alpha_only = 1\nx = alpha_only\n"
    beta = "beta_only = 2\ny = beta_only\n"

    alone = first(2000, [alpha])
    assert {i.seed for i in alone} == {0}
    assert not any("beta_only" in i.text for i in alone)

    both = first(2000, [alpha, beta])
    assert any(i.seed == 0 and "beta_only" in i.text for i in both)


def test_no_seed_texts_is_a_value_error():
    with pytest.raises(ValueError, match="at least one seed text"):
        input_sequence([], 1)


def test_the_readme_lists_every_rule_in_order():
    readme = (PROJECT / "README.md").read_text()
    table = readme.split("## Change rules", 1)[1].split("###", 1)[0]
    assert tuple(re.findall(r"^\| `(\w+)` \|", table, re.MULTILINE)) == RULE_NAMES
