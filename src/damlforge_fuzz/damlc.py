"""Build the Daml that forge wrote with damlc, through `dpm build`, and sort each text.

This module imports no forge and no other damlforge_fuzz module. It owns four
decisions:

- how dpm is found: on PATH, then ~/.dpm/bin/dpm, the same lookup as `forge dar`;
- how many texts share one temporary Daml project, and how each text gets its
  own module name there, so that every damlc error maps to one text (BATCH);
- which part of dpm's output is "the first damlc error" of a text, and when a
  failed build is about dpm and not about the texts (DamlcUnavailable);
- what makes two damlc errors the same bug (DamlErrorKey).

Measured with SDK 3.5.2: one `dpm build` costs about 0.7 s plus 9 ms per
module, and a bad module does not stop damlc from checking the others. In the
unit 6 design, the 200 distinct texts of a 2000-input run gave the same 157
failures, with the same first error lines, in one batch as when each was
built alone.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import ClassVar, Final, Literal, TypeAlias

import yaml

BATCH: Final = 500
"""Texts per `dpm build`. 500 modules take about 5 s and 1 GB of memory, and a
Ctrl-C loses at most the batch that is building."""


@dataclass(frozen=True, slots=True)
class DamlSource:
    """One Daml text to build, and the daml.yaml whose settings build it.

    Hashable, so a caller can drop texts it has seen. The first line of `daml`
    is `module <module_name> where`, as forge writes it.
    """

    daml: str
    module_name: str
    daml_yaml: Path


@dataclass(frozen=True, slots=True)
class DamlErrorKey:
    """What makes two damlc errors the same bug: one bad Daml group.

    `text` is the first error line with the parts that come from the input
    replaced by `…`: quoted names, the name and type after "not in scope:",
    the field in "Duplicate field name", file locations, and qualified names.

        Variable not in scope: str : Int -> t  ->  Variable not in scope: …
        Not in scope: ‘float’                  ->  Not in scope: ‘…’

    On the 737 bad texts of a 10-second run, the line as printed gives 398
    groups, and this key gives 28.
    """

    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class DamlError:
    """damlc rejected the text. The first error damlc reported for it.

    `message` is the first line of that error, without the `file:line:col:
    error:` head, as if the text was built alone in its own file:
    "Variable not in scope: str : Int -> t". `stage` is damlc's `Source:`
    field, such as "typecheck" or "parser". `line` is the error's line in the text.
    """

    label: ClassVar[str] = "BAD_DAML"

    message: str
    stage: str
    line: int

    @property
    def key(self) -> DamlErrorKey:
        return DamlErrorKey(_key(self.message))


DamlcVerdict: TypeAlias = Literal["builds", "rejects"] | None
"""damlc's verdict on a Daml text in report.json. None when the run has no damlc, or
when Ctrl-C or a dpm failure stopped damlc before it built the text."""


class DamlcUnavailable(Exception):
    """dpm cannot judge the texts: it is not installed, the SDK in daml.yaml is
    not installed, the daml.yaml is broken, or dpm failed and named no module.
    str() is one line, such as dpm's "... via 'dpm install 3.5.2'"."""


def find_dpm() -> str | None:
    """`dpm` on PATH, else ~/.dpm/bin/dpm, else None."""
    fallback = Path.home() / ".dpm" / "bin" / "dpm"
    return shutil.which("dpm") or (str(fallback) if fallback.is_file() else None)


def need_dpm() -> str:
    """find_dpm(), or DamlcUnavailable when it finds no dpm."""
    dpm = find_dpm()
    if dpm is None:
        raise DamlcUnavailable("dpm not found on PATH or at ~/.dpm/bin/dpm")
    return dpm


def build_daml(sources: Iterable[DamlSource]) -> Iterator[tuple[DamlSource, DamlError | None]]:
    """Build each source with damlc and yield it with its verdict: None when it builds.

    Sources whose daml.yaml settings differ never share a build. The settings
    are the daml.yaml without `name` and `source`, so the four seeds share
    one. Each group is cut into batches of BATCH in the order given, and the
    batches build one after the other. A batch's verdicts are yielded, in the
    order given, when its build ends, so a KeyboardInterrupt loses only the
    batch that is building. Pass each source once.

    Only errors count. A text with warnings only builds.

    Raises DamlcUnavailable (see there), and ValueError when a text does not
    start with `module <module_name> where`.
    """
    dpm = need_dpm()
    by_settings = groupby(
        sorted(enumerate(sources), key=lambda pair: _settings(pair[1].daml_yaml)),
        key=lambda pair: _settings(pair[1].daml_yaml),
    )
    for settings, numbered in by_settings:
        group = [source for _, source in numbered]
        for start in range(0, len(group), BATCH):
            batch = group[start : start + BATCH]
            yield from zip(batch, _build_batch(dpm, settings, batch), strict=True)


def _build_batch(dpm: str, settings: str, batch: list[DamlSource]) -> list[DamlError | None]:
    """One temporary project, one `dpm build`, one verdict per source.

    Source k is written to daml/I<k>/<Module>.daml, and only its first line
    changes, to `module I<k>.<Module> where`. Template names stay, so
    damlc's messages are the ones it gives for the text alone.
    """
    with tempfile.TemporaryDirectory(prefix="damlforge-fuzz-") as temp:
        project = Path(temp)
        config = {**json.loads(settings), "name": "damlforge-fuzz-batch", "source": "daml"}
        (project / "daml.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        for k, source in enumerate(batch):
            folder = project / "daml" / _folder(k)
            folder.mkdir(parents=True)
            text = _in_folder(k, source.daml, source.module_name)
            (folder / f"{source.module_name}.daml").write_text(text, encoding="utf-8")
        returncode, output = _run_dpm(dpm, "build", project)
    verdicts: list[DamlError | None] = [None] * len(batch)
    for k, error in _folder_errors(output).items():
        verdicts[k] = error
    if returncode != 0 and all(verdict is None for verdict in verdicts):
        raise _unavailable("build", returncode, output)
    return verdicts


def _run_dpm(dpm: str, command: str, project: Path) -> tuple[int, str]:
    """`dpm <command>` in `project`: its exit status, and its stdout and stderr together."""
    result = subprocess.run(
        [dpm, command],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )
    return result.returncode, result.stdout + result.stderr


def _folder_errors(output: str) -> dict[int, DamlError]:
    """k -> the first error in daml/I<k>/, for each folder that dpm reports an error in."""
    first: dict[int, DamlError] = {}
    for file, error in _errors(output):
        folder = _FOLDER.match(file)
        if folder is not None:
            first.setdefault(int(folder[1]), error)
    return first


def _unavailable(command: str, returncode: int, output: str) -> DamlcUnavailable:
    """The error for a dpm run that failed and named no module: dpm's own line that says why."""
    lines = [line.strip() for line in _ANSI.sub("", output).splitlines() if line.strip()]
    reason = next((line for line in lines if _FAILURE.search(line)), None)
    return DamlcUnavailable(reason or f"dpm {command} exited with {returncode}")


def _folder(k: int) -> str:
    return f"I{k:05d}"


def _in_folder(k: int, daml: str, module_name: str) -> str:
    """`daml` with its first line changed to `module I<k>.<module_name> where`.

    Raises ValueError when the text does not start with `module <module_name> where`.
    """
    head, newline, rest = daml.partition("\n")
    if head != f"module {module_name} where":
        raise ValueError(f"forge's Daml starts with {head!r}, not module {module_name}")
    return f"module {_folder(k)}.{module_name} where{newline}{rest}"


@functools.cache
def _settings(daml_yaml: Path) -> str:
    """The daml.yaml without `name` and `source`, as canonical JSON: the batch key."""
    config = yaml.safe_load(daml_yaml.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "sdk-version" not in config:
        # Without sdk-version, `dpm build` prints 'unknown command "build"' and exits with 0.
        raise DamlcUnavailable(f"{daml_yaml} has no sdk-version, so dpm cannot build with it")
    config.pop("name", None)
    config.pop("source", None)
    return json.dumps(config, sort_keys=True, default=str)


_ANSI: Final = re.compile(r"\x1b\[[0-9;]*m")
_BLOCK: Final = re.compile(
    r"^File:\s+(?P<file>\S+)\n(?:.*\n)*?Range:\s+(?P<line>\d+):\d+.*\nSource:\s+(?P<stage>.*)\n"
    r"Severity:\s+(?P<severity>\w+)\nMessage:\s*\n(?P<message>(?:(?!File:\s).*\n?)*)",
    re.MULTILINE,
)
"""One diagnostic of dpm's output. `File:` names the module even when the
message names no file, such as "Duplicate field name owner. Original ..."."""
_FOLDER: Final = re.compile(r"(?:\./)?daml/I(\d{5})/")
_FAILURE: Final = re.compile(r"^(?:[A-Z][A-Z_]+:|Error:|damlc:)|ERROR")
"""dpm's line that says why it built nothing: "SDK_NOT_INSTALLED: ... via
'dpm install 3.5.2'", 'Error: unknown command "build"', 'damlc: "Package ... not found'."""
_HEAD: Final = re.compile(r"^\S+:\d+:\d+: (?:error|warning):\s*")
_LOCATION: Final = re.compile(r"(?:\S+/)?(\w+\.daml:\d+:\d+(?:-\d+)?)")
_PREFIX: Final = re.compile(r"\bI\d{5}\.(?=[A-Z])")
_PREAMBLE: Final = "Possible Daml-specific reason for the following type error:"


def _errors(output: str) -> Iterator[tuple[str, DamlError]]:
    """(the File: field, the error) for each DsError block of dpm's output, in output order."""
    for block in _BLOCK.finditer(_ANSI.sub("", output)):
        if block["severity"] == "DsError":
            message = _first_line(block["message"])
            yield block["file"], DamlError(message, block["stage"].strip(), int(block["line"]))


def _first_line(message: str) -> str:
    """The line a person reads, from a block's Message text.

    Drops the `file:line:col: error:` head and the bullet, and skips damlc's
    preamble line. When GHC wrapped the line (it ends with ":"), joins the
    next one. Removes the batch folder from file locations and the `I<k>.`
    module prefix, which the Daml-LF stages print ("choice I00125.Iou:Iou.Currency").
    """
    lines = [_HEAD.sub("", line).strip().lstrip("•").strip() for line in message.splitlines()]
    lines = [line for line in lines if line] or [""]
    if lines[0] == _PREAMBLE and len(lines) > 1:
        lines = lines[1:]
    line = lines[0]
    if line.endswith(":") and len(lines) > 1:
        line = f"{line} {lines[1]}"
    return _PREFIX.sub("", _LOCATION.sub(r"\1", line))


_MASKS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"^(Duplicate field name) \S+?\."), r"\1 …."),
    (re.compile(r"\b\w+\.daml:\d+:\d+(-\d+)?"), "…"),
    # No instance for (IsParties Bool) -> No instance for (IsParties …)
    (re.compile(r"\((\w+) .*$"), r"(\1 …)"),
    # Iou:Iou.Currency
    (re.compile(r"\b[\w.]+:[\w.]+\b"), "…"),
)


def _key(message: str) -> str:
    """DamlErrorKey.text for a first error line.

    Quoted names become ‘…’ first; a quote that the line cuts off ends at the
    line's end. Then, when the text after the first ": " has no quote, it is
    a bare name and its type ("Variable not in scope: str : Int -> t"), so it
    becomes "…". _MASKS run last, in order.
    """
    key = re.sub(r"‘[^’]*(’|$)", "‘…’", message)
    head, colon, rest = key.partition(": ")
    if colon and "‘" not in rest:
        key = f"{head}: …"
    for pattern, replacement in _MASKS:
        key = pattern.sub(replacement, key)
    return key
