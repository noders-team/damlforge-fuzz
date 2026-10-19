"""One run's report: crash groups, totals, a timeline, and the run folder that holds them.

This module imports the compiler, so it loads forge. It owns three decisions:

- which crashes form one group: one CrashKey, one group, ids g01, g02, ...
  in the order of the first input that reached each key;
- the shape of report.json (schema 1). The dataclasses below are the shape:
  their fields are the JSON fields, one for one. to_json() is the only code
  that builds the document, and markdown() reads the same model, so report.md
  shows nothing report.json lacks;
- the layout of a run folder:

      reports/2026-10-19T13-50-00Z/
          report.json
          report.md
          groups/g01/iou.vy      the first input of the group, under the seed's file name
          groups/g01/daml.yaml   a copy of the seed's daml.yaml, when it has one
          groups/g01/shrunk/iou.vy   the shrunk input (see shrinker.shrunk_path)

Time enters a run only here: Report.add reads the clock. fuzz() and the
inputs never see it, so `--count N --random-seed S` gives the same inputs, the
same groups, and the same ids on every machine. Only run.started, timeline,
and first_seen.second differ between two such runs.
"""

from __future__ import annotations

import datetime
import json
import re
import shutil
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Final, Literal

from damlforge_fuzz.compiler import FORGE_VERSION, STAGE_TEXT, Crash, CrashKey, Seed, Stage
from damlforge_fuzz.runner import Count, Limit, Seconds, Totals, Tried
from damlforge_fuzz.shrinker import shrink, shrunk_path

SCHEMA: Final = 1
"""The version of the report.json shape. Raise it when a change breaks readers:
a renamed, removed, or retyped field. Adding a field does not raise it."""


@dataclass(frozen=True, slots=True)
class Run:
    """What was run. Exactly one of `seconds` and `count` is set: the Limit, split for JSON."""

    started: str
    """UTC, to the second: "2026-10-19T13:50:00Z". The run folder's name comes from it."""
    random_seed: int
    seconds: float | None
    count: int | None
    seeds: tuple[str, ...]
    """The seed .vy paths as given, in run order. The order decides the inputs."""
    forge_version: str
    interrupted: bool
    """True when Ctrl-C stopped the run. The report then covers the inputs so far."""


@dataclass(frozen=True, slots=True)
class Tick:
    """The counts after second `second` of the run: every input added before that time.

    Cumulative, so no count goes down from one tick to the next.
    """

    second: int
    inputs: int
    ok: int
    rejected: int
    crash: int
    skipped: int


@dataclass(frozen=True, slots=True)
class FirstSeen:
    second: float
    """Seconds since the run started, rounded to 2 places. Differs between runs."""
    input: int
    """Input.number of the group's first input. The same on every machine."""


@dataclass(slots=True)
class Group:
    """All crashes of one run with one CrashKey.

    The first input that reached the key supplies every field except `count`.
    Later inputs only raise `count`. `stage` and `message` are the first
    input's: forge can reach one key from two stages, and a message can hold
    text from the input. `where` and `seed` are strings because this class is
    the JSON row; the typed key is the key of Report.groups.
    """

    id: str
    kind: Literal["crash"]
    exception: str
    where: str | None
    """"forge/ir/lower.py:289", or None for RecursionError and MemoryError."""
    stage: Stage
    message: str
    count: int
    first_seen: FirstSeen
    seed: str
    """The seed path as given, such as "contracts/iou/iou.vy"."""
    input: str
    """The full text of the first input."""
    input_file: str
    """Where write() saves `input`, relative to the run folder: "groups/g01/iou.vy"."""
    shrunk: str | None = None
    """The shortest text the shrinker found by deleting lines of `input` that
    still crashes in this group. Its lines are a subsequence of `input`'s lines.
    None only when Ctrl-C stopped the shrinking before this group."""
    shrunk_file: str | None = None
    """Where write() saves `shrunk`: "groups/g01/shrunk/iou.vy". None exactly when `shrunk` is None."""


@dataclass(slots=True)
class Report:
    """The accumulator the run loop feeds, and the model report.json serializes.

    Invariants after every add():

    - totals.crash == sum(group.count for group in groups.values());
    - groups is in first-seen order, which is input-number order, and the
      ids are g01, g02, ... in that order;
    - timeline holds one Tick for each whole second that has passed, seconds
      1, 2, ... with no gap. to_json() adds the final partial second, so the
      document's last tick always equals its totals.

    The run loop and shrink() are the only writers. Make one with Report.open.
    """

    run: Run
    folder: Path
    """The run folder. open() creates it, write() fills it."""
    totals: Totals = field(default_factory=Totals)
    timeline: list[Tick] = field(default_factory=list)
    groups: dict[CrashKey, Group] = field(default_factory=dict)
    _start: float = field(default_factory=time.monotonic, repr=False)
    _seeds: dict[str, Seed] = field(default_factory=dict, repr=False)
    """Group.seed -> the Seed, so write() can copy its daml.yaml."""

    @classmethod
    def open(
        cls, seeds: Sequence[Seed], random_seed: int, limit: Limit, reports: Path
    ) -> Report:
        """Start the clock and create the run folder under `reports`, before input 1.

        The folder is named after run.started with `-` for `:`, which Windows
        forbids in file names: reports/2026-10-19T13-50-00Z. When that folder
        exists, -2, -3, ... is added. mkdir picks the name, so two runs in one
        second never share a folder.

        Raises OSError when the folder cannot be made, for example when
        `reports` is a file. A bad path then fails before any input runs.
        """
        started = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
        match limit:
            case Count(n):
                seconds, count = None, n
            case Seconds(s):
                seconds, count = s, None
        run = Run(
            started,
            random_seed,
            seconds,
            count,
            tuple(str(seed.path) for seed in seeds),
            FORGE_VERSION,
            interrupted=False,
        )
        reports.mkdir(parents=True, exist_ok=True)
        name = started.replace(":", "-")
        folder = reports / name
        suffix = 1
        while True:
            try:
                folder.mkdir()
                break
            except FileExistsError:
                suffix += 1
                folder = reports / f"{name}-{suffix}"
        return cls(run, folder)

    def add(self, tried: Tried) -> None:
        """Count `tried`, close every whole second before it, and group it if it crashed."""
        elapsed = time.monotonic() - self._start
        while len(self.timeline) < int(elapsed):
            self.timeline.append(Tick(len(self.timeline) + 1, **asdict(self.totals)))
        self.totals.add(tried)
        if not isinstance(crash := tried.outcome, Crash):
            return
        group = self.groups.get(crash.key)
        if group is None:
            group_id = f"g{len(self.groups) + 1:02d}"
            seed = str(tried.seed.path)
            self._seeds[seed] = tried.seed
            group = self.groups[crash.key] = Group(
                id=group_id,
                kind="crash",
                exception=crash.exception,
                where=None if crash.where is None else str(crash.where),
                stage=crash.stage,
                message=crash.message,
                count=0,
                first_seen=FirstSeen(round(elapsed, 2), tried.input.number),
                seed=seed,
                input=tried.input.text,
                input_file=f"groups/{group_id}/{tried.seed.path.name}",
            )
        group.count += 1

    def interrupt(self) -> None:
        """Mark the run as stopped by Ctrl-C."""
        self.run = replace(self.run, interrupted=True)

    def shrink(self) -> None:
        """Shrink each group that has no shrunk input yet, in group order.

        Each group shrinks with the run's own Seed and the group's key, so the
        shrinker compiles exactly as the run did. shrunk and shrunk_file are
        set together after shrink() returns, so a Ctrl-C in the middle of a
        group leaves that group untouched. A second call finishes the groups
        that a Ctrl-C skipped. KeyboardInterrupt propagates to the caller.
        """
        for key, group in self.groups.items():
            if group.shrunk is None:
                text = shrink(group.input, self._seeds[group.seed], key)
                group.shrunk = text
                group.shrunk_file = str(shrunk_path(PurePosixPath(group.input_file)))

    def to_json(self) -> dict[str, Any]:
        """The report.json document. The only code that builds its shape. Pure."""
        timeline = list(self.timeline)
        final = Tick(len(timeline) + 1, **asdict(self.totals))
        if not timeline or replace(timeline[-1], second=final.second) != final:
            timeline.append(final)
        return {
            "schema": SCHEMA,
            "run": asdict(self.run),
            "totals": asdict(self.totals),
            "timeline": [asdict(tick) for tick in timeline],
            "groups": [asdict(group) for group in self.groups.values()],
        }

    def markdown(self) -> str:
        """report.md: the run settings, the totals, one table row per group, the
        stages those groups crashed in, and each shrunk input."""
        run, totals = self.run, self.totals
        if run.count is not None:
            limit = f"{run.count} inputs"
        else:
            limit = f"{int(run.seconds) if run.seconds.is_integer() else run.seconds} seconds"
        lines = [
            f"# damlforge-fuzz run {run.started}",
            "",
            f"- Random seed: {run.random_seed}",
            f"- Limit: {limit}",
            f"- Seeds: {', '.join(f'`{seed}`' for seed in run.seeds)}",
            f"- DamlForge: {run.forge_version}",
        ]
        if run.interrupted:
            lines.append("- Stopped early by Ctrl-C. The report covers the inputs so far.")
        lines += [
            "",
            "## Totals",
            "",
            f"{totals.inputs} inputs: {totals.ok} OK, {totals.rejected} rejected, "
            f"{totals.crash} crash, {totals.skipped} skipped.",
            "",
            f"## {len(self.groups)} crash group{'' if len(self.groups) == 1 else 's'}",
        ]
        if self.groups:
            lines += [
                "",
                "| Group | Count | Exception | Stage | Seed | First seen | Input | Shrunk |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        for group in self.groups.values():
            cells = [
                group.id,
                str(group.count),
                _exception_at(group),
                group.stage,
                group.seed,
                f"input {group.first_seen.input}, {group.first_seen.second} s",
                f"[{Path(group.input_file).name}]({group.input_file})",
                _shrunk_cell(group),
            ]
            lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
        present = {group.stage for group in self.groups.values()}
        if present:
            lines += ["", "## Stages", ""]
            lines += [f"- `{stage}`: {STAGE_TEXT[stage]}" for stage in Stage if stage in present]
            lines += [
                "",
                "The stage is the step that was running, not the folder of the forge file, "
                "so a crash can have stage `check` and a line in `forge/ir/lower.py`.",
            ]
        shrunk = [group for group in self.groups.values() if group.shrunk is not None]
        if shrunk:
            lines += ["", "## Shrunk inputs"]
        for group in shrunk:
            # One backtick more than the longest run in the text, so the text cannot end the block.
            fence = "`" * max([3, *(len(run) + 1 for run in re.findall("`+", group.shrunk))])
            lines += ["", f"### {group.id}: {_exception_at(group)}", "", f"{fence}python"]
            lines += [group.shrunk.rstrip("\n"), fence]
        return "\n".join(lines) + "\n"

    def write(self) -> None:
        """Write groups/, report.md, and report.json into the run folder.

        Idempotent: groups/ is removed first, so writing again leaves no stale
        group folder. report.json is written last, so a folder that has it is
        complete.

        Raises OSError when a file cannot be written.
        """
        groups = self.folder / "groups"
        if groups.exists():
            shutil.rmtree(groups)
        for group in self.groups.values():
            saved = self.folder / group.input_file
            saved.parent.mkdir(parents=True)
            saved.write_text(group.input, encoding="utf-8", newline="")
            daml_yaml = self._seeds[group.seed].daml_yaml
            if daml_yaml is not None:
                shutil.copyfile(daml_yaml, saved.parent / "daml.yaml")
            if group.shrunk_file is not None:
                shrunk = self.folder / group.shrunk_file
                shrunk.parent.mkdir()
                shrunk.write_text(group.shrunk, encoding="utf-8", newline="")
        (self.folder / "report.md").write_text(self.markdown(), encoding="utf-8")
        document = json.dumps(self.to_json(), indent=2, ensure_ascii=False) + "\n"
        (self.folder / "report.json").write_text(document, encoding="utf-8")


def _exception_at(group: Group) -> str:
    """'KeyError at forge/ir/lower.py:289', or 'RecursionError' when there is no forge line."""
    return group.exception if group.where is None else f"{group.exception} at {group.where}"


def _shrunk_cell(group: Group) -> str:
    """'[3 of 42 lines](groups/g02/shrunk/escrow.vy)', or 'not shrunk'."""
    if group.shrunk is None:
        return "not shrunk"
    total = len(group.input.splitlines())
    lines = f"{len(group.shrunk.splitlines())} of {total} line{'' if total == 1 else 's'}"
    return f"[{lines}]({group.shrunk_file})"


def _now() -> datetime.datetime:
    """Now, in UTC. Tests replace it to make two runs start in one second."""
    return datetime.datetime.now(datetime.UTC)
