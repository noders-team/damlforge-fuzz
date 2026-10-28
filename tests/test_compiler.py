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

"""compile_and_sort through the public API, on real forge."""

import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from conftest import CONTRACTS, OWNER_FIELD, SEED_FILES, copy_iou
from planted_crash import IN_LOWER, Planted, plant

from damlforge_fuzz import Crash, CrashKey, ForgeLine, Ok, Rejected, Seed, Stage, compile_and_sort


def forge_daml_output(vy: Path, out: Path, module_name: str) -> str:
    forge_script = Path(sys.executable).with_name("forge")
    subprocess.run([forge_script, "daml", "--no-i", vy, "-o", out], check=True, capture_output=True)
    return (out / f"{module_name}.daml").read_text()


@pytest.mark.parametrize("path", SEED_FILES, ids=lambda p: p.stem)
def test_each_seed_is_ok_with_the_daml_forge_daml_writes(path, tmp_path):
    seed = Seed.load(path)
    outcome = compile_and_sort(seed.text, seed)
    assert isinstance(outcome, Ok), f"{path.name} should sort as Ok, got {outcome}"
    assert outcome.stage is Stage.EMIT
    assert outcome.daml == forge_daml_output(path, tmp_path, outcome.module_name)


def test_a_seed_keeps_the_daml_yaml_forge_read_or_none(write_vy):
    assert Seed.load(CONTRACTS / "iou" / "iou.vy").daml_yaml == CONTRACTS / "iou" / "daml.yaml"
    assert Seed.load(write_vy("alone.vy", "")).daml_yaml is None


def test_daml_yaml_build_options_reach_forge(tmp_path):
    project = tmp_path / "escrow"
    shutil.copytree(CONTRACTS / "escrow", project)
    with (project / "daml.yaml").open("a") as daml_yaml:
        daml_yaml.write("build-options:\n  - --explicit-serializable=yes\n")
    default = Seed.load(CONTRACTS / "escrow" / "escrow.vy")
    explicit = Seed.load(project / "escrow.vy")

    outcome = compile_and_sort(explicit.text, explicit)
    default_outcome = compile_and_sort(default.text, default)

    assert isinstance(outcome, Ok)
    assert outcome != default_outcome, "--explicit-serializable=yes should change the Daml"
    assert outcome.daml == forge_daml_output(project / "escrow.vy", tmp_path / "out", "Escrow")


def test_a_crash_has_its_stage_exception_message_and_the_forge_line_that_raised(
    monkeypatch, write_vy
):
    where = ForgeLine("forge/ir/lower.py", 289)
    plant(monkeypatch, Planted("# crash", Stage.LOWER, KeyError, "BitAnd", where))
    seed = Seed.load(write_vy("planted.vy", "# crash\n"))

    outcome = compile_and_sort(seed.text, seed)

    assert outcome == Crash(Stage.LOWER, "KeyError", "'BitAnd'", where)


def test_crashes_with_different_messages_at_one_forge_line_share_a_key(monkeypatch, write_vy):
    where, next_line = ForgeLine("forge/ir/lower.py", 289), ForgeLine("forge/ir/lower.py", 290)
    plant(
        monkeypatch,
        Planted("# and", Stage.LOWER, KeyError, "BitAnd", where),
        Planted("# or", Stage.LOWER, KeyError, "BitOr", where),
        Planted("# and below", Stage.LOWER, KeyError, "BitAnd", next_line),
    )
    seed = Seed.load(write_vy("ops.vy", ""))

    outcomes = [compile_and_sort(text, seed) for text in ["# and", "# or", "# and below"]]

    assert all(isinstance(outcome, Crash) for outcome in outcomes), outcomes
    bitand, bitor, below = outcomes
    assert bitand.message != bitor.message
    assert bitand.key == bitor.key == CrashKey("KeyError", where)
    assert below.key == CrashKey("KeyError", next_line)


def test_field_typed_as_its_own_name_is_rejected_with_DF1213(tmp_path):
    vy = copy_iou(tmp_path / "owner", OWNER_FIELD, "\n    owner: owner\n", count=1)
    seed = Seed.load(vy)

    outcome = compile_and_sort(seed.text, seed)

    assert isinstance(outcome, Rejected), outcome
    assert outcome.stage is Stage.CHECK
    assert "DF1213" in outcome.codes
    assert outcome.message.startswith("DF1213: ")


def test_several_errors_are_rejected_with_each_code_once(tmp_path):
    vy = copy_iou(tmp_path / "owners", "owner: Party", "owner: owner", count=2)
    seed = Seed.load(vy)

    outcome = compile_and_sort(seed.text, seed)

    assert isinstance(outcome, Rejected), outcome
    assert outcome.codes == ("DF1213",)
    assert outcome.message.startswith("DF1213: ")


def test_python_syntax_error_is_rejected_at_parse_with_no_code(write_vy):
    seed = Seed.load(write_vy("broken.vy", "def f(:\n"))

    outcome = compile_and_sort(seed.text, seed)

    assert isinstance(outcome, Rejected), outcome
    assert (outcome.stage, outcome.exception, outcome.codes) == (
        Stage.PARSE,
        "SyntaxException",
        (),
    )


def deep_sum(terms: int) -> str:
    return "def f(a: int) -> int:\n    return " + " + ".join(["a"] * terms) + "\n"


ODD_TEXTS = {
    "empty": "",
    "nul": "x\x00",
    "keyword": "def",
    "long": "x = 1\n" * 5000,
    "tabs": "\t\t)))",
    "deep": deep_sum(600),
}


@pytest.mark.parametrize("text", ODD_TEXTS.values(), ids=ODD_TEXTS.keys())
def test_odd_text_returns_an_outcome(text, write_vy):
    seed = Seed.load(write_vy("odd.vy", ""))
    assert isinstance(compile_and_sort(text, seed), Ok | Rejected | Crash)


def test_recursion_crashes_have_no_line_and_group_by_exception_alone(monkeypatch, write_vy):
    # Where the recursion limit hits depends on how deep the input nests.
    plant(
        monkeypatch,
        Planted("# 300 terms", Stage.PARSE, RecursionError, "maximum recursion depth exceeded",
                ForgeLine("forge/ast/nodes.py", 135)),
        Planted("# 600 terms", Stage.PARSE, RecursionError, "maximum recursion depth exceeded",
                ForgeLine("forge/ast/parse.py", 251)),
    )  # fmt: skip
    seed = Seed.load(write_vy("deep.vy", ""))

    shallow = compile_and_sort("# 300 terms\n", seed)
    deep = compile_and_sort("# 600 terms\n", seed)

    assert isinstance(shallow, Crash) and isinstance(deep, Crash), (shallow, deep)
    assert (deep.exception, deep.where) == ("RecursionError", None)
    assert shallow.key == deep.key


def test_stage_is_the_step_running_not_the_folder_of_the_file(monkeypatch, write_vy):
    lower_type = ForgeLine("forge/ir/lower.py", 101)
    plant(monkeypatch, Planted("# crash", Stage.CHECK, KeyError, "voters", lower_type))
    seed = Seed.load(write_vy("ballot.vy", "# crash\n"))

    outcome = compile_and_sort(seed.text, seed)

    assert isinstance(outcome, Crash), outcome
    assert (outcome.stage, outcome.where) == (Stage.CHECK, lower_type)


def test_a_python_indentation_error_that_escapes_forge_is_a_parse_crash(monkeypatch, write_vy):
    pre_parser = ForgeLine("forge/ast/pre_parser.py", 60)
    message = "unindent does not match any outer indentation level"
    plant(monkeypatch, Planted("# crash", Stage.PARSE, IndentationError, message, pre_parser))
    seed = Seed.load(write_vy("indent.vy", "# crash\n"))

    outcome = compile_and_sort(seed.text, seed)

    assert outcome == Crash(Stage.PARSE, "IndentationError", message, pre_parser)


def test_repeated_calls_in_mixed_order_give_equal_outcomes(monkeypatch):
    plant(monkeypatch, IN_LOWER)
    seed = Seed.load(CONTRACTS / "iou" / "iou.vy")

    outcomes = [compile_and_sort(text, seed) for text in [IN_LOWER.trigger, seed.text] * 2]

    assert isinstance(outcomes[0], Crash) and isinstance(outcomes[1], Ok)
    assert outcomes[2] == outcomes[0], "a crash after an OK compile should repeat exactly"
    assert outcomes[3] == outcomes[1], "an OK compile after a crash should repeat exactly"


def iou_with_deprecated_decimal() -> tuple[Seed, str]:
    seed = Seed.load(CONTRACTS / "iou" / "iou.vy")
    text = seed.text.replace("amount > Decimal(0)", "amount > Decimal({})", 1)
    assert text != seed.text, "iou.vy should contain `amount > Decimal(0)`"
    return seed, text


def test_result_does_not_depend_on_the_callers_warning_filters():
    seed, text = iou_with_deprecated_decimal()
    expected = compile_and_sort(text, seed)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        filters = list(warnings.filters)
        outcome = compile_and_sort(text, seed)
        assert warnings.filters == filters, "compile_and_sort should restore the caller's filters"

    assert isinstance(expected, Ok)
    assert outcome == expected


def test_compiling_prints_nothing_even_when_the_process_shows_warnings():
    seed, deprecated = iou_with_deprecated_decimal()
    syntax_warning = "def f(a: int) -> int:\n    return 1if a else 2\n"
    compile_each = (
        "import sys; from pathlib import Path; "
        "from damlforge_fuzz import Seed, compile_and_sort; "
        "seed = Seed.load(Path(sys.argv[1])); "
        "[compile_and_sort(text, seed) for text in sys.argv[2:]]"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "default",
            "-c",
            compile_each,
            seed.path,
            deprecated,
            syntax_warning,
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (result.stdout, result.stderr) == ("", "")


def test_the_text_argument_is_compiled_not_the_file(tmp_path):
    vy = tmp_path / "iou.vy"
    shutil.copy(CONTRACTS / "iou" / "iou.vy", vy)
    seed = Seed.load(vy)
    vy.write_text("def f(:\n")

    assert isinstance(compile_and_sort(seed.text, seed), Ok)
