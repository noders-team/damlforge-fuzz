"""The `damlforge-fuzz` command. Unit 2 adds `check`; unit 3 adds `run`; unit 4 adds its report.

    damlforge-fuzz check PATH [PATH ...]

Each PATH is a .vy file, or a folder searched recursively for .vy files.
`check` prints one line per file, in argument order and sorted within a folder:

    OK       emit   contracts/iou/iou.vy
    REJECTED check  owner.vy  DF1213: No builtin or user-defined type named `owner` (field `owner` of `Iou`)
    CRASH    lower  bitand.vy  KeyError 'BitAnd' at forge/ir/lower.py:289
    CRASH    parse  deep.vy  RecursionError maximum recursion depth exceeded

Exit status: 0 when every file is OK, 1 when any file is REJECTED or CRASH,
2 for a usage error (a missing path, a folder with no .vy file, an unreadable
file, or DamlForge not installed). A usage error prints no result lines: every
path is loaded before anything compiles.

    damlforge-fuzz run [SEED_FOLDER ...] (--seconds N | --count N) [--random-seed S]
                       [--reports DIR]

`run` changes copies of the seeds at random and compiles each copy. Without a
SEED_FOLDER it uses contracts/. Without --random-seed it picks one. It prints
three lines, the last two when the run ends (the numbers are examples):

    random seed 48213, 4 seeds, 60 seconds
    random seed 48213: 31200 inputs, 7300 OK, 21000 rejected, 1900 crash, 1000 skipped
    14 crash groups, report in reports/2026-10-19T13-50-00Z

The first two lines hold no time, so two --count runs with one random seed
print the same first two lines. `--count 31200 --random-seed 48213` repeats
the 60-second run above. The third line names the run folder, which every run
makes under --reports (default: reports): report.json, report.md, and one
folder per crash group with the group's first input.

Exit status: 0 when no input crashed, 1 when any input crashed, 2 for a usage
error (as for check, and a --reports folder that cannot be made, or a report
that cannot be written), 130 on Ctrl-C, after all three lines and the report
for the inputs so far.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from damlforge_fuzz import Limit, Outcome, Totals


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
    args = parser.parse_args(argv)
    if args.command == "check":
        return _check(args.paths)
    return _run(args.seed_folders, args.seconds, args.count, args.random_seed, args.reports)


def _check(paths: Sequence[Path]) -> int:
    try:
        from damlforge_fuzz import Ok, Seed, compile_and_sort
    except ImportError as error:
        print(f"damlforge-fuzz: {error}", file=sys.stderr)
        return 2
    try:
        seeds = [Seed.load(path) for path in _vy_files(paths)]
    except (OSError, ValueError) as error:
        print(f"damlforge-fuzz check: {error}", file=sys.stderr)
        return 2
    status = 0
    for seed in seeds:
        outcome = compile_and_sort(seed.text, seed)
        print(_line(seed.path, outcome))
        if not isinstance(outcome, Ok):
            status = 1
    return status


def _run(
    seed_folders: Sequence[Path],
    seconds: float | None,
    count: int | None,
    random_seed: int | None,
    reports: Path,
) -> int:
    try:
        from damlforge_fuzz import Count, Report, Seconds, Seed, fuzz
    except ImportError as error:
        print(f"damlforge-fuzz: {error}", file=sys.stderr)
        return 2
    try:
        seeds = [Seed.load(path) for path in _vy_files(seed_folders or [Path("contracts")])]
    except (OSError, ValueError) as error:
        print(f"damlforge-fuzz run: {error}", file=sys.stderr)
        return 2
    if random_seed is None:
        # Short enough to retype from the screen.
        random_seed = secrets.randbelow(1_000_000)
    limit = Count(count) if count is not None else Seconds(seconds)
    try:
        report = Report.open(seeds, random_seed, limit, reports)
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
    try:
        report.write()
    except OSError as error:
        print(f"damlforge-fuzz run: cannot write the report: {error}", file=sys.stderr)
        return 2
    print(f"{_plural(len(report.groups), 'crash group')}, report in {report.folder}")
    if report.run.interrupted:
        return 130
    return 1 if report.totals.crash else 0


def _start_line(random_seed: int, seed_count: int, limit: Limit) -> str:
    """'random seed 48213, 4 seeds, 60 seconds' or 'random seed 1, 1 seed, 2000 inputs'."""
    from damlforge_fuzz import Count, Seconds

    match limit:
        case Count(n):
            how_long = _plural(n, "input")
        case Seconds(s):
            how_long = _plural(int(s) if s.is_integer() else s, "second")
    return f"random seed {random_seed}, {_plural(seed_count, 'seed')}, {how_long}"


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
    from damlforge_fuzz import Crash, Ok, Rejected

    head = f"{outcome.label:<9}{outcome.stage:<7}{path}"
    match outcome:
        case Ok():
            return head
        case Rejected(exception=exception, message=message, codes=codes):
            detail = message if codes else f"{exception}: {message}"
        case Crash(exception=exception, message=message, where=where):
            first_line = message.partition("\n")[0]
            detail = " ".join(part for part in (exception, first_line) if part)
            if where is not None:
                detail += f" at {where}"
    return f"{head}  {detail}"
