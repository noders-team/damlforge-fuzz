import shutil
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
CONTRACTS = PROJECT / "contracts"
SEED_FILES = sorted(CONTRACTS.glob("*/*.vy"))

BITAND = "def f(count: int) -> int:\n    return count & 1\n"
"""Crashes forge in lower: `&` is missing from forge's _BIN_OPS table. `a // b` did too, until DamlForge v0.0.10."""
BITOR = "def f(count: int) -> int:\n    return count | 1\n"

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


@pytest.fixture
def write_vy(tmp_path):
    """Write a .vy file under tmp_path, outside any Daml project, and return its path."""

    def write(name: str, text: str) -> Path:
        path = tmp_path / name
        path.write_text(text)
        return path

    return write
