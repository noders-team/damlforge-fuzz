"""The import check (I1 to I4), the import rules, and the import bug programs.

The check and rule tests need no forge. The last test runs forge on
bugs/imports/ and shows when forge writes other Daml today, as the loop bug
programs do.
"""

import random
import re

import pytest
from conftest import PROJECT

from damlforge_fuzz import LoopCheck, Seed, build_daml, compile_and_sort, find_import_bugs
from damlforge_fuzz.cli import main
from damlforge_fuzz.mutate import _RULES, _Context

GOOD_DAML = """\
module ImportSibling where

import Models (Kind(..), Lot(..), Note(..), double)
import qualified Models2 as M
import DA.Map as Map
import qualified DA.Text as Text
import DA.Optional (fromSome)

f : Note -> Decimal
f note =
  let lot = Lot with kind = CASH, amount = double (M.size note)
  in (note.lot).amount + Map.size Map.empty + Text.length "A.b -- M.x"
"""
GOOD_VY = (
    "from forge.models import Party\nfrom models import Kind, Lot, Note, double\n"
    "import models2 as M\n"
)


def checks(vy, daml):
    return [bug.check for bug in find_import_bugs(vy, daml)]


def test_good_daml_with_every_kind_of_import_has_no_finding():
    assert checks(GOOD_VY, GOOD_DAML) == []


def test_i1_a_qualifier_that_no_import_binds():
    daml = GOOD_DAML.replace("import DA.Map as Map\n", "")
    [bug] = find_import_bugs(GOOD_VY, daml)
    assert (bug.check, bug.daml_line, bug.label) == (LoopCheck.I1, 11, "BAD_IMP")
    assert bug.detail == "Map. at Daml line 11 with no import that binds Map"
    assert checks("", "x = Party.amount\n") == [LoopCheck.I1]


def test_i2_a_lower_case_module_alias():
    assert checks(GOOD_VY, GOOD_DAML.replace("as M\n", "as m\n").replace("M.size", "m.size")) == [
        LoopCheck.I2
    ]


def test_i3_an_upper_case_name_selected_from_an_expression():
    assert checks("", "x = (M.Kind).CASH\n") == [LoopCheck.I1, LoopCheck.I3]
    assert checks("", "import qualified Models as M\nx = (M.Kind).CASH\n") == [LoopCheck.I3]


@pytest.mark.parametrize(
    ("vy", "expected"),
    [
        ("from models import Note, double, extra\n", [LoopCheck.I4]),
        ("from .models import Note, extra\n", [LoopCheck.I4]),
        ("import other\n", [LoopCheck.I4]),
        ("from models import *\n", []),
        ("from forge.models import Nothing\nfrom typing import Optional\n", []),
        ("from .enum import Enum\n", []),
        ("from models import (\n    Note,\n    double,\n)\n", []),
    ],
    ids=[
        "missing-name", "relative", "missing-module", "star", "forge-and-stdlib", "dot-stdlib",
        "parens",
    ],
)  # fmt: skip
def test_i4_a_vy_import_that_the_daml_does_not_have(vy, expected):
    assert checks(vy, GOOD_DAML) == expected


@pytest.mark.parametrize("text", ["", "\x00", "import", "import qualified", "(" * 1000, ").X" * 3])
def test_any_text_gives_findings_and_never_raises(text):
    find_import_bugs(text, text)


def apply(rule, text, line, seed=0):
    [apply] = [r.apply for r in _RULES if r.name == rule]
    lines = tuple(text.split("\n"))
    new = apply(random.Random(seed), line - 1, _Context(lines, lines))
    return None if new is None else "\n".join(new)


SIBLING = """\
from models import Note, double


def f(n: Note) -> Note:
    s = "Note"  # Note
    return Note(amount=double(n.amount), note=n.Note)
"""


@pytest.mark.parametrize("seed", range(4))
def test_import_form_qualifies_each_use_and_switches_back(seed):
    qualified = apply("import_form", SIBLING, 1, seed)
    head, *body = qualified.split("\n")
    prefix = head.split(" as ")[1] if " as " in head else "models"
    assert head.startswith("import models")
    assert body[2] == f"def f(n: {prefix}.Note) -> {prefix}.Note:"
    assert body[3] == '    s = "Note"  # Note'
    assert body[4] == f"    return {prefix}.Note(amount={prefix}.double(n.amount), note=n.Note)"
    assert apply("import_form", qualified, 1) == SIBLING


def test_import_form_does_not_fit_a_relative_or_aliased_from_import_or_other_lines():
    assert apply("import_form", "from .models import Note\nx = Note", 1) is None
    assert apply("import_form", "from models import Note as N\nx = N", 1) is None
    assert apply("import_form", "import models\nx = 1", 1) is None
    assert apply("import_form", "x = 1", 1) is None


def test_import_name_deletes_or_adds_a_name_and_import_module_changes_the_path():
    deleted = {apply("import_name", "from m import a, b, c", 1, seed) for seed in range(20)}
    assert "from m import a, c" in deleted
    assert any(re.fullmatch(r"from m import a, b, c, \w+", text) for text in deleted)
    assert apply("import_name", "    from m import a", 1) is None
    moved = {apply("import_module", "import math as m", 1, seed) for seed in range(40)}
    paths = (".math", "..math", "pkg.math", "forge.math", "maths")
    assert moved == {f"import {path} as m" for path in paths}


def readme_block(command):
    readme = (PROJECT / "bugs" / "imports" / "README.md").read_text()
    return readme.split(f"$ {command}\n", 1)[1].split("```", 1)[0]


def test_check_prints_each_import_bug_program_as_the_bug_readme_shows(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "bugs/imports"]) == 1
    assert capsys.readouterr().out == readme_block("damlforge-fuzz check bugs/imports")


def test_check_damlc_builds_each_program_with_its_sibling_as_the_bug_readme_shows(
    dpm, monkeypatch, capsys
):
    monkeypatch.chdir(PROJECT)

    assert main(["check", "--damlc", "bugs/imports"]) == 1
    assert capsys.readouterr().out == readme_block("damlforge-fuzz check --damlc bugs/imports")


def test_damlc_builds_a_text_with_the_siblings_it_imports_and_no_other(dpm, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "daml.yaml").write_bytes((PROJECT / "bugs" / "imports" / "daml.yaml").read_bytes())
    (folder / "models.vy").write_bytes((PROJECT / "bugs" / "imports" / "models.vy").read_bytes())
    (folder / "broken.vy").write_text(
        "import models as m\n\n\ndef f() -> m.Kind:\n    return m.Kind.CASH\n"
    )
    (folder / "main.vy").write_text(
        "from models import Kind\n\n\ndef f() -> Kind:\n    return Kind.CASH\n"
    )
    seed = Seed.load(folder / "main.vy")
    assert [sibling.module_name for sibling in seed.siblings] == ["Broken", "Models"]
    ok = compile_and_sort(seed.text, seed)

    [(_, error)] = build_daml([seed.daml_source(ok.daml, ok.module_name)])
    assert error is None, "main imports Models; Broken's bad Daml must not build with it"
    [(_, error)] = build_daml([seed.daml_source(ok.daml.replace("import Models", "--"), "Main")])
    assert error is not None and "Kind" in error.message, "with no import, Kind is not in scope"

    saved = tmp_path / "saved"
    saved.mkdir()
    seed.copy_siblings(saved, ok.daml)
    names = sorted(path.name for path in saved.iterdir())
    assert names == ["Models.daml", "broken.vy", "models.vy"]
