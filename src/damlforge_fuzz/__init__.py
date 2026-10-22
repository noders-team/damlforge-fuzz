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

Unit 4 groups the crashes and writes the run folder (report.json, report.md,
and one saved input per group)::

    from damlforge_fuzz import Report

    report = Report.open([seed], 1, Count(2000), reports=Path("reports"))
    for tried in fuzz([seed], random_seed=1, limit=Count(2000)):
        report.add(tried)
    report.write()  # report.folder is reports/2026-10-19T13-50-00Z
    report.groups   # {CrashKey: Group}, in first-seen order

Unit 5 shrinks each crashing input: it deletes lines while the text still
crashes with the same key. Report.shrink() does this for every group, and
write() saves each result under groups/gNN/shrunk/::

    from damlforge_fuzz import same_crash, shrink, shrunk_path

    small = shrink(text, seed, same_crash(crash.key))  # a subsequence of text's lines
    shrunk_path(path)  # groups/g02/escrow.vy -> groups/g02/shrunk/escrow.vy

Unit 6 builds the Daml of OK inputs with damlc, through `dpm build`, and
groups the texts damlc rejects (BAD_DAML). It needs dpm and the Daml SDK::

    from damlforge_fuzz import DamlSource, build_daml

    source = seed.daml_source(ok.daml, ok.module_name)  # with the seed's sibling modules
    for source, error in build_daml([source]):  # one dpm build per 500 texts
        ...  # error is None, or a DamlError with .message and .key

    report = Report.open([seed], 1, Count(2000), Path("reports"), damlc=True)
    ...
    report.check_daml()        # after the inputs: every distinct Daml text
    report.bad_daml_groups()   # [BadDamlGroup], ids d01, d02, ...

Unit 8 checks the loops in forge's Daml (BAD_LOOP). The check reads the .vy
text and the Daml, and needs no forge and no damlc. compile_and_sort runs it,
so each Ok carries its loop bugs::

    from damlforge_fuzz import find_loop_bugs

    outcome = compile_and_sort(text, seed)
    if isinstance(outcome, Ok) and outcome.loop_bugs:
        outcome.loop_key             # LoopCheck.L3, the first check that fails
        outcome.loop_bugs[0].detail  # "the return in a loop of choice GiveUntil at Daml line 14 ..."
    find_loop_bugs(vy_text, daml_text)  # the same check on a saved .vy text and its Daml

    report.loop_groups()  # [LoopGroup], ids l01, l02, ...: one per first check (and damlc verdict)

Unit 10 shrinks the first input of each loop group too. same_loop keeps the
first check and, with a verdict, damlc's verdict on the Daml, so it needs dpm::

    from damlforge_fuzz import same_loop

    small = shrink(text, seed, same_loop(outcome.loop_key, "builds", seed))

Unit 11 runs each OK input of a seed with a calls file (loop_give.calls.yaml
next to loop_give.vy) in Python and in Daml Script, and compares (BAD_RUN).
It needs dpm and the Daml SDK::

    from damlforge_fuzz import CompareInput, Compared, load_calls, run_and_compare

    calls = load_calls(seed)  # None when the seed has no calls file
    inputs = {"mine": CompareInput(text, outcome, seed, calls)}  # outcome is an Ok
    for key, result in run_and_compare(inputs):  # one batch per 100 inputs
        if isinstance(result, Compared) and result.difference is not None:
            ...  # .kind "contracts", .call "Iou.GiveAll #1", .python, .test

    report = Report.open([seed], 1, Count(2000), Path("reports"), compare={str(seed.path): calls})
    ...
    report.run_and_compare()  # after the inputs, and after check_daml() with damlc
    report.run_groups()       # [RunGroup], ids r01, r02, ...

Import from this package only. The modules behind it are not part of the API.
"""

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from damlforge_fuzz.compiler import (
        FORGE_VERSION,
        STAGE_TEXT,
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
    from damlforge_fuzz.damlc import (
        DamlcUnavailable,
        DamlError,
        DamlErrorKey,
        DamlSource,
        build_daml,
    )
    from damlforge_fuzz.compare import (
        Call,
        Calls,
        Compared,
        CompareInput,
        Difference,
        DifferenceKind,
        Dropped,
        InputResult,
        Skipped,
        calls_path,
        load_calls,
        run_and_compare,
    )
    from damlforge_fuzz.importcheck import find_import_bugs
    from damlforge_fuzz.loopcheck import LOOP_CHECK_TEXT, LoopBug, LoopCheck, find_loop_bugs
    from damlforge_fuzz.mutate import RULE_NAMES, Change, Input, input_sequence
    from damlforge_fuzz.report import (
        BadDamlGroup,
        CompareSummary,
        DamlcSummary,
        FirstSeen,
        Group,
        LoopGroup,
        Report,
        Run,
        RunGroup,
        Tick,
    )
    from damlforge_fuzz.runner import Count, Limit, Seconds, Totals, Tried, fuzz
    from damlforge_fuzz.shrinker import same_crash, same_loop, shrink, shrunk_path

_HOME = {
    **dict.fromkeys(
        ["FORGE_VERSION", "Crash", "CrashKey", "ForgeLine", "Ok", "Outcome", "Rejected", "Seed", "Stage"]
        + ["STAGE_TEXT", "compile_and_sort"],
        "compiler",
    ),
    **dict.fromkeys(["Change", "Input", "RULE_NAMES", "input_sequence"], "mutate"),
    **dict.fromkeys(["Count", "Limit", "Seconds", "Totals", "Tried", "fuzz"], "runner"),
    **dict.fromkeys(
        ["BadDamlGroup", "CompareSummary", "DamlcSummary", "FirstSeen", "Group", "LoopGroup"]
        + ["Report", "Run", "RunGroup", "Tick"],
        "report",
    ),
    **dict.fromkeys(
        ["DamlError", "DamlErrorKey", "DamlSource", "DamlcUnavailable", "build_daml"], "damlc"
    ),
    **dict.fromkeys(["same_crash", "same_loop", "shrink", "shrunk_path"], "shrinker"),
    **dict.fromkeys(["LOOP_CHECK_TEXT", "LoopBug", "LoopCheck", "find_loop_bugs"], "loopcheck"),
    "find_import_bugs": "importcheck",
    **dict.fromkeys(
        ["Call", "Calls", "CompareInput", "Compared", "Difference", "DifferenceKind", "Dropped"]
        + ["InputResult", "Skipped", "calls_path", "load_calls", "run_and_compare"],
        "compare",
    ),
}
"""The module that holds each public name. compiler, runner, and report load forge; mutate,
damlc, loopcheck, and compare do not."""

__all__ = sorted(_HOME)


def __getattr__(name: str) -> object:
    # The command's module, damlforge_fuzz.cli, is inside this package, so this
    # file runs before `damlforge-fuzz --help`. Each module loads on first use,
    # so --help, usage errors, and the change rules work without DamlForge.
    if name in _HOME:
        return getattr(importlib.import_module(f"damlforge_fuzz.{_HOME[name]}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
