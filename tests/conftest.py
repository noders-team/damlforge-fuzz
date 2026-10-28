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

import re
import shutil
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
CONTRACTS = PROJECT / "contracts"
SEED_FILES = sorted(CONTRACTS.glob("*/*.vy"))
LOOP_BUGS = "reports/2026-10-20T16-34-28Z/analysis/loops"
"""The loop bug programs b17 to b23, in the analysis of the report that found them."""
IMPORT_BUGS = "reports/2026-10-26T07-07-10Z/analysis/imports"
"""The import bug programs b31 to b33, in the analysis of the report that found them."""

FIXTURE_FORGE = re.search(
    r"DamlForge v([\d.]+)", (PROJECT / "tests" / "loops" / "EXPECTED.tsv").read_text()
).group(1)
"""The forge version that wrote the Daml in tests/loops/."""

OWNER_FIELD = "\n    owner: Party\n"
"""iou.vy's field line. "owner: Party" alone also matches `new_owner: Party` in Transfer."""


def copy_iou(folder: Path, old: str, new: str, count: int) -> Path:
    """Copy contracts/iou/ to `folder`, replace `old` with `new` in iou.vy, and return that iou.vy.

    Fails when iou.vy does not contain `old` exactly `count` times, so a seed
    edit cannot quietly change which lines the test edits.
    """
    shutil.copytree(CONTRACTS / "iou", folder)
    vy = folder / "iou.vy"
    text = vy.read_text()
    assert text.count(old) == count, f"iou.vy should contain {old!r} {count} times"
    vy.write_text(text.replace(old, new))
    return vy


def hide_dpm(monkeypatch, tmp_path):
    """Make find_dpm() find no dpm: an empty PATH, and a HOME with no .dpm/bin/dpm."""
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def write_vy(tmp_path):
    """Write a .vy file under tmp_path, outside any Daml project, and return its path."""

    def write(name: str, text: str) -> Path:
        path = tmp_path / name
        path.write_text(text)
        return path

    return write


@pytest.fixture(scope="session")
def dpm():
    """dpm's path. Skips the test when dpm or the SDK in contracts/*/daml.yaml (3.5.2) is missing.

    One build of the unchanged iou seed proves both, and that its Daml builds.
    """
    from damlforge_fuzz import DamlcUnavailable, Seed, compile_and_sort
    from damlforge_fuzz.damlc import DamlSource, build_daml, find_dpm

    path = find_dpm()
    if path is None:
        pytest.skip("dpm not found on PATH or at ~/.dpm/bin/dpm")
    seed = Seed.load(CONTRACTS / "iou" / "iou.vy")
    ok = compile_and_sort(seed.text, seed)
    try:
        [(_, error)] = build_daml([DamlSource(ok.daml, ok.module_name, seed.daml_yaml)])
    except DamlcUnavailable as unavailable:
        pytest.skip(f"dpm cannot build the seeds' Daml SDK: {unavailable}")
    assert error is None, f"the iou seed's Daml does not build: {error}"
    return path


def version(text):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


@pytest.fixture
def fixture_forge():
    """Skip a test of forge's own output on a forge older than the one that wrote tests/loops/.

    An older forge, such as v0.0.7, writes other Daml and has other loop bugs.
    A newer forge must still write the saved Daml, so a change in forge fails
    these tests and shows which saved Daml to write again.
    """
    from damlforge_fuzz import FORGE_VERSION

    if version(FORGE_VERSION) < version(FIXTURE_FORGE):
        pytest.skip(
            f"tests/loops/ holds the Daml of DamlForge {FIXTURE_FORGE}, not {FORGE_VERSION}"
        )
