"""The import check: four ways the import lines of forge's Daml are wrong.

This module imports no forge, like loopcheck.py, whose check enum and finding
type it shares: I1 to I4 are LoopCheck members after L1 to L4, so a text's
loop finding names its group before an import finding does. It owns one
decision: how one .vy text and forge's Daml for it give import findings
(find_import_bugs). It reads only the two texts, so it needs no damlc and
cannot see the sibling files.
"""

from __future__ import annotations

import re
import sys
from typing import Final

from damlforge_fuzz.loopcheck import LoopBug, LoopCheck

_DAML_IMPORT: Final = re.compile(
    r"import(?P<qualified> qualified)? (?P<module>[\w.]+)"
    r"(?: as (?P<alias>\S+))?(?: \((?P<names>.*)\))? *"
)
_DAML_NOT_CODE: Final = re.compile(r'"(?:\\.|[^"\\\n])*"|--[^\n]*')
_QUALIFIED_USE: Final = re.compile(r"(?<![\w.])((?:[A-Z]\w*\.)+)[A-Za-z_(]")
_MODULE_ALIAS: Final = re.compile(r"[A-Z]\w*(?:\.[A-Z]\w*)*")
_TYPE_SELECTOR: Final = re.compile(r"\)\.(?P<name>[A-Z]\w*)")
_VY_FROM: Final = re.compile(
    r"^from +(?P<module>[\w.]+) +import +(?P<names>\([^)]*\)|[^\n#]+)", re.M
)
_VY_IMPORT: Final = re.compile(r"^import +(?P<module>[\w.]+)(?: +as +\w+)? *$", re.M)
_SEGMENT: Final = re.compile(r"[A-Za-z0-9]+")


def find_import_bugs(vy: str, daml: str) -> tuple[LoopBug, ...]:
    """The import checks that `daml`, forge's Daml for the .vy text `vy`, fails.

    At most one finding per check, the first in the Daml, in check order (I1
    to I4). Pure and total: it never raises for any two strings.
    """
    lines = daml.split("\n")
    imports = [(n, m) for n, line in enumerate(lines) if (m := _DAML_IMPORT.fullmatch(line))]
    code = [
        "" if line.startswith(("module ", "import ")) else _DAML_NOT_CODE.sub("", line)
        for line in lines
    ]
    found = (_i1(code, imports), _i2(imports), _i3(code), _i4(vy, imports))
    return tuple(finding for finding in found if finding is not None)


def _i1(code: list[str], imports: list[tuple[int, re.Match[str]]]) -> LoopBug | None:
    bound = {m["alias"] or m["module"] for _, m in imports} | {m["module"] for _, m in imports}
    for n, line in enumerate(code):
        for use in _QUALIFIED_USE.finditer(line):
            qualifier = use[1][:-1]
            if not any(qualifier == q or qualifier.startswith(q + ".") for q in bound):
                detail = f"{qualifier}. at Daml line {n + 1} with no import that binds {qualifier}"
                return LoopBug(LoopCheck.I1, n + 1, detail)
    return None


def _i2(imports: list[tuple[int, re.Match[str]]]) -> LoopBug | None:
    for n, m in imports:
        if m["alias"] is not None and _MODULE_ALIAS.fullmatch(m["alias"]) is None:
            detail = f"import alias {m['alias']} at Daml line {n + 1} is not a Daml module name"
            return LoopBug(LoopCheck.I2, n + 1, detail)
    return None


def _i3(code: list[str]) -> LoopBug | None:
    for n, line in enumerate(code):
        if (use := _TYPE_SELECTOR.search(line)) is not None:
            detail = f").{use['name']} at Daml line {n + 1} selects an upper-case name from an expression"
            return LoopBug(LoopCheck.I3, n + 1, detail)
    return None


def _i4(vy: str, imports: list[tuple[int, re.Match[str]]]) -> LoopBug | None:
    by_module = {m["module"]: m for _, m in imports}
    wanted = [(m["module"], _names(m["names"])) for m in _VY_FROM.finditer(vy)]
    wanted += [(m["module"], []) for m in _VY_IMPORT.finditer(vy)]
    for module, names in wanted:
        # forge ignores the dots of a relative import: `.models` is `models`.
        module = module.lstrip(".")
        root = module.split(".", 1)[0]
        if not root or root == "forge" or root in sys.stdlib_module_names or "*" in names:
            continue
        daml_module = ".".join(_daml_module_name(part) for part in module.split("."))
        daml_import = by_module.get(daml_module)
        if daml_import is None:
            detail = f"the .vy imports {module}, and the Daml has no import {daml_module}"
            return LoopBug(LoopCheck.I4, 1, detail)
        listed = _names(daml_import["names"] or "")
        missing = [name for name in names if daml_import["names"] is not None and name not in listed]
        if missing:
            detail = (
                f"the .vy imports {missing[0]} from {module}, "
                f"and the Daml import of {daml_module} does not list it"
            )
            return LoopBug(LoopCheck.I4, 1, detail)
    return None


def _names(text: str) -> list[str]:
    """`a, B(..), c` or `(a, b)` -> ["a", "B", "c"]."""
    names = text.strip("() \n").replace("\n", " ").split(",")
    return [name.split("(")[0].strip() for name in names if name.strip()]


def _daml_module_name(stem: str) -> str:
    # forge.utils.daml_module_name, copied so that this module needs no forge.
    name = "".join(segment[:1].upper() + segment[1:] for segment in _SEGMENT.findall(stem))
    return name if name and name[0].isalpha() else f"M{name}"
