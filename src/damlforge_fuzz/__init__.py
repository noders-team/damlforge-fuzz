"""damlforge-fuzz: change seed contracts at random and report where forge crashes.

Unit 2 compiles one .vy text with forge, in this process, and sorts the result
into OK, REJECTED, or CRASH::

    from pathlib import Path
    from damlforge_fuzz import Crash, Ok, Rejected, Seed, compile_and_sort

    seed = Seed.load(Path("contracts/iou/iou.vy"))
    outcome = compile_and_sort(seed.text.replace(" > ", " // ", 1), seed)
    match outcome:
        case Ok(daml=daml, module_name=name):
            ...  # forge wrote Daml module `name`
        case Rejected(codes=codes):
            ...  # forge reported its own error, such as ("DF1213",)
        case Crash(key=key):
            ...  # a forge bug; key is (exception type, forge file:line)

Unit 3 makes the inputs and runs them. input_sequence needs no forge::

    from damlforge_fuzz import Count, Totals, fuzz, input_sequence

    first = next(input_sequence([seed.text], random_seed=1))  # Input 1 of random seed 1
    totals = Totals()
    for tried in fuzz([seed], random_seed=1, limit=Count(2000)):
        totals.add(tried)

Import from this package only. The modules behind it are not part of the API.
"""

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from damlforge_fuzz.compiler import (
        Crash,
        CrashKey,
        ForgeLine,
        Ok,
        Outcome,
        Rejected,
        Seed,
        Stage,
        compile_and_sort,
    )
    from damlforge_fuzz.mutate import RULE_NAMES, Change, Input, input_sequence
    from damlforge_fuzz.runner import Count, Limit, Seconds, Totals, Tried, fuzz

_HOME = {
    **dict.fromkeys(
        ["Crash", "CrashKey", "ForgeLine", "Ok", "Outcome", "Rejected", "Seed", "Stage"]
        + ["compile_and_sort"],
        "compiler",
    ),
    **dict.fromkeys(["Change", "Input", "RULE_NAMES", "input_sequence"], "mutate"),
    **dict.fromkeys(["Count", "Limit", "Seconds", "Totals", "Tried", "fuzz"], "runner"),
}
"""The module that holds each public name. compiler and runner load forge; mutate does not."""

__all__ = sorted(_HOME)


def __getattr__(name: str) -> object:
    # The command's module, damlforge_fuzz.cli, is inside this package, so this
    # file runs before `damlforge-fuzz --help`. Each module loads on first use,
    # so --help, usage errors, and the change rules work without DamlForge.
    if name in _HOME:
        return getattr(importlib.import_module(f"damlforge_fuzz.{_HOME[name]}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
