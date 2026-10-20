"""Compare sets of change rules on the same seeds by what the loop check finds.

    python scripts/compare_rules.py contracts/loop_* --count 5000 --random-seed 1 2 3 \\
        --first 10 --leave-out inline_var

Each rule set runs the inputs of each random seed through forge, as
`damlforge-fuzz run` does without --damlc, and counts the OK inputs and, for
each first loop check (L1 to L4), the inputs and the loop groups. Without
damlc a run has at most one loop group for each check, so the groups of a
check are the random seeds that found it.

The rule sets are all the rules; the first N rules with --first, which are the
rules from before the later ones were added at the end of the list; and all
the rules but one, for each rule that --leave-out names.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from unittest import mock

from damlforge_fuzz import RULE_NAMES, Count, LoopCheck, Ok, Seed, fuzz, mutate
from damlforge_fuzz.cli import _vy_files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("seed_folders", nargs="+", type=Path, metavar="SEED_FOLDER")
    parser.add_argument("--count", type=int, required=True, help="inputs for each random seed")
    parser.add_argument("--random-seed", type=int, nargs="+", required=True)
    parser.add_argument("--first", type=int, help="also run with only the first N rules")
    parser.add_argument("--leave-out", nargs="*", default=[], choices=RULE_NAMES, metavar="RULE")
    args = parser.parse_args()

    rules = mutate._RULES
    rule_sets = {f"all {len(rules)} rules": rules}
    if args.first:
        rule_sets[f"first {args.first} rules"] = rules[: args.first]
    for name in args.leave_out:
        rule_sets[f"all but {name}"] = tuple(rule for rule in rules if rule.name != name)

    seeds = [Seed.load(path) for path in _vy_files(args.seed_folders)]
    random_seeds = " ".join(map(str, args.random_seed))
    print(f"{len(seeds)} seeds, random seeds {random_seeds}, {args.count} inputs each")
    print("cells: inputs/groups of the loop findings whose first check is that check")
    print(f"{'rule set':<30} {'OK':>6}" + "".join(f" {check:>9}" for check in LoopCheck))
    for label, rule_set in rule_sets.items():
        ok, inputs, groups = 0, Counter(), Counter()
        # input_sequence reads mutate._RULES for each input, so the patch
        # changes the rules and nothing else.
        with mock.patch.object(mutate, "_RULES", rule_set):
            for random_seed in args.random_seed:
                checks = set()
                for tried in fuzz(seeds, random_seed, Count(args.count)):
                    if isinstance(tried.outcome, Ok):
                        ok += 1
                        if tried.outcome.loop_key is not None:
                            inputs[tried.outcome.loop_key] += 1
                            checks.add(tried.outcome.loop_key)
                groups.update(checks)
        cells = "".join(f" {f'{inputs[check]}/{groups[check]}':>9}" for check in LoopCheck)
        print(f"{label:<30} {ok:>6}{cells}", flush=True)


if __name__ == "__main__":
    main()
