"""The compare step: what its Python side does not compare, and why.

These tests need no dpm: every input stops before the Daml side.
"""

import pytest
from conftest import CONTRACTS, hide_dpm

from damlforge_fuzz import (
    CompareInput,
    DamlError,
    DamlSource,
    Dropped,
    Ok,
    Seed,
    Skipped,
    load_calls,
    run_and_compare,
)

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
