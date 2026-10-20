"""One run's report: crash groups, totals, a timeline, and the run folder that holds them.

This module imports the compiler, so it loads forge. It owns three decisions:

- which crashes form one group: one CrashKey, one group, ids g01, g02, ...
  in the order of the first input that reached each key. With damlc, which
  bad Daml forms one group: one DamlErrorKey, ids d01, d02, ... in the same order.
  Which OK inputs with loop bugs form one group: the first loop check and,
  with damlc, damlc's verdict on the Daml, ids l01, l02, ... in the same order.
  With compare, which OK inputs whose Daml runs differently from the .vy
  code form one group: the difference kind and the first loop check, ids
  r01, r02, ... in the same order;
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
          groups/d01/iou.vy      the first input whose Daml damlc rejects with the group's key
          groups/d01/daml.yaml   a copy of the seed's daml.yaml
          groups/d01/Iou.daml    forge's Daml for that input, so `dpm build` in d01 shows the error
          groups/l01/loop_give.vy    the first input of the loop group
          groups/l01/daml.yaml       a copy of the seed's daml.yaml, when it has one
          groups/l01/LoopGive.daml   forge's Daml for that input
          groups/l01/shrunk/loop_give.vy    the shrunk input
          groups/l01/shrunk/LoopGive.daml   forge's Daml for the shrunk input
          groups/r01/loop_give.vy          the first input of the run group
          groups/r01/loop_give.calls.yaml  a copy of the seed's calls file
          groups/r01/daml.yaml             the seed's, with daml-script and `source: daml`
          groups/r01/daml/LoopGive.daml    forge's Daml for that input
          groups/r01/daml/Test.daml        its scripts, so `dpm test` in r01 shows the difference

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

from damlforge_fuzz.compare import (
    Calls,
    Compared,
    CompareInput,
    DifferenceKind,
    Dropped,
    InputResult,
    Skipped,
    calls_path,
    group_daml_yaml,
    run_and_compare,
)
from damlforge_fuzz.compiler import (
    FORGE_VERSION,
    STAGE_TEXT,
    Crash,
    CrashKey,
    Ok,
    Seed,
    Stage,
    compile_and_sort,
)
from damlforge_fuzz.damlc import DamlcVerdict, DamlError, DamlErrorKey, DamlSource, build_daml
from damlforge_fuzz.loopcheck import LOOP_CHECK_TEXT, LoopBug, LoopCheck
from damlforge_fuzz.runner import Count, Limit, Seconds, Totals, Tried
from damlforge_fuzz.shrinker import same_crash, same_loop, shrink, shrunk_path

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
class BadDamlGroup:
    """All OK inputs whose Daml damlc rejects with one DamlErrorKey.

    The group's first input, the lowest input number, supplies every field
    except `count`. Not shrunk: each shrink candidate would need its own
    `dpm build`, about 0.7 s.
    """

    id: str
    """"d01", "d02", ... in first-input order. A series of its own, so a new
    crash group does not move these ids."""
    kind: Literal["bad_daml"]
    key: str
    """The DamlErrorKey: "Variable not in scope: …"."""
    message: str
    """damlc's first error line for the first input: "Variable not in scope: str : Int -> t"."""
    damlc_stage: str
    """damlc's Source field, such as "typecheck" or "parser"."""
    daml_line: int
    """The line of the error in `daml`."""
    count: int
    """OK inputs whose Daml damlc rejects with this key."""
    first_seen: FirstSeen
    seed: str
    input: str
    input_file: str
    """"groups/d01/iou.vy", with a copy of the seed's daml.yaml next to it."""
    daml: str
    """forge's Daml for `input`."""
    daml_file: str
    """"groups/d01/Iou.daml". `dpm build` in groups/d01 shows the error again."""


@dataclass(slots=True)
class LoopGroup:
    """All OK inputs whose first loop check is `check` and whose Daml damlc judges the same way.

    Without damlc, `damlc` is None for every input, so there is one group per
    check. The group's first input, the lowest input number, supplies every
    field except `count` and the four shrunk fields.
    """

    id: str
    """"l01", "l02", ... in first-input order. A series of its own, like d01."""
    kind: Literal["bad_loop"]
    check: LoopCheck
    """The first check that the first input fails."""
    checks: list[LoopCheck]
    """Every check that the first input fails, in check order. checks[0] == check."""
    message: str
    """The first input's LoopBug.detail for `check`."""
    daml_line: int
    """The line in `daml` that `message` names."""
    damlc: DamlcVerdict
    """The same for every input of the group, because it is part of the group key."""
    damlc_error: str | None
    """damlc's first error line for `daml` when `damlc` is "rejects", else None."""
    count: int
    """OK inputs in this group."""
    first_seen: FirstSeen
    seed: str
    input: str
    input_file: str
    """"groups/l01/loop_give.vy", with a copy of the seed's daml.yaml next to it when it has one."""
    daml: str
    """forge's Daml for `input`."""
    daml_file: str
    """"groups/l01/LoopGive.daml". `damlforge-fuzz check` on input_file prints BAD_LOOP
    with the same checks again."""
    shrunk: str | None = None
    """The shortest text the shrinker found by deleting lines of `input` that
    still has `check` as its first check and, when `damlc` is not None, the
    same damlc verdict. Its lines are a subsequence of `input`'s lines. The
    four shrunk fields are None together, only when Ctrl-C or a dpm failure
    stopped the shrinking before this group."""
    shrunk_file: str | None = None
    """Where write() saves `shrunk`: "groups/l01/shrunk/loop_give.vy"."""
    shrunk_daml: str | None = None
    """forge's Daml for `shrunk`."""
    shrunk_daml_file: str | None = None
    """"groups/l01/shrunk/LoopGive.daml"."""


@dataclass(slots=True)
class RunGroup:
    """All compared inputs whose first difference has one kind and whose first loop check is one.

    The loop check is in the key, so inputs that a loop check already names,
    such as L3, do not hide the inputs that only the run shows. The group's
    first input, the lowest input number, supplies every field except `count`.
    Not shrunk: each shrink candidate would need its own `dpm test`, seconds.
    """

    id: str
    """"r01", "r02", ... in first-input order. A series of its own, like d01."""
    kind: Literal["bad_run"]
    difference: DifferenceKind
    call: str
    """The first call that differs, as "Iou.GiveAll #1": the call's place in the calls file."""
    loop_check: LoopCheck | None
    """The first loop check that the input fails, or None."""
    python: str
    """What Python does in that call: "returns None, makes 1 contract: Iou(...)" or
    "fails: positive"."""
    count: int
    """OK inputs in this group."""
    first_seen: FirstSeen
    seed: str
    input: str
    input_file: str
    """"groups/r01/loop_give.vy". `damlforge-fuzz check --compare` on it prints BAD_RUN again."""
    calls_file: str
    """"groups/r01/loop_give.calls.yaml", a copy of the seed's calls file."""
    daml: str
    """forge's Daml for `input`."""
    daml_file: str
    """"groups/r01/daml/LoopGive.daml"."""
    test: str
    """The Daml Script module with the scripts of `input`'s calls."""
    test_file: str
    """"groups/r01/daml/Test.daml". `dpm test` in groups/r01 fails the script of `call`."""


@dataclass(frozen=True, slots=True)
class CompareSummary:
    """report.json "compare": what the compare step did. None when the run had no --compare.

    Each count is of OK inputs of the seeds with a calls file, and the step
    runs each distinct .vy text once. compared + skipped + dropped is all of
    them, unless Ctrl-C (interrupted) or a dpm failure stopped the step.
    differ == sum(group.count for the run groups).
    """

    compared: int
    skipped: int
    """Inputs with no call that Python could run and compare."""
    dropped: int
    """Inputs whose Daml or test module damlc rejects."""
    differ: int
    skipped_calls: int
    """Calls of the compared inputs that were not compared."""
    seconds: float
    interrupted: bool


@dataclass(frozen=True, slots=True)
class DamlcSummary:
    """report.json "damlc": what the damlc step did. None when the run had no --damlc.

    checked_texts counts the distinct Daml texts of OK inputs that damlc built;
    fewer than all only after Ctrl-C (interrupted) or a dpm failure.
    bad_inputs == sum(group.count for the bad Daml groups).
    """

    checked_texts: int
    bad_texts: int
    bad_inputs: int
    seconds: float
    interrupted: bool


@dataclass(slots=True)
class _DamlText:
    """One distinct Daml text of the run's OK inputs, and the first input that made it."""

    first_seen: FirstSeen
    seed: str
    input: str
    count: int = 0


@dataclass(slots=True)
class _Damlc:
    """The damlc step's state. add() is the only writer of texts, check_daml() of the rest."""

    texts: dict[DamlSource, _DamlText] = field(default_factory=dict)
    """In first-seen order, which is input-number order."""
    verdicts: dict[DamlSource, DamlError | None] = field(default_factory=dict)
    seconds: float = 0.0
    interrupted: bool = False


@dataclass(frozen=True, slots=True)
class _LoopText:
    """One Daml text of one seed and the first loop check of its input: a key of Report._loops.

    `check` is in the key because L3 also reads the .vy text, so two inputs
    with one Daml text can fail different checks.
    """

    seed: str
    daml: str
    check: LoopCheck


@dataclass(slots=True)
class _RunInput:
    """One distinct .vy text of a seed with calls: its first OK input, and how many there are."""

    first_seen: FirstSeen
    ok: Ok
    count: int = 0


@dataclass(slots=True)
class _Compare:
    """The compare step's state. add() is the only writer of inputs, run_and_compare() of
    the rest."""

    calls: dict[str, Calls]
    """The seeds with a calls file, by Group.seed."""
    inputs: dict[tuple[str, str], _RunInput] = field(default_factory=dict)
    """(seed, .vy text) -> its inputs, in first-seen order."""
    results: dict[tuple[str, str], InputResult] = field(default_factory=dict)
    seconds: float = 0.0
    interrupted: bool = False


@dataclass(frozen=True, slots=True)
class _Shrunk:
    """A loop group's shrunk input and forge's Daml for it. One object, so both are set at once."""

    vy: str
    daml: str


@dataclass(slots=True)
class _LoopInputs:
    """The OK inputs with one _LoopText: the first of them, and how many there are."""

    first_seen: FirstSeen
    input: str
    module_name: str
    bugs: tuple[LoopBug, ...]
    count: int = 0
    shrunk: _Shrunk | None = None


@dataclass(slots=True)
class Report:
    """The accumulator the run loop feeds, and the model report.json serializes.

    Invariants after every add():

    - totals.crash == sum(group.count for group in groups.values());
    - groups is in first-seen order, which is input-number order, and the
      ids are g01, g02, ... in that order;
    - with damlc, every distinct Daml text of an OK input is in _damlc.texts;
    - every OK input with loop bugs is counted in _loops, with or without damlc;
    - timeline holds one Tick for each whole second that has passed, seconds
      1, 2, ... with no gap. to_json() adds the final partial second, so the
      document's last tick always equals its totals.

    The run loop, check_daml(), and shrink() are the only writers. Make one with Report.open.
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
    _damlc: _Damlc | None = field(default=None, repr=False)
    """None when the run has no damlc step. Then the report is unit 5's, with "damlc": null."""
    _loops: dict[_LoopText, _LoopInputs] = field(default_factory=dict, repr=False)
    """The OK inputs with loop bugs, in first-seen order. loop_groups() reads it."""
    _compare: _Compare | None = field(default=None, repr=False)
    """None when the run has no compare step. Then report.json has "compare": null."""

    @classmethod
    def open(
        cls,
        seeds: Sequence[Seed],
        random_seed: int,
        limit: Limit,
        reports: Path,
        damlc: bool = False,
        compare: dict[str, Calls] | None = None,
    ) -> Report:
        """Start the clock and create the run folder under `reports`, before input 1.

        With `damlc`, add() keeps each distinct Daml text of an OK input for
        check_daml(). Every seed then needs a daml.yaml.

        With `compare`, the calls of each seed that has a calls file, by seed
        path as given, add() keeps each distinct .vy text of an OK input of
        those seeds for run_and_compare(). Those seeds need a daml.yaml.

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
        return cls(
            run,
            folder,
            _damlc=_Damlc() if damlc else None,
            _compare=None if compare is None else _Compare(dict(compare)),
        )

    def add(self, tried: Tried) -> None:
        """Count `tried`, close every whole second before it, and group it if it crashed.

        With damlc, an OK input's Daml text is kept, once per distinct text. An
        OK input with loop bugs is kept once per Daml text and first check.
        With compare, an OK input of a seed with calls is kept once per .vy text.
        """
        elapsed = time.monotonic() - self._start
        while len(self.timeline) < int(elapsed):
            self.timeline.append(Tick(len(self.timeline) + 1, **asdict(self.totals)))
        self.totals.add(tried)
        if isinstance(ok := tried.outcome, Ok) and self._damlc is not None:
            source = DamlSource(ok.daml, ok.module_name, tried.seed.daml_yaml)
            text = self._damlc.texts.get(source)
            if text is None:
                seed = str(tried.seed.path)
                self._seeds[seed] = tried.seed
                text = self._damlc.texts[source] = _DamlText(
                    FirstSeen(round(elapsed, 2), tried.input.number), seed, tried.input.text
                )
            text.count += 1
        if isinstance(ok, Ok) and ok.loop_bugs:
            seed = str(tried.seed.path)
            key = _LoopText(seed, ok.daml, ok.loop_key)
            kept = self._loops.get(key)
            if kept is None:
                self._seeds[seed] = tried.seed
                kept = self._loops[key] = _LoopInputs(
                    FirstSeen(round(elapsed, 2), tried.input.number),
                    tried.input.text,
                    ok.module_name,
                    ok.loop_bugs,
                )
            kept.count += 1
        if isinstance(ok, Ok) and self._compare is not None:
            seed = str(tried.seed.path)
            if seed in self._compare.calls:
                self._seeds[seed] = tried.seed
                run = self._compare.inputs.setdefault(
                    (seed, tried.input.text),
                    _RunInput(FirstSeen(round(elapsed, 2), tried.input.number), ok),
                )
                run.count += 1
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
        """Shrink each group that has no shrunk input yet: the crash groups, then
        the loop groups, each in id order.

        Each group shrinks with the run's own Seed, so the shrinker compiles
        exactly as the run did. A crash group keeps its CrashKey. A loop group
        keeps its first check and its damlc verdict, so call check_daml()
        first. With a verdict, damlc builds the Daml of the candidates that
        keep the check, once per Daml text: a few seconds per group. Without
        one, a loop group shrinks by the check only.

        A group's shrunk fields are set together after its shrink returns, so
        a Ctrl-C in the middle of a group leaves that group untouched. A second
        call finishes the groups that a Ctrl-C skipped. KeyboardInterrupt and
        DamlcUnavailable propagate to the caller.
        """
        for key, group in self.groups.items():
            if group.shrunk is None:
                text = shrink(group.input, self._seeds[group.seed], same_crash(key))
                group.shrunk = text
                group.shrunk_file = str(shrunk_path(PurePosixPath(group.input_file)))
        for loop in self.loop_groups():
            kept = self._loops[_LoopText(loop.seed, loop.daml, loop.check)]
            if kept.shrunk is None:
                seed = self._seeds[loop.seed]
                text = shrink(loop.input, seed, same_loop(loop.check, loop.damlc, seed))
                daml = loop.daml if text == loop.input else compile_and_sort(text, seed).daml
                kept.shrunk = _Shrunk(text, daml)

    def check_daml(self) -> None:
        """Build with damlc every kept Daml text that has no verdict yet, in first-seen order.

        Each verdict is stored as its batch ends, so a Ctrl-C keeps the
        finished batches, marks the step interrupted, and propagates. A second
        call builds only the rest. Raises DamlcUnavailable as build_daml does.
        Does nothing without damlc.
        """
        if self._damlc is None:
            return
        damlc = self._damlc
        start = time.monotonic()
        try:
            todo = [source for source in damlc.texts if source not in damlc.verdicts]
            for source, verdict in build_daml(todo):
                damlc.verdicts[source] = verdict
        except KeyboardInterrupt:
            damlc.interrupted = True
            raise
        finally:
            damlc.seconds += time.monotonic() - start

    def run_and_compare(self) -> None:
        """Compare every kept .vy text that has no result yet, in first-seen order.

        With damlc, the compare step reuses damlc's verdicts, so call
        check_daml() first. Each result is stored as its batch ends, so a
        Ctrl-C keeps the finished batches, marks the step interrupted, and
        propagates. A second call compares only the rest. Raises
        DamlcUnavailable as run_and_compare in compare.py does. Does nothing
        without compare.
        """
        if self._compare is None:
            return
        state = self._compare
        start = time.monotonic()
        try:
            todo = {
                key: CompareInput(key[1], run.ok, self._seeds[key[0]], state.calls[key[0]])
                for key, run in state.inputs.items()
                if key not in state.results
            }
            verdicts = None if self._damlc is None else self._damlc.verdicts
            for key, result in run_and_compare(todo, verdicts):
                state.results[key] = result
        except KeyboardInterrupt:
            state.interrupted = True
            raise
        finally:
            state.seconds += time.monotonic() - start

    @property
    def compare(self) -> CompareSummary | None:
        if self._compare is None:
            return None
        state = self._compare
        counts = {"compared": 0, "skipped": 0, "dropped": 0, "differ": 0, "skipped_calls": 0}
        for key, result in state.results.items():
            count = state.inputs[key].count
            match result:
                case Compared(difference=difference, skipped=skipped):
                    counts["compared"] += count
                    counts["differ"] += count if difference is not None else 0
                    counts["skipped_calls"] += count * len(skipped)
                case Skipped():
                    counts["skipped"] += count
                case Dropped():
                    counts["dropped"] += count
        return CompareSummary(
            **counts, seconds=round(state.seconds, 2), interrupted=state.interrupted
        )

    @property
    def damlc(self) -> DamlcSummary | None:
        if self._damlc is None:
            return None
        bad = [source for source, verdict in self._damlc.verdicts.items() if verdict is not None]
        return DamlcSummary(
            checked_texts=len(self._damlc.verdicts),
            bad_texts=len(bad),
            bad_inputs=sum(self._damlc.texts[source].count for source in bad),
            seconds=round(self._damlc.seconds, 2),
            interrupted=self._damlc.interrupted,
        )

    def bad_daml_groups(self) -> list[BadDamlGroup]:
        """One group per DamlErrorKey of the checked texts, ids d01, d02, ... in first-input order.

        Derived from the texts and their verdicts on every call, so
        report.json, report.md, and the group folders cannot disagree.
        """
        if self._damlc is None:
            return []
        groups: dict[DamlErrorKey, BadDamlGroup] = {}
        for source, text in self._damlc.texts.items():
            if (error := self._damlc.verdicts.get(source)) is None:
                continue
            group = groups.get(error.key)
            if group is None:
                group_id = f"d{len(groups) + 1:02d}"
                folder = f"groups/{group_id}"
                group = groups[error.key] = BadDamlGroup(
                    id=group_id,
                    kind="bad_daml",
                    key=str(error.key),
                    message=error.message,
                    damlc_stage=error.stage,
                    daml_line=error.line,
                    count=0,
                    first_seen=text.first_seen,
                    seed=text.seed,
                    input=text.input,
                    input_file=f"{folder}/{Path(text.seed).name}",
                    daml=source.daml,
                    daml_file=f"{folder}/{source.module_name}.daml",
                )
            group.count += text.count
        return list(groups.values())

    def loop_groups(self) -> list[LoopGroup]:
        """One group per first loop check and damlc verdict, ids l01, l02, ... in first-input order.

        Without damlc the verdict is None, so there is at most one group per
        check. Derived on every call, like bad_daml_groups(), so report.json,
        report.md, the group folders, and the run's lines cannot disagree.
        """
        groups: dict[tuple[LoopCheck, DamlcVerdict], LoopGroup] = {}
        for key, kept in self._loops.items():
            verdict, error = self._damlc_verdict(key.seed, key.daml, kept.module_name)
            group = groups.get((key.check, verdict))
            if group is None:
                group_id = f"l{len(groups) + 1:02d}"
                folder = f"groups/{group_id}"
                first = kept.bugs[0]
                group = groups[(key.check, verdict)] = LoopGroup(
                    id=group_id,
                    kind="bad_loop",
                    check=key.check,
                    checks=[bug.check for bug in kept.bugs],
                    message=first.detail,
                    daml_line=first.daml_line,
                    damlc=verdict,
                    damlc_error=error,
                    count=0,
                    first_seen=kept.first_seen,
                    seed=key.seed,
                    input=kept.input,
                    input_file=f"{folder}/{Path(key.seed).name}",
                    daml=key.daml,
                    daml_file=f"{folder}/{kept.module_name}.daml",
                )
                if kept.shrunk is not None:
                    group.shrunk, group.shrunk_daml = kept.shrunk.vy, kept.shrunk.daml
                    group.shrunk_file = str(shrunk_path(PurePosixPath(group.input_file)))
                    group.shrunk_daml_file = str(shrunk_path(PurePosixPath(group.daml_file)))
            group.count += kept.count
        return list(groups.values())

    def run_groups(self) -> list[RunGroup]:
        """One group per difference kind and first loop check, ids r01, r02, ... by first input.

        Derived on every call, like loop_groups(), so report.json, report.md,
        the group folders, and the run's lines cannot disagree.
        """
        if self._compare is None:
            return []
        groups: dict[tuple[DifferenceKind, LoopCheck | None], RunGroup] = {}
        for key, run in self._compare.inputs.items():
            result = self._compare.results.get(key)
            if not isinstance(result, Compared) or result.difference is None:
                continue
            difference = result.difference
            group = groups.get((difference.kind, run.ok.loop_key))
            if group is None:
                group_id = f"r{len(groups) + 1:02d}"
                folder = f"groups/{group_id}"
                seed = Path(key[0])
                group = groups[(difference.kind, run.ok.loop_key)] = RunGroup(
                    id=group_id,
                    kind="bad_run",
                    difference=difference.kind,
                    call=difference.call,
                    loop_check=run.ok.loop_key,
                    python=difference.python,
                    count=0,
                    first_seen=run.first_seen,
                    seed=key[0],
                    input=key[1],
                    input_file=f"{folder}/{seed.name}",
                    calls_file=f"{folder}/{calls_path(seed).name}",
                    daml=run.ok.daml,
                    daml_file=f"{folder}/daml/{run.ok.module_name}.daml",
                    test=difference.test,
                    test_file=f"{folder}/daml/Test.daml",
                )
            group.count += run.count
        return list(groups.values())

    def _damlc_verdict(
        self, seed: str, daml: str, module_name: str
    ) -> tuple[DamlcVerdict, str | None]:
        """damlc's verdict on one Daml text, and its first error line when it rejects the text.

        Read from the damlc step's verdicts, with no build of its own: every OK
        text is in _damlc.texts. (None, None) without damlc, and for a text that
        Ctrl-C or a dpm failure left unbuilt.
        """
        if self._damlc is None:
            return None, None
        source = DamlSource(daml, module_name, self._seeds[seed].daml_yaml)
        if source not in self._damlc.verdicts:
            return None, None
        error = self._damlc.verdicts[source]
        return ("builds", None) if error is None else ("rejects", error.message)

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
            "damlc": None if self.damlc is None else asdict(self.damlc),
            "compare": None if self.compare is None else asdict(self.compare),
            "groups": [
                asdict(g)
                for g in [
                    *self.groups.values(),
                    *self.bad_daml_groups(),
                    *self.loop_groups(),
                    *self.run_groups(),
                ]
            ],
        }

    def markdown(self) -> str:
        """report.md: the run settings, the totals, one table row per group, the
        stages those groups crashed in, each shrunk input, and the loop check."""
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
            lines += ["", f"### {group.id}: {_exception_at(group)}", ""]
            lines += _code_block(group.shrunk, "python")
        if self.damlc is not None:
            lines += self._damlc_markdown(self.damlc)
        lines += self._loops_markdown()
        if self.compare is not None:
            lines += self._compare_markdown(self.compare)
        return "\n".join(lines) + "\n"

    def _damlc_markdown(self, damlc: DamlcSummary) -> list[str]:
        groups = self.bad_daml_groups()
        lines = [
            "",
            "## Bad Daml",
            "",
            BAD_DAML_TEXT,
            "",
            f"damlc built {damlc.checked_texts} distinct Daml text"
            f"{'' if damlc.checked_texts == 1 else 's'} of the OK inputs in {damlc.seconds} s. "
            f"It rejected {damlc.bad_texts}, which {damlc.bad_inputs} OK input"
            f"{' has' if damlc.bad_inputs == 1 else 's have'}.",
        ]
        if damlc.interrupted:
            lines.append("Ctrl-C stopped damlc, so some texts were not built.")
        lines += ["", f"## {len(groups)} bad Daml group{'' if len(groups) == 1 else 's'}"]
        if groups:
            lines += [
                "",
                "| Group | Count | damlc error | damlc stage | Seed | First seen | Input | Daml |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        for group in groups:
            cells = [
                group.id,
                str(group.count),
                group.key,
                group.damlc_stage,
                group.seed,
                f"input {group.first_seen.input}, {group.first_seen.second} s",
                f"[{Path(group.input_file).name}]({group.input_file})",
                f"[{Path(group.daml_file).name}]({group.daml_file})",
            ]
            lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
        if groups:
            lines += ["", "### First error lines", ""]
            lines += [
                f"- {group.id}, {Path(group.daml_file).name} line {group.daml_line}: "
                f"{_inline_code(group.message)}"
                for group in groups
            ]
        return lines

    def _loops_markdown(self) -> list[str]:
        groups = self.loop_groups()
        inputs = sum(group.count for group in groups)
        present = {check for group in groups for check in group.checks}
        lines = [
            "",
            "## Loop check",
            "",
            BAD_LOOP_TEXT,
            "",
            f"{inputs} OK input{' has' if inputs == 1 else 's have'} loop bugs.",
        ]
        if present:
            lines.append("")
            lines += [
                f"- `{check}`: {LOOP_CHECK_TEXT[check]}" for check in LoopCheck if check in present
            ]
        lines += ["", f"## {len(groups)} loop group{'' if len(groups) == 1 else 's'}"]
        if groups:
            lines += [
                "",
                "| Group | Check | Checks | Count | damlc | Seed | First seen | Input | Daml "
                "| Shrunk |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        for group in groups:
            if self._damlc is None:
                damlc = "-"
            else:
                damlc = group.damlc or "not built"
            cells = [
                group.id,
                group.check,
                " ".join(group.checks),
                str(group.count),
                damlc,
                group.seed,
                f"input {group.first_seen.input}, {group.first_seen.second} s",
                f"[{Path(group.input_file).name}]({group.input_file})",
                f"[{Path(group.daml_file).name}]({group.daml_file})",
                _shrunk_cell(group),
            ]
            lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
        if groups:
            lines += ["", "### Loop bugs", ""]
            for group in groups:
                line = (
                    f"- {group.id}, {Path(group.daml_file).name} line {group.daml_line}: "
                    f"{_inline_code(group.message)}"
                )
                if group.damlc_error is not None:
                    line += f". damlc: {_inline_code(group.damlc_error)}"
                lines.append(line)
        shrunk = [group for group in groups if group.shrunk is not None]
        if shrunk:
            lines += ["", "## Shrunk loop inputs"]
        for group in shrunk:
            verdict = "" if group.damlc is None else f", damlc {group.damlc}"
            lines += ["", f"### {group.id}: {group.check}{verdict}", ""]
            lines += _code_block(group.shrunk, "python") + [""]
            lines += _code_block(group.shrunk_daml, "daml")
        return lines

    def _compare_markdown(self, compare: CompareSummary) -> list[str]:
        groups = self.run_groups()
        lines = [
            "",
            "## Run and compare",
            "",
            BAD_RUN_TEXT,
            "",
            f"The run compared {_plural(compare.compared, 'OK input')} in {compare.seconds} s, "
            f"and {compare.differ} differ. Python could run no call of {compare.skipped}, "
            f"and damlc rejects the Daml or the test of {compare.dropped}. "
            f"{_plural(compare.skipped_calls, 'call')} of the compared inputs "
            f"{'was' if compare.skipped_calls == 1 else 'were'} not compared.",
        ]
        if compare.interrupted:
            lines.append("Ctrl-C stopped the compare step, so some inputs were not compared.")
        lines += ["", f"## {_plural(len(groups), 'run group')}"]
        if groups:
            lines += [
                "",
                "| Group | Difference | Call | Loop check | Count | Seed | First seen | Input "
                "| Test |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        for group in groups:
            cells = [
                group.id,
                group.difference,
                group.call,
                group.loop_check or "-",
                str(group.count),
                group.seed,
                f"input {group.first_seen.input}, {group.first_seen.second} s",
                f"[{Path(group.input_file).name}]({group.input_file})",
                f"[{Path(group.test_file).name}]({group.test_file})",
            ]
            lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
        if groups:
            lines += ["", "### What Python does", ""]
            lines += [
                f"- {group.id}, {group.call}: {_inline_code(group.python)}. "
                f"Run `dpm test` in groups/{group.id} to see what Daml does."
                for group in groups
            ]
        return lines

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
        for bad in self.bad_daml_groups():
            saved = self.folder / bad.input_file
            saved.parent.mkdir(parents=True)
            saved.write_text(bad.input, encoding="utf-8", newline="")
            shutil.copyfile(self._seeds[bad.seed].daml_yaml, saved.parent / "daml.yaml")
            (self.folder / bad.daml_file).write_text(bad.daml, encoding="utf-8", newline="")
        for loop in self.loop_groups():
            saved = self.folder / loop.input_file
            saved.parent.mkdir(parents=True)
            saved.write_text(loop.input, encoding="utf-8", newline="")
            daml_yaml = self._seeds[loop.seed].daml_yaml
            if daml_yaml is not None:
                shutil.copyfile(daml_yaml, saved.parent / "daml.yaml")
            (self.folder / loop.daml_file).write_text(loop.daml, encoding="utf-8", newline="")
            if loop.shrunk_file is not None:
                shrunk = self.folder / loop.shrunk_file
                shrunk.parent.mkdir()
                shrunk.write_text(loop.shrunk, encoding="utf-8", newline="")
                (self.folder / loop.shrunk_daml_file).write_text(
                    loop.shrunk_daml, encoding="utf-8", newline=""
                )
        for run in self.run_groups():
            saved = self.folder / run.input_file
            (saved.parent / "daml").mkdir(parents=True)
            saved.write_text(run.input, encoding="utf-8", newline="")
            seed = self._seeds[run.seed]
            shutil.copyfile(calls_path(seed.path), self.folder / run.calls_file)
            daml_yaml = group_daml_yaml(seed.daml_yaml)
            (saved.parent / "daml.yaml").write_text(daml_yaml, encoding="utf-8")
            (self.folder / run.daml_file).write_text(run.daml, encoding="utf-8", newline="")
            (self.folder / run.test_file).write_text(run.test, encoding="utf-8", newline="")
        (self.folder / "report.md").write_text(self.markdown(), encoding="utf-8")
        document = json.dumps(self.to_json(), indent=2, ensure_ascii=False) + "\n"
        (self.folder / "report.json").write_text(document, encoding="utf-8")


BAD_DAML_TEXT: Final = (
    "BAD_DAML means that forge said OK and wrote Daml, but damlc, the Daml compiler, "
    "rejects that Daml. That is a bug in forge: its check stage let through a program "
    "that it then translated to wrong Daml. Each group folder has the input, its daml.yaml, "
    "and forge's Daml, so `dpm build` in the folder shows the error again."
)
"""What BAD_DAML means, in plain English, for report.md."""

BAD_LOOP_TEXT: Final = (
    "BAD_LOOP means that forge said OK and wrote Daml, but the loop check finds a loop "
    "bug, L1 to L4, in that Daml. The check reads forge's Daml and the .vy text, "
    "with no damlc. An input goes to the group of its first check. With --damlc, the "
    "groups are also split by whether damlc builds the Daml. A group that builds is the "
    "most serious case: damlc accepts the wrong code. Each group folder has the input, "
    "its daml.yaml when the seed has one, forge's Daml, and in shrunk/ the shrunk input "
    "and its Daml."
)
"""What BAD_LOOP means, in plain English, for report.md."""

BAD_RUN_TEXT: Final = (
    "BAD_RUN means that forge said OK and wrote Daml that damlc builds, but the Daml "
    "does not do what the .vy code does. The run calls each function and choice of the "
    "seed's calls file in Python, on the .vy code, and in Daml Script, on forge's Daml, "
    "with the same data, and compares the results and the contracts that each call makes. "
    "An input goes to the group of its first difference, in calls file order, and its first "
    "loop check. Each group folder is a Daml project with the input, its calls file, "
    "forge's Daml, and a test, so `dpm test` in the folder shows the difference again."
)
"""What BAD_RUN means, in plain English, for report.md."""


def _inline_code(text: str) -> str:
    """Markdown code for `text`, which can hold backticks: "`self' is ..." is a damlc message."""
    ticks = "`" * (max(map(len, re.findall("`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"


def _exception_at(group: Group) -> str:
    """'KeyError at forge/ir/lower.py:289', or 'RecursionError' when there is no forge line."""
    return group.exception if group.where is None else f"{group.exception} at {group.where}"


def _code_block(text: str, language: str) -> list[str]:
    """`text` as a fenced Markdown code block: the opening fence, the text, the closing fence."""
    # One backtick more than the longest run in the text, so the text cannot end the block.
    fence = "`" * max([3, *(len(run) + 1 for run in re.findall("`+", text))])
    return [f"{fence}{language}", text.rstrip("\n"), fence]


def _plural(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _shrunk_cell(group: Group | LoopGroup) -> str:
    """'[3 of 42 lines](groups/g02/shrunk/escrow.vy)', or 'not shrunk'."""
    if group.shrunk is None:
        return "not shrunk"
    total = len(group.input.splitlines())
    lines = f"{len(group.shrunk.splitlines())} of {total} line{'' if total == 1 else 's'}"
    return f"[{lines}]({group.shrunk_file})"


def _now() -> datetime.datetime:
    """Now, in UTC. Tests replace it to make two runs start in one second."""
    return datetime.datetime.now(datetime.UTC)
