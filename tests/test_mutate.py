"""The change rules and the input sequence. These tests need no forge."""

import os
import random
import re
import subprocess
import sys
from itertools import islice

import pytest
from conftest import PROJECT, SEED_FILES

from damlforge_fuzz import RULE_NAMES, Change, Input, input_sequence
from damlforge_fuzz.mutate import _RULES, _Context

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


def apply(rule, text, line):
    """The text after `rule` changes it at 1-based `line`, with random.Random(0), or None."""
    [apply] = [r.apply for r in _RULES if r.name == rule]
    new = apply(random.Random(0), line - 1, _Context((), tuple(text.split("\n"))))
    return None if new is None else "\n".join(new)


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
        text="{} = 1\nb = 2",
        changes=(Change("import_form", 1), Change("literal", 1), Change("inline_local", 1)),
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
    # import_name fits 17 of the 378 seed lines. Its first input with one
    # change that changes the text is input 9697.
    single = [i for i in first(9900, SEED_TEXTS) if len(i.changes) == 1]
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


def test_inline_local_puts_a_value_in_place_of_one_use():
    fetched = "def f(c: ContractId[Iou]) -> bool:\n    i = fetch(c)\n    return i.amount > 1"
    assert apply("inline_local", fetched, 3) == fetched.replace("i.amount", "fetch(c).amount")
    assert apply("inline_local", "s = a + b\nt = s * 2", 2) == "s = a + b\nt = (a + b) * 2"


def test_inline_local_reads_only_code_and_not_its_own_target():
    text = 'n = "n # n"  # n\nn = n + len("n")  # n\nm.n = 1'
    assert apply("inline_local", text, 2) == (
        'n = "n # n"  # n\nn = ("n # n") + len("n")  # n\nm.n = 1'
    )
    assert apply("inline_local", text, 3) is None
    assert apply("inline_local", "x = 1\ny = 2", 2) is None


LOOPS = """def f(rows: list[list[int]]) -> int:
    n = 0
    for row in rows:
        if n > 1:
            n = n + 1
        for x in row:
            n = n + x
    return n
"""


def test_early_return_inserts_the_return_that_follows_the_loop():
    assert apply("early_return", LOOPS, 5).split("\n")[3:7] == [
        "        if n > 1:",
        "            if row == row:",
        "                return n",
        "            n = n + 1",
    ]


def test_early_return_looks_out_of_an_inner_loop_that_no_return_follows():
    assert apply("early_return", LOOPS, 7).split("\n")[5:9] == [
        "        for x in row:",
        "            if row == row:",
        "                return n",
        "            n = n + x",
    ]


@pytest.mark.parametrize("line", [2, 3, 9])
def test_early_return_fits_only_a_line_in_a_loop_body(line):
    assert apply("early_return", LOOPS, line) is None


def test_early_return_needs_a_return_after_the_loop_and_a_loop_outside_a_string():
    no_return = "def f(xs: list[int]) -> None:\n    for x in xs:\n        g(x)"
    assert apply("early_return", no_return, 3) is None
    in_a_string = 'def f() -> int:\n    """\n    for x in xs:\n        x\n    """\n    return 1'
    assert apply("early_return", in_a_string, 4) is None


def test_wrap_in_loop_puts_a_statement_in_a_loop():
    text = "def f() -> int:\n    return 1  # one"
    assert apply("wrap_in_loop", text, 2) == (
        "def f() -> int:\n    for _k in range(0, 2):\n        return 1  # one"
    )


@pytest.mark.parametrize(
    "line", ["x = 1", "    if x:", "    else:  # c", "    @choice()", "    # c", ""]
)
def test_wrap_in_loop_fits_only_a_simple_statement_with_an_indent(line):
    assert apply("wrap_in_loop", line, 1) is None


def test_dedent_line_moves_a_line_4_spaces_to_the_left():
    assert apply("dedent_line", "        x = 1", 1) == "    x = 1"
    assert apply("dedent_line", "       x = 1", 1) is None
    assert apply("dedent_line", "        # c", 1) is None


def test_inline_var_puts_the_value_in_each_use_below_and_deletes_the_line():
    text = (
        "    for o in owners:\n        cid = create(Iou(owner=o))\n"
        "        cids.append(cid)\n    return cid"
    )
    assert apply("inline_var", text, 2) == (
        "    for o in owners:\n        cids.append(create(Iou(owner=o)))\n    return cid"
    )
    text = 't = a + b\nu = t * t  # t\nv = "t"'
    assert apply("inline_var", text, 1) == 'u = (a + b) * (a + b)  # t\nv = "t"'


@pytest.mark.parametrize(
    "text",
    ["t = 1\nt += 1\nu = t", "t = 1\nfor t in xs:\n    u = t", "t = 1\nu = 2", "t == 1\nu = t"],
)
def test_inline_var_does_not_fit_when_v_gets_a_new_value_or_has_no_use(text):
    assert apply("inline_var", text, 1) is None
