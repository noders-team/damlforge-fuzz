"""damlforge-fuzz: change seed contracts at random and report where forge crashes.

Unit 2 provides one operation. It compiles one .vy text with forge, in this
process, and sorts the result into OK, REJECTED, or CRASH::

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

Import from this package only. The modules behind it are not part of the API.
"""

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

__all__ = [
    "Crash",
    "CrashKey",
    "ForgeLine",
    "Ok",
    "Outcome",
    "Rejected",
    "Seed",
    "Stage",
    "compile_and_sort",
]


def __getattr__(name: str) -> object:
    # The command's module, damlforge_fuzz.cli, is inside this package, so this
    # file runs before `damlforge-fuzz --help`. The compiler, and forge with it,
    # loads on first use, so --help and usage errors work without DamlForge.
    if name in __all__:
        from damlforge_fuzz import compiler

        return getattr(compiler, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
