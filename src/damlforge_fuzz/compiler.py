"""Compile one .vy text with forge, in this process, and sort the result.

This is the only module that imports forge. It owns three decisions that every
later unit relies on:

- how a .vy file on disk becomes the context forge compiles a text in (Seed);
- which exceptions are forge's own errors and which are forge bugs (Ok, Rejected, Crash);
- what makes two crashes "the same crash" (CrashKey).

Every Ok also carries the loop check's findings on its Daml (Ok.loop_bugs).
loopcheck.py decides which loops are wrong and needs no forge. This module only
runs it, so every caller of compile_and_sort gets the same findings.
"""

from __future__ import annotations

import enum
import functools
import os
import shutil
import re
import traceback
import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import ClassVar, Final, TypeAlias

from damlforge_fuzz.damlc import DamlSource, imported_siblings
from damlforge_fuzz.importcheck import find_import_bugs
from damlforge_fuzz.loopcheck import LoopBug, LoopCheck, find_loop_bugs

try:
    import forge
    from forge.ast.parse import parse_to_ast
    from forge.cli.forge_daml import _find_project_dir, _load_codegen_settings
    from forge.codegen import daml_module_name, generate_daml
    from forge.daml_versions import DamlCodegenSettings
    from forge.exceptions import VyperException, VyperInternalException
    from forge.ir import lower_module
    from forge.semantics import analyze_module
except ImportError as error:
    raise ImportError(
        "damlforge-fuzz needs DamlForge's `forge` package. Install DamlForge first, "
        "as README.md shows. `pip install forge` installs an unrelated Django tool. "
        f"({error})"
    ) from error


FORGE_VERSION: Final[str] = forge.__version__
"""The installed DamlForge version, such as "0.0.11". Reports record it."""


class Stage(enum.StrEnum):
    """The forge step that was running. Members are in pipeline order.

    A stage names the top-level step, not the folder of the file that failed.
    The check step calls forge.ir.lower.lower_type, so a crash at
    forge/ir/lower.py:101 can have stage CHECK.
    """

    PARSE = "parse"  # forge.ast.parse_to_ast
    CHECK = "check"  # forge.semantics.analyze_module
    LOWER = "lower"  # forge.ir.lower_module
    EMIT = "emit"  # forge.codegen.generate_daml


STAGE_TEXT: Final[dict[Stage, str]] = {
    Stage.PARSE: "forge reads the .vy text and makes a syntax tree (forge.ast.parse_to_ast). "
    "A crash here means forge failed while it read the code.",
    Stage.CHECK: "forge checks names, types, imports, and the rules for templates and choices "
    "(forge.semantics.analyze_module). Wrong code must stop here with a DF error.",
    Stage.LOWER: "forge changes the checked program into its internal form, IR "
    "(forge.ir.lower_module). A crash here usually means that check let through code "
    "that forge cannot translate.",
    Stage.EMIT: "forge writes the Daml code from the IR (forge.codegen.generate_daml).",
}
"""What each stage does, in plain English, for readers of report.md and the README."""


@dataclass(frozen=True, slots=True)
class ForgeLine:
    """A line in forge's source, such as forge/ir/lower.py:244.

    `file` is relative to the folder that holds the forge package and uses `/`
    on every OS, so the same crash prints the same way on every machine and
    for every install method (wheel, git, editable checkout).
    """

    file: str
    line: int

    def __str__(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True, slots=True)
class CrashKey:
    """What makes two crashes the same crash: one report group, one shrink target.

    The message is left out on purpose because it often holds text from the
    input. `count & 1` and `count | 1` both crash with KeyError at
    forge/ir/lower.py:289 in DamlForge v0.0.10, with messages 'BitAnd' and 'BitOr'. They are one
    bug, a missing entry in forge's _BIN_OPS table.

    `where` is None for a crash with no stable line. See Crash.where.
    """

    exception: str
    where: ForgeLine | None

    def __str__(self) -> str:
        return self.exception if self.where is None else f"{self.exception} at {self.where}"


@dataclass(frozen=True, slots=True)
class Sibling:
    """Another .vy file in a seed's folder, which the seed can import, and forge's Daml for it."""

    path: Path
    module_name: str
    daml: str


@dataclass(frozen=True)
class Seed:
    """A .vy file and the context forge compiles it in.

    compile_and_sort(text, seed) compiles `text` as if it were the file at
    `seed.path`: the same Daml module name, the same daml.yaml settings, and the
    same folder for sibling imports. That is how a mutated copy, a shrunk copy,
    and the seed itself all compile the way `forge daml` would compile the file.

    Load a seed once with Seed.load and reuse it. Loading reads the file and the
    nearest daml.yaml. Compiling reads neither.
    """

    path: Path
    """The path as the user gave it. Output and reports show this path."""
    text: str
    """The file's text at load time. Mutations start from it."""
    module_name: str
    """The Daml module name forge derives from the file name: iou.vy -> Iou."""
    daml_yaml: Path | None
    """The daml.yaml forge took the settings from, or None when forge found none.

    A report copies it next to a saved input, so the input compiles with the
    seed's settings wherever the report folder is.
    """
    _resolved: Path = field(repr=False)
    _settings: DamlCodegenSettings = field(repr=False, compare=False)
    siblings: tuple[Sibling, ...] = field(default=(), repr=False, compare=False)
    """The other .vy files of the seed's folder that forge compiles, in name order.
    forge reads them from the disk when the seed imports them, so they never change
    in a run. A report copies them next to a saved input, and damlc builds their
    Daml next to the input's Daml."""

    @classmethod
    def load(cls, path: Path) -> Seed:
        """Read a .vy file, its project settings, and the other .vy files of its folder.

        Raises OSError when the file cannot be read, and ValueError when the
        text is not UTF-8 or daml.yaml does not hold a mapping. A daml.yaml that
        is not valid YAML raises yaml.YAMLError from forge's loader.
        """
        seed = cls._load_alone(path)
        siblings = []
        for other in sorted(seed._resolved.parent.glob("*.vy")):
            if other != seed._resolved:
                alone = cls._load_alone(other)
                outcome = compile_and_sort(alone.text, alone)
                if isinstance(outcome, Ok):
                    siblings.append(Sibling(other, outcome.module_name, outcome.daml))
        return replace(seed, siblings=tuple(siblings))

    def daml_source(self, daml: str, module_name: str) -> DamlSource:
        """The DamlSource of forge's Daml for a text of this seed, with its siblings' Daml."""
        siblings = tuple((sibling.module_name, sibling.daml) for sibling in self.siblings)
        return DamlSource(daml, module_name, self.daml_yaml, siblings)

    def copy_siblings(self, folder: Path, daml: str | None = None) -> None:
        """Copy the sibling .vy files into `folder`, so a saved copy of the seed compiles there.

        With `daml`, forge's Daml for the saved copy, also write the Daml of each
        sibling that it imports, so `dpm build` there builds what damlc built.
        """
        for sibling in self.siblings:
            shutil.copyfile(sibling.path, folder / sibling.path.name)
        if daml is not None:
            for name, text in imported_siblings(daml, self.daml_source(daml, "").siblings):
                (folder / f"{name}.daml").write_text(text, encoding="utf-8", newline="")

    @classmethod
    def _load_alone(cls, path: Path) -> Seed:
        resolved = path.resolve()
        text = path.read_text(encoding="utf-8")
        # forge's own private loaders, so a seed compiles exactly as `forge daml`
        # compiles it. A rename in forge fails at import instead of letting the
        # two tools disagree silently.
        project = _find_project_dir(resolved)
        settings = _load_codegen_settings(project)
        daml_yaml = project / "daml.yaml" if (project / "daml.yaml").is_file() else None
        return cls(path, text, daml_module_name(resolved.stem), daml_yaml, resolved, settings)


@dataclass(frozen=True, slots=True)
class Ok:
    """forge wrote Daml. `daml` is module `module_name`, so it belongs in `<module_name>.daml`.

    `loop_bugs` is what the loop check finds in that Daml: at most one LoopBug
    per check, in check order, and empty when the loops look right. Totals
    still counts an Ok with loop bugs as OK, because forge said OK.
    """

    label: ClassVar[str] = "OK"
    stage: ClassVar[Stage] = Stage.EMIT

    daml: str
    module_name: str
    loop_bugs: tuple[LoopBug, ...] = ()
    """Empty by default, so a test can make Ok("", "Iou"). compile_and_sort fills it."""

    @property
    def loop_key(self) -> LoopCheck | None:
        """The first loop check this Daml fails, or None. It names the input's loop group."""
        return self.loop_bugs[0].check if self.loop_bugs else None


@dataclass(frozen=True, slots=True)
class Rejected:
    """forge reported one of its own errors, a VyperException. The input is wrong, not forge.

    `codes` holds every DamlForge diagnostic code in forge's message, in order
    and without duplicates, such as ("DF1213",). It is empty for errors that
    have none (SyntaxException, UnknownType, ...). When forge finds several
    errors it raises one plain VyperException that lists them, so the codes
    come from the message text, not from an attribute.

    `message` is one line: the first line of forge's message that has a code,
    such as "DF1213: No builtin ...", or else its first line.
    """

    label: ClassVar[str] = "REJECTED"

    stage: Stage
    exception: str
    message: str
    codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Crash:
    """forge raised anything that is not a VyperException. That is a forge bug.

    `where` is the innermost traceback frame inside the forge package: the forge
    line that raised, or that called the library code that raised. It is None
    only for RecursionError and MemoryError. Their innermost frame depends on
    how deep the input nests, not on the bug: a 300-term sum fails at
    forge/ast/nodes.py:135 and a 600-term sum at forge/ast/parse.py:251, so
    those crashes group by exception type alone.

    The exception object itself is not kept. Its traceback holds every frame and
    the whole parsed module, and later units need only these strings.
    """

    label: ClassVar[str] = "CRASH"

    stage: Stage
    exception: str
    message: str
    where: ForgeLine | None

    @property
    def key(self) -> CrashKey:
        return CrashKey(self.exception, self.where)


Outcome: TypeAlias = Ok | Rejected | Crash


def compile_and_sort(text: str, seed: Seed) -> Outcome:
    """Compile `text` as if it were the file `seed.path`, and sort what happened.

    Invariants every caller relies on:

    - Returns an outcome for any text. It raises only KeyboardInterrupt,
      SystemExit, or an exception with no forge frame in its traceback, which
      is a bug in the fuzzer, not in forge.
    - An Ok carries find_loop_bugs(text, daml). A bug in the loop check is a
      fuzzer bug: it propagates and is never sorted as a forge crash.
    - Silent. It writes nothing to stdout or stderr.
    - Deterministic in (text, seed). The caller's warning filters do not change the
      result, and the filters are the same after the call as before it.
    - No file I/O of its own. forge reads files only to resolve sibling imports.
    - Not thread-safe. warnings.catch_warnings swaps process-wide state for the
      length of the call. Run several fuzzers as processes, not threads.
    """
    with warnings.catch_warnings():
        # Not only noise: under a caller's "error" filter, forge's Deprecation
        # warning is raised and Decimal({}) sorts as CRASH instead of OK.
        warnings.simplefilter("ignore")
        stage = Stage.PARSE
        try:
            module = parse_to_ast(
                text, module_path=seed._resolved.name, resolved_path=str(seed._resolved)
            )
            stage = Stage.CHECK
            import_graph = analyze_module(module)
            stage = Stage.LOWER
            ir = lower_module(module, import_graph=import_graph)
            stage = Stage.EMIT
            daml, _source_map = generate_daml(
                ir, module_name=seed.module_name, settings=seed._settings
            )
        except VyperException as error:
            return _rejected(stage, error)
        except Exception as error:
            if isinstance(error, _NO_STABLE_LINE):
                where = None
            else:
                where = _innermost_forge_line(error)
                if where is None:
                    raise
            return Crash(stage, type(error).__name__, _message(error), where)
        # After the try, so an exception here is never sorted as a forge crash.
        return Ok(daml, seed.module_name, find_loop_bugs(text, daml) + find_import_bugs(text, daml))


_NO_STABLE_LINE: Final = (RecursionError, MemoryError)

_FORGE_DIR: Final = os.path.dirname(os.path.realpath(forge.__file__))

_DF_CODE: Final = re.compile(r"DF\d{4}")


def _rejected(stage: Stage, error: VyperException) -> Rejected:
    message = _message(error)
    lines = message.splitlines() or [""]
    codes = tuple(dict.fromkeys(_DF_CODE.findall(message)))
    line = next((line for line in lines if _DF_CODE.search(line)), lines[0])
    return Rejected(stage, type(error).__name__, line.removeprefix("DamlForgeException: "), codes)


def _message(error: Exception) -> str:
    """forge's text for `error`, cheap and never raising.

    For forge's exception classes this is `.message`, not str(): str() formats a
    source excerpt, computes a hint, and adds a "please file an issue" footer to
    internal errors.
    """
    if isinstance(error, (VyperException, VyperInternalException)):
        return str(error.message)
    try:
        return str(error)
    except Exception:
        return f"<unprintable {type(error).__name__}>"


def _innermost_forge_line(error: BaseException) -> ForgeLine | None:
    """The innermost traceback frame whose file belongs to the forge package.

    Library frames below it are skipped. A KeyError raised inside enum.py or
    importlib is reported at the forge line that called into the library.
    """
    found = None
    for frame, lineno in traceback.walk_tb(error.__traceback__):
        file = _forge_file(frame.f_code.co_filename)
        if file is not None:
            found = ForgeLine(file, lineno)
    return found


@functools.cache
def _forge_file(filename: str) -> str | None:
    """'forge/ir/lower.py' when `filename` is inside the forge package, else None.

    Compares real paths against forge.__file__ instead of searching for "/forge/"
    in the name, so a checkout at ~/src/forge/... or a venv symlink cannot
    misplace a frame. Cached because a run meets a few hundred distinct file
    names and realpath costs one lstat per path component.
    """
    if not os.path.isabs(filename):
        # "<string>" or "<frozen importlib._bootstrap>": realpath would join the cwd.
        return None
    real = os.path.realpath(filename)
    if os.path.commonpath([real, _FORGE_DIR]) != _FORGE_DIR:
        return None
    return "forge/" + Path(os.path.relpath(real, _FORGE_DIR)).as_posix()
