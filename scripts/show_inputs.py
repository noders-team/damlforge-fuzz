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

"""Print the inputs of a run, one by one: the seed, the changes, the changed lines, and forge's result.

    python scripts/show_inputs.py contracts/iou --count 5 --random-seed 1

The inputs are the same as for `damlforge-fuzz run` with the same seed folders
and random seed. Install the fuzzer and DamlForge first, as README.md shows.
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from damlforge_fuzz import Count, Crash, Ok, Rejected, Seed, fuzz
from damlforge_fuzz.cli import _bugs_text, _vy_files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("seed_folders", nargs="*", type=Path, metavar="SEED_FOLDER")
    parser.add_argument("--count", type=int, default=5, help="how many inputs to show (default 5)")
    parser.add_argument("--random-seed", type=int, default=1, help="default 1")
    args = parser.parse_args()

    seeds = [Seed.load(path) for path in _vy_files(args.seed_folders or [Path("contracts")])]
    for tried in fuzz(seeds, args.random_seed, Count(args.count)):
        item, seed = tried.input, tried.seed
        print(f"=== input {item.number}: starts from {seed.path}")
        for number, change in enumerate(item.changes, 1):
            print(f"    change {number}: {change.rule} on line {change.line}")
        old, new = seed.text.split("\n"), item.text.split("\n")
        for line in difflib.unified_diff(old, new, lineterm="", n=0):
            if line.startswith("@@"):
                print(f"  {line}")
            elif not line.startswith(("---", "+++")):
                print(f"    {line}")
        print(f"  result: {_result(tried.outcome)}\n")


def _result(outcome) -> str:
    match outcome:
        case None:
            return "SKIPPED (the changes left the text as it was, so forge did not compile it)"
        case Ok(loop_bugs=bugs) if bugs:
            return f"BAD_LOOP (forge wrote Daml with a loop bug) {_bugs_text(bugs)}"
        case Ok():
            return "OK (forge wrote Daml)"
        case Rejected(stage=stage, message=message):
            return f"REJECTED in {stage}: {message}"
        case Crash(stage=stage, key=key):
            return f"CRASH in {stage}: {key}"


if __name__ == "__main__":
    main()
