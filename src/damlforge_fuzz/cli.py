"""The `damlforge-fuzz` command. Unit 2 adds `check`; unit 3 adds `run`; unit 4 adds its report;
unit 5 adds shrinking and `shrink`; unit 6 adds --damlc; unit 8 adds the loop check; unit 10
shrinks the loop groups.

    damlforge-fuzz check [--damlc] PATH [PATH ...]

Each PATH is a .vy file, or a folder searched recursively for .vy files.
`check` prints one line per file, in argument order and sorted within a folder:

    OK       emit   contracts/iou/iou.vy
    REJECTED check  owner.vy  DF1213: No builtin or user-defined type named `owner` (field `owner` of `Iou`)
    CRASH    lower  bitand.vy  KeyError 'BitAnd' at forge/ir/lower.py:289
    CRASH    parse  deep.vy  RecursionError maximum recursion depth exceeded

With --damlc, `check` also builds the Daml of the OK files with damlc, in one
`dpm build`, and prints BAD_DAML for each file whose Daml damlc rejects, with
damlc's first error line:

    BAD_DAML emit   iou.vy  Variable not in scope: str : Decimal -> Text

The loop check reads the Daml of each OK file, with no damlc. A file whose
Daml has a loop bug prints BAD_LOOP, every check it fails, and the first bug:

    BAD_LOOP emit   b19.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20

With --damlc, a BAD_LOOP line ends with damlc's verdict, `; damlc builds` or
`; damlc rejects: <first error line>`. A file with a loop bug prints BAD_LOOP,
not BAD_DAML, because the loop bug names the cause.

Exit status: 0 when every file is OK, 1 when any file is REJECTED, CRASH,
BAD_DAML, or BAD_LOOP, 2 for a usage error (a missing path, a folder with no
.vy file, an unreadable file, or DamlForge not installed; with --damlc, also a
file with no daml.yaml, or dpm or its SDK missing). A usage error prints no
result lines: every path is loaded before anything compiles.

    damlforge-fuzz run [SEED_FOLDER ...] (--seconds N | --count N) [--random-seed S]
                       [--reports DIR] [--damlc]

`run` changes copies of the seeds at random and compiles each copy. Without a
SEED_FOLDER it uses contracts/. Without --random-seed it picks one. It prints
four lines, the last three when the run ends (the numbers are examples):

    random seed 48213, 4 seeds, 60 seconds
    random seed 48213: 31200 inputs, 7300 OK, 21000 rejected, 1900 crash, 1000 skipped
    loops: 19 inputs with loop findings, 3 loop groups
    14 crash groups, report in reports/2026-10-19T13-50-00Z

The first two lines hold no time, so two --count runs with one random seed
print the same first two lines. `--count 31200 --random-seed 48213` repeats
the 60-second run above. The loops line counts the OK inputs whose Daml has a
loop bug (BAD_LOOP) and their loop groups, one for each first check. The last
line names the run folder, which every run makes under --reports (default:
reports): report.json, report.md, and one folder per group with the group's
first input and its shrunk copy. Between the loops line and the last line,
`run` shrinks the input of each crash group and each loop group.

Before input 1, `run` compiles each seed. When the loop check finds a bug in
a seed, it prints one line to stderr and exits 2, because that bug would be
in almost every input.

With --damlc, `run` first builds the Daml of the unchanged seeds. When dpm or
the SDK is missing, or a seed's Daml does not build, it prints one line to
stderr and exits 2 before input 1. After the inputs it builds each distinct
Daml text of the OK inputs, groups the ones damlc rejects (BAD_DAML) in the
report, and prints one more line before the loops line. The loop groups are
then also split by damlc's verdict, and the loops line counts the groups whose
Daml damlc builds:

    damlc: 200 Daml texts, 157 bad, 22 bad Daml groups
    loops: 19 inputs with loop findings, 4 loop groups, 1 builds with damlc

With --damlc, the shrink of a loop group also keeps damlc's verdict, so it
builds the Daml of the candidates: a few seconds per loop group.

Exit status: 0 when no input crashed, no Daml was bad, and no loop group was
found, 1 when any input crashed, any Daml text was bad, or the report has a
loop group, 2 for a usage error (as for check, and a --reports folder that
cannot be made, a report that cannot be written, or dpm failing during the
damlc step or the shrinking, after the report is written), 130 on Ctrl-C,
after all the lines and the report for the inputs so far. A first Ctrl-C
stops the inputs, and the run still builds the Daml and shrinks. A Ctrl-C
while damlc builds keeps the batches already built and stops the damlc step.
A Ctrl-C while it shrinks stops the shrinking: the groups not shrunk yet get
"shrunk": null.

    damlforge-fuzz shrink FILE

`shrink` compiles FILE as `check` does. When it crashes, it deletes lines while
the text still crashes in the same group, writes the result to shrunk/ next to
FILE under the same name, and prints a line and the shrunk text:

    shrunk groups/g02/escrow.vy from 42 to 3 lines: groups/g02/shrunk/escrow.vy
    @template
    ...

Exit status: 0 when the shrunk file is written, 1 when FILE does not crash
(one line to stderr, nothing written), 2 for a usage error (as for check, and
a FILE that is a folder or already in a shrunk/ folder), 130 on Ctrl-C
(nothing written).
"""

from __future__ import annotations

import argparse
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from damlforge_fuzz import (
        DamlcSummary,
        DamlError,
        Limit,
        LoopBug,
        LoopGroup,
        Outcome,
        Seed,
        Totals,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return its exit status. argparse usage errors exit 2 via SystemExit."""
    parser = argparse.ArgumentParser(
        prog="damlforge-fuzz",
        description="A fuzzer for the DamlForge compiler, forge.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check",
        help="compile .vy files with forge and sort each result",
        description="Compile each .vy file with forge and print OK, REJECTED, or CRASH.",
    )
    check.add_argument(
        "--damlc",
        action="store_true",
        help="also build the Daml of the OK files with damlc (needs dpm and the Daml SDK)",
    )
    check.add_argument(
        "paths",
        nargs="+",
        type=Path,
        metavar="PATH",
        help="a .vy file, or a folder searched recursively for .vy files",
    )
    run = commands.add_parser(
        "run",
        help="change the seeds at random and compile each changed copy",
        description="Change copies of the seeds at random, compile each copy with forge, "
        "and count OK, rejected, crash, and skipped inputs.",
    )
    run.add_argument(
        "seed_folders",
        nargs="*",
        type=Path,
        metavar="SEED_FOLDER",
        help="a seed folder or .vy file (default: contracts)",
    )
    limit = run.add_mutually_exclusive_group(required=True)
    limit.add_argument("--seconds", type=_positive_float, metavar="N", help="run for N seconds")
    limit.add_argument(
        "--count", type=_positive_int, metavar="N", help="try inputs 1 to N; repeats exactly"
    )
    run.add_argument(
        "--random-seed",
        type=_non_negative_int,
        metavar="S",
        help="the number that fixes the sequence of inputs (default: a new one, printed)",
    )
    run.add_argument(
        "--reports",
        type=Path,
        default=Path("reports"),
        metavar="DIR",
        help="the folder that gets one run folder per run (default: reports)",
    )
    run.add_argument(
        "--damlc",
        action="store_true",
        help="also build the Daml of the OK inputs with damlc and report the bad ones "
        "(needs dpm and the Daml SDK)",
    )
    shrink = commands.add_parser(
        "shrink",
        help="delete lines of a crashing .vy file while it still crashes the same way",
        description="Delete lines of FILE while forge still crashes on it with the same "
        "exception at the same forge line, and write the result to shrunk/ next to FILE.",
    )
    shrink.add_argument("file", type=Path, metavar="FILE", help="a .vy file that crashes forge")
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.paths, args.damlc)
    if args.command == "shrink":
        return _shrink(args.file)
    return _run(
        args.seed_folders, args.seconds, args.count, args.random_seed, args.reports, args.damlc
    )


def _check(paths: Sequence[Path], damlc: bool) -> int:
    try:
        from damlforge_fuzz import (
            DamlcUnavailable,
            DamlSource,
            Ok,
            Seed,
            build_daml,
            compile_and_sort,
        )
    except ImportError as error:
        print(f"damlforge-fuzz: {error}", file=sys.stderr)
        return 2
    try:
        seeds = [Seed.load(path) for path in _vy_files(paths)]
        if damlc:
            _need_daml_yaml(seeds)
    except (OSError, ValueError) as error:
        print(f"damlforge-fuzz check: {error}", file=sys.stderr)
        return 2
    outcomes = [compile_and_sort(seed.text, seed) for seed in seeds]
    sources = {
        seed.path: DamlSource(outcome.daml, outcome.module_name, seed.daml_yaml)
        for seed, outcome in zip(seeds, outcomes, strict=True)
        if damlc and isinstance(outcome, Ok)
    }
    try:
        verdicts = dict(build_daml(set(sources.values()))) if sources else {}
    except DamlcUnavailable as error:
        print(f"damlforge-fuzz check: damlc: {error}", file=sys.stderr)
        return 2
    status = 0
    for seed, outcome in zip(seeds, outcomes, strict=True):
        source = sources.get(seed.path)
        error = verdicts.get(source)
        bugs = outcome.loop_bugs if isinstance(outcome, Ok) else ()
        if bugs:
            print(_bad_loop_line(seed.path, bugs, source in verdicts, error))
        elif error is not None:
            print(_bad_daml_line(seed.path, error))
        else:
            print(_line(seed.path, outcome))
        if not isinstance(outcome, Ok) or error is not None or bugs:
            status = 1
    return status


def _run(
    seed_folders: Sequence[Path],
    seconds: float | None,
    count: int | None,
    random_seed: int | None,
    reports: Path,
    damlc: bool,
) -> int:
    try:
        from damlforge_fuzz import Count, DamlcUnavailable, Report, Seconds, Seed, fuzz
    except ImportError as error:
        print(f"damlforge-fuzz: {error}", file=sys.stderr)
        return 2
    try:
        seeds = [Seed.load(path) for path in _vy_files(seed_folders or [Path("contracts")])]
        if damlc:
            _need_daml_yaml(seeds)
        _check_seeds(seeds, damlc)
    except (OSError, ValueError, DamlcUnavailable) as error:
        print(f"damlforge-fuzz run: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    if random_seed is None:
        # Short enough to retype from the screen.
        random_seed = secrets.randbelow(1_000_000)
    limit = Count(count) if count is not None else Seconds(seconds)
    try:
        report = Report.open(seeds, random_seed, limit, reports, damlc=damlc)
    except OSError as error:
        print(f"damlforge-fuzz run: cannot make a run folder in {reports}: {error}", file=sys.stderr)
        return 2
    print(_start_line(random_seed, len(seeds), limit), flush=True)
    try:
        for tried in fuzz(seeds, random_seed, limit):
            report.add(tried)
    except KeyboardInterrupt:
        report.interrupt()
    print(_final_line(random_seed, report.totals), flush=True)
    dpm_failed = False
    try:
        report.check_daml()
    except KeyboardInterrupt:
        report.interrupt()
    except DamlcUnavailable as error:
        print(f"damlforge-fuzz run: damlc: {error}", file=sys.stderr)
        dpm_failed = True
    if report.damlc is not None:
        print(_damlc_line(report.damlc, len(report.bad_daml_groups())), flush=True)
    loop_groups = report.loop_groups()
    print(_loops_line(loop_groups, damlc), flush=True)
    try:
        report.shrink()
    except KeyboardInterrupt:
        report.interrupt()
    except DamlcUnavailable as error:
        print(f"damlforge-fuzz run: damlc: {error}", file=sys.stderr)
        dpm_failed = True
    try:
        report.write()
    except OSError as error:
        print(f"damlforge-fuzz run: cannot write the report: {error}", file=sys.stderr)
        return 2
    print(f"{_plural(len(report.groups), 'crash group')}, report in {report.folder}")
    if dpm_failed:
        return 2
    if report.run.interrupted:
        return 130
    bad = report.totals.crash or (report.damlc and report.damlc.bad_texts) or loop_groups
    return 1 if bad else 0


def _need_daml_yaml(seeds: Sequence[Seed]) -> None:
    """Raise ValueError for the first seed with no daml.yaml: damlc needs its sdk-version."""
    for seed in seeds:
        if seed.daml_yaml is None:
            raise ValueError(f"--damlc needs a daml.yaml for {seed.path}, and found none")


def _check_seeds(seeds: Sequence[Seed], damlc: bool) -> None:
    """Raise ValueError when the loop check finds a bug in a seed. With damlc, also
    when forge does not compile a seed or damlc rejects a seed's Daml.

    One compile per seed, before input 1, in every run: a seed's own loop bug
    would be in almost every input. Without damlc, a seed that forge does not
    compile is still accepted. With damlc, one build of all the seeds' Daml, so
    a missing dpm or SDK fails in about a second, not after the run, and no bad
    Daml group comes from a seed itself. Raises DamlcUnavailable when dpm
    cannot build.
    """
    from damlforge_fuzz import DamlSource, Ok, build_daml, compile_and_sort

    sources = {}
    for seed in seeds:
        outcome = compile_and_sort(seed.text, seed)
        if isinstance(outcome, Ok) and outcome.loop_bugs:
            raise ValueError(
                f"the loop check finds a bug in seed {seed.path}: {_bugs_text(outcome.loop_bugs)}"
            )
        if not damlc:
            continue
        if not isinstance(outcome, Ok):
            raise ValueError(
                f"--damlc needs seeds that forge compiles: {_line(seed.path, outcome)}"
            )
        sources[DamlSource(outcome.daml, outcome.module_name, seed.daml_yaml)] = seed
    if not damlc:
        return
    for source, error in build_daml(sources):
        if error is not None:
            raise ValueError(
                f"damlc rejects the Daml of seed {sources[source].path}: {error.message}"
            )


def _shrink(path: Path) -> int:
    try:
        from damlforge_fuzz import Crash, Seed, compile_and_sort, same_crash, shrink, shrunk_path
    except ImportError as error:
        print(f"damlforge-fuzz: {error}", file=sys.stderr)
        return 2
    if path.parent.name == "shrunk":
        # Shrinking again changes nothing, and would write shrunk/shrunk/.
        print(f"damlforge-fuzz shrink: {path} is already a shrunk file", file=sys.stderr)
        return 2
    try:
        if path.is_dir():
            raise IsADirectoryError(f"{path} is a folder, not a .vy file")
        seed = Seed.load(path)
    except (OSError, ValueError) as error:
        print(f"damlforge-fuzz shrink: {error}", file=sys.stderr)
        return 2
    try:
        outcome = compile_and_sort(seed.text, seed)
        if not isinstance(outcome, Crash):
            detail = _detail(outcome)
            result = f"{outcome.label} {outcome.stage}" + (f"  {detail}" if detail else "")
            print(f"{path} does not crash forge: {result}", file=sys.stderr)
            return 1
        text = shrink(seed.text, seed, same_crash(outcome.key))
    except KeyboardInterrupt:
        return 130
    out = shrunk_path(path)
    try:
        out.parent.mkdir(exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="")
    except OSError as error:
        print(f"damlforge-fuzz shrink: cannot write {out}: {error}", file=sys.stderr)
        return 2
    before, after = len(seed.text.splitlines()), len(text.splitlines())
    print(f"shrunk {path} from {before} to {_plural(after, 'line')}: {out}")
    print(text, end="" if text.endswith("\n") else "\n")
    return 0


def _start_line(random_seed: int, seed_count: int, limit: Limit) -> str:
    """'random seed 48213, 4 seeds, 60 seconds' or 'random seed 1, 1 seed, 2000 inputs'."""
    from damlforge_fuzz import Count, Seconds

    match limit:
        case Count(n):
            how_long = _plural(n, "input")
        case Seconds(s):
            how_long = _plural(int(s) if s.is_integer() else s, "second")
    return f"random seed {random_seed}, {_plural(seed_count, 'seed')}, {how_long}"


def _damlc_line(damlc: DamlcSummary, groups: int) -> str:
    """'damlc: 200 Daml texts, 157 bad, 22 bad Daml groups'."""
    return (
        f"damlc: {_plural(damlc.checked_texts, 'Daml text')}, {damlc.bad_texts} bad, "
        f"{_plural(groups, 'bad Daml group')}"
    )


def _loops_line(groups: Sequence[LoopGroup], damlc: bool) -> str:
    """'loops: 19 inputs with loop findings, 4 loop groups, 1 builds with damlc'.

    Every number comes from the groups. The last part is there only with
    --damlc. Its verb agrees with the groups: '1 builds', '7 build'.
    """
    inputs = sum(group.count for group in groups)
    line = (
        f"loops: {_plural(inputs, 'input')} with loop findings, "
        f"{_plural(len(groups), 'loop group')}"
    )
    if damlc:
        builds = sum(group.damlc == "builds" for group in groups)
        line += f", {builds} {'builds' if builds == 1 else 'build'} with damlc"
    return line


def _final_line(random_seed: int, totals: Totals) -> str:
    return (
        f"random seed {random_seed}: {_plural(totals.inputs, 'input')}, {totals.ok} OK, "
        f"{totals.rejected} rejected, {totals.crash} crash, {totals.skipped} skipped"
    )


def _plural(number: float, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value <= 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number above 0")
    return value


def _positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = 0.0
    if not value > 0:  # also refuses nan
        raise argparse.ArgumentTypeError(f"{text!r} is not a number above 0")
    return value


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = -1
    if value < 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number of 0 or more")
    return value


def _vy_files(paths: Sequence[Path]) -> list[Path]:
    """Expand PATH arguments into .vy files, each listed once, in a fixed order.

    The order is part of the contract: unit 3 picks seeds from this list, and
    the same arguments must give the same list for --random-seed to repeat.
    Hidden folders, such as .daml/ and .venv/, are skipped.

    Raises FileNotFoundError for a missing path or a folder with no .vy file.
    """
    files: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            found = sorted(
                file
                for file in path.rglob("*.vy")
                if not any(part.startswith(".") for part in file.relative_to(path).parts)
            )
            if not found:
                raise FileNotFoundError(f"no .vy files under {path}")
        elif path.exists():
            found = [path]
        else:
            raise FileNotFoundError(f"no such file or folder: {path}")
        for file in found:
            if file.resolve() not in seen:
                seen.add(file.resolve())
                files.append(file)
    return files


def _line(path: Path, outcome: Outcome) -> str:
    """One result line: LABEL, STAGE, PATH, then what went wrong.

    The label and stage columns are padded so the paths line up.
    """
    head = f"{outcome.label:<9}{outcome.stage:<7}{path}"
    detail = _detail(outcome)
    return f"{head}  {detail}" if detail else head


def _bad_daml_line(path: Path, error: DamlError) -> str:
    """'BAD_DAML emit   iou.vy  Variable not in scope: ...': forge wrote Daml, damlc rejects it."""
    return f"{error.label:<9}{'emit':<7}{path}  {error.message}"


def _bad_loop_line(
    path: Path, bugs: Sequence[LoopBug], built: bool, error: DamlError | None
) -> str:
    """'BAD_LOOP emit   b19.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20'.

    When damlc built the Daml (`built`), the line ends with '; damlc builds' or
    '; damlc rejects: ' and damlc's first error line.
    """
    line = f"{bugs[0].label:<9}{'emit':<7}{path}  {_bugs_text(bugs)}"
    if not built:
        return line
    return line + ("; damlc builds" if error is None else f"; damlc rejects: {error.message}")


def _bugs_text(bugs: Sequence[LoopBug]) -> str:
    """'L2 L4: fetch at Daml line 22 in the pure foldl of line 20': every check, then the first bug."""
    return f"{' '.join(bug.check for bug in bugs)}: {bugs[0].detail}"


def _detail(outcome: Outcome) -> str:
    """What went wrong, as a result line ends: '' for OK."""
    from damlforge_fuzz import Crash, Ok, Rejected

    match outcome:
        case Ok():
            return ""
        case Rejected(exception=exception, message=message, codes=codes):
            detail = message if codes else f"{exception}: {message}"
        case Crash(exception=exception, message=message, where=where):
            first_line = message.partition("\n")[0]
            detail = " ".join(part for part in (exception, first_line) if part)
            if where is not None:
                detail += f" at {where}"
    return detail
