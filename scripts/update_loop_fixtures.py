"""Write the Daml of each loop fixture in tests/loops/ again with the installed forge.

    python scripts/update_loop_fixtures.py

Run it after a forge upgrade, when test_loopcheck.py says that forge writes
other Daml. It compiles each tests/loops/*.vy, writes its .daml, and puts the
forge version in EXPECTED.tsv. It prints each fixture whose Daml or loop
findings changed. It does not change the expected checks in EXPECTED.tsv:
read each printed fixture, and change its checks by hand when the new
findings are right. Running it again changes nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from damlforge_fuzz import FORGE_VERSION, Ok, Seed, compile_and_sort, find_loop_bugs

LOOPS = Path(__file__).resolve().parents[1] / "tests" / "loops"
VERSION = re.compile(r"(?<=DamlForge v)[\d.]+")


def main() -> int:
    expected = LOOPS / "EXPECTED.tsv"
    table = expected.read_text()
    old_version = VERSION.search(table).group()
    if _numbers(FORGE_VERSION) < _numbers(old_version):
        print(f"forge {FORGE_VERSION} is older than {old_version}, which wrote the fixtures")
        return 2
    failed = False
    for vy in sorted(LOOPS.glob("*.vy")):
        seed = Seed.load(vy)
        outcome = compile_and_sort(seed.text, seed)
        if not isinstance(outcome, Ok):
            print(f"{vy.stem}: forge does not write Daml for it now: {outcome}")
            failed = True
            continue
        daml_file = vy.with_suffix(".daml")
        old = daml_file.read_text()
        if outcome.daml == old:
            continue
        daml_file.write_text(outcome.daml)
        old_checks = _checks(find_loop_bugs(seed.text, old))
        new_checks = _checks(outcome.loop_bugs)
        if old_checks == new_checks:
            print(f"{vy.stem}: new Daml, the same loop findings ({old_checks})")
        else:
            print(f"{vy.stem}: new Daml, loop findings {old_checks} -> {new_checks}")
    expected.write_text(VERSION.sub(FORGE_VERSION, table, count=1))
    return 1 if failed else 0


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def _checks(bugs) -> str:
    return " ".join(bug.check for bug in bugs) or "none"


if __name__ == "__main__":
    sys.exit(main())
