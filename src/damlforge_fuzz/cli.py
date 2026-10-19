"""The `damlforge-fuzz` command. Unit 2 adds `check`; unit 3 adds `run`.

    damlforge-fuzz check PATH [PATH ...]

Each PATH is a .vy file, or a folder searched recursively for .vy files.
`check` prints one line per file, in argument order and sorted within a folder:

    OK       emit   contracts/iou/iou.vy
    REJECTED check  owner.vy  DF1213: No builtin or user-defined type named `owner` (field `owner` of `Iou`)
    CRASH    lower  floordiv.vy  KeyError 'FloorDiv' at forge/ir/lower.py:244
    CRASH    parse  deep.vy  RecursionError maximum recursion depth exceeded

Exit status: 0 when every file is OK, 1 when any file is REJECTED or CRASH,
2 for a usage error (a missing path, a folder with no .vy file, an unreadable
file, or DamlForge not installed). A usage error prints no result lines: every
path is loaded before anything compiles.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from damlforge_fuzz import Outcome


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
    args = parser.parse_args(argv)
    return _check(args.paths)


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
