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

"""Print the input counts that the tests need with the installed forge and the current rules.

Several tests need a run that finds at least one or two groups. A forge upgrade,
a new rule, or a new seed changes how many inputs that takes. Run this script
after such a change and copy the numbers into the tests:

    python scripts/measure_test_counts.py

It compiles inputs in this process (no damlc), so it takes about a minute.
"""

import sys
from itertools import islice
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "src"))

from damlforge_fuzz import Crash, Ok, Seed, compile_and_sort, input_sequence  # noqa: E402

CONTRACTS = PROJECT / "contracts"
LIMIT = 100_000


def first_inputs(paths, want, key):
    """Input number and compile-call number at which `want` distinct keys have been seen."""
    seeds = [Seed.load(path) for path in paths]
    seen, calls = set(), 0
    for item in islice(input_sequence([seed.text for seed in seeds], 1), LIMIT):
        if not item.changed:
            continue
        calls += 1
        k = key(compile_and_sort(item.text, seeds[item.seed]))
        if k is not None:
            seen.add(k)
            if len(seen) >= want:
                return item.number, calls
    return None, calls


def crash_key(outcome):
    return outcome.key if isinstance(outcome, Crash) else None


def any_group_key(outcome):
    if isinstance(outcome, Crash):
        return ("crash", outcome.key)
    if isinstance(outcome, Ok) and outcome.loop_key is not None:
        return ("check", outcome.loop_key)
    return None


def family_key(family):
    def key(outcome):
        if isinstance(outcome, Ok) and outcome.loop_key is not None:
            return outcome.loop_key if outcome.loop_key.startswith(family) else None
        return None

    return key


def check_key(outcome):
    return outcome.loop_key if isinstance(outcome, Ok) else None


def main():
    every = sorted(CONTRACTS.glob("*/*.vy"))
    loops = [path for path in every if path.parent.name.startswith("loop_")]
    iou = [CONTRACTS / "iou" / "iou.vy"]
    rows = [
        ("all seeds: first crash (counted, ctrl-c test)", every, 1, crash_key),
        ("all seeds: third crash group (ctrl-c while shrinking)", every, 3, crash_key),
        ("iou alone: first group of any kind (stale folder test)", iou, 1, any_group_key),
        ("loop seeds: first L group (loop_run)", loops, 1, family_key("L")),
        ("loop seeds: second check group (ctrl-c in a loop group)", loops, 2, check_key),
    ]
    for label, paths, want, key in rows:
        number, calls = first_inputs(paths, want, key)
        print(f"{label}: input {number}, compile call {calls}")


if __name__ == "__main__":
    main()
