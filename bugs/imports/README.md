# Import bugs b28 to b32

This folder has five small programs that show import bugs in DamlForge `0413ac6` (`forge_version` 0.0.12).
The numbers continue b01 to b27 ([the 20000-input analysis](../../reports/2026-10-19T18-45-34Z/analysis.md), [the loop report analysis](../../reports/2026-10-20T16-34-28Z/analysis.md)), and the categories are the categories of the 20000-input analysis.

b28 was found by hand. The fuzzer found b29, b30, and b31 with the import seeds (`contracts/import_*`), the import rules, and the import check (unit 12). Each program here was then made by hand, as small as it can be.
`models.vy` is the sibling module that b30, b31, and b32 import. It is not a bug program.

The two import bugs of the first report are fixed on 0.0.12. b13 (`import` in a function) and b14 (a typo in `from forge.X import ...`) now get `DF1213`.

| Bug | Category | Code | What happens | Proof |
| --- | --- | --- | --- | --- |
| [b28](#b28-a-relative-import-crashes) | C | `from . import models` | `AttributeError` at `forge/builtin_stubs.py:150`, no DF error | forge's traceback |
| [b29](#b29-an-aliased-import-of-a-missing-forge-module-crashes) | C | `import forge.math as m`, and an enum | `ModuleNotFoundError` at `forge/semantics/analysis/imports.py:108`, no DF error | forge's traceback |
| [b30](#b30-a-lower-case-module-alias-gives-bad-daml) | B | `import models as m`, then `m.double(x)` | forge writes `import qualified Models as m` | import check `I2`, and damlc: `parse error on input ‘m’` |
| [b31](#b31-a-qualified-enum-value-gives-bad-daml) | B | `import models as M`, then `M.Kind.CASH` | forge writes `(M.Kind).CASH` | import check `I3`, and damlc: `Not in scope: data constructor ‘M.Kind’` |
| [b32](#b32-a-plain-module-import-cannot-name-a-type) | B | `import models`, then `-> models.Kind` | `DF1213: No builtin or user-defined type named models.Kind`; with `as M` the same code is OK | forge's error |

Category B is valid code that forge cannot compile right. Category C is code that makes forge crash with a Python traceback, where a DF error is the right answer.

Run all the programs with one command from the repository root.
This is the real output:

```
$ damlforge-fuzz check bugs/imports
CRASH    check  bugs/imports/b28_relative_import.vy  AttributeError 'NoneType' object has no attribute 'split' at forge/builtin_stubs.py:150
CRASH    check  bugs/imports/b29_missing_forge_module_with_alias.vy  ModuleNotFoundError No module named 'forge.math' at forge/semantics/analysis/imports.py:108
BAD_IMP  emit   bugs/imports/b30_lower_case_module_alias.vy  I2: import alias m at Daml line 3 is not a Daml module name
BAD_IMP  emit   bugs/imports/b31_qualified_enum_value.vy  I3: ).CASH at Daml line 7 selects an upper-case name from an expression
REJECTED check  bugs/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Kind` (return type of `cash`)
OK       emit   bugs/imports/models.vy
```

The command exits with 1.
With `--damlc`, damlc builds each program's Daml together with forge's Daml of `models.vy`, and proves b30 and b31. It needs dpm and the Daml SDK 3.5.2:

```
$ damlforge-fuzz check --damlc bugs/imports
CRASH    check  bugs/imports/b28_relative_import.vy  AttributeError 'NoneType' object has no attribute 'split' at forge/builtin_stubs.py:150
CRASH    check  bugs/imports/b29_missing_forge_module_with_alias.vy  ModuleNotFoundError No module named 'forge.math' at forge/semantics/analysis/imports.py:108
BAD_IMP  emit   bugs/imports/b30_lower_case_module_alias.vy  I2: import alias m at Daml line 3 is not a Daml module name; damlc rejects: parse error on input ‘m’
BAD_IMP  emit   bugs/imports/b31_qualified_enum_value.vy  I3: ).CASH at Daml line 7 selects an upper-case name from an expression; damlc rejects: Not in scope: data constructor ‘M.Kind’
REJECTED check  bugs/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Kind` (return type of `cash`)
OK       emit   bugs/imports/models.vy
```

## b28: a relative import crashes

```python
from . import models
```

A relative import with no name after the dots crashes forge while it builds the module's scope, before its import checks run:

```
forge/semantics/__init__.py:9, analyze_module
  -> forge/builtin_stubs.py:162, scope_of
  -> forge/builtin_stubs.py:155, _stub_imports
  -> forge/builtin_stubs.py:150, _root
       return module.split(".", 1)[0]
```

`_root` expects `stmt.module` to be a string. Python's parser sets `ImportFrom.module` to `None` for `from . import X` and `from .. import X`.
`from .models import X` does not crash, because its `module` is `"models"`.
A related point, not counted as a bug here: forge ignores the dots of a relative import. `from ..models import X` loads `models.vy` next to the file, and `from .enum import Enum` is read as the standard library's `enum`.

## b29: an aliased import of a missing forge module crashes

```python
from enum import Enum, auto

import forge.math as m


class Kind(Enum):
    CASH = auto()
```

`forge.math` does not exist. forge should give `DF1213`, as it does for `from forge.modles import Party`. Instead:

```
forge/semantics/analysis/types.py:289, known_type_names
  -> forge/semantics/analysis/types.py:271, _qualified_import_type_names
       mod = ImportsBuilder._import_real_module(alias.name)
  -> forge/semantics/analysis/imports.py:108, _import_real_module
       return importlib.import_module(module_path)
ModuleNotFoundError: No module named 'forge.math'
```

When forge collects the known type names, it imports each module of an aliased `import X as Y` with Python's `importlib`, and nothing catches the error.
Any type declaration, such as the enum, makes forge collect the type names.
Without the alias, `import forge.math` alone is accepted, with no error, and forge writes no Daml for it.

## b30: a lower-case module alias gives bad Daml

```python
from forge.models import Decimal
import models as m


def twice(x: Decimal) -> Decimal:
    return m.double(x)
```

forge writes:

```
import qualified Models as m

twice : Decimal -> Decimal
twice x =
  m.double x
```

A Daml module alias must start with an upper-case letter, so `damlc` rejects `as m`. forge should rename the alias (for example to `M`) or reject it with a DF error.

Proof with damlc (SDK 3.5.2), building forge's Daml of this program together with forge's `Models.daml` of `models.vy`, the way `forge daml bugs/imports` writes them:

```
./B30.daml:3:28: error: parse error on input ‘m’
```

The control, the same program with `import models as M` and `M.double(x)`, builds.

## b31: a qualified enum value gives bad Daml

```python
import models as M


def cash() -> M.Kind:
    return M.Kind.CASH
```

forge writes:

```
cash : M.Kind
cash =
  (M.Kind).CASH
```

In Daml, the qualified value is `M.CASH`. `(M.Kind).CASH` is not valid Daml.
With `from models import Kind` and `Kind.CASH`, forge writes the right `CASH`.
The same Daml shape, `(expression).UpperName`, also shows in forge's own example `examples/basic/simple.vy`, where a choice is called on an `Optional` field: `(self.cross_template).CrossTemplate_Cross`.

Proof with damlc (SDK 3.5.2), building forge's Daml of this program together with forge's `Models.daml` of `models.vy`, the way `forge daml bugs/imports` writes them:

```
./B31.daml:7:4: error:
    Not in scope: data constructor ‘M.Kind’
```

The control, `from models import Kind` with `-> Kind` and `return Kind.CASH`, builds.

## b32: a plain module import cannot name a type

```python
import models


def cash() -> models.Kind:
    return models.Kind.CASH
```

forge rejects it with `DF1213: No builtin or user-defined type named models.Kind (return type of cash)`.
The same code with `import models as M` and `M.Kind` compiles.
The cause is in `_qualified_import_type_names` (`forge/semantics/analysis/types.py:263`), which adds the type names of an imported module only for an import with an alias: `if alias.asname is None: continue`.
The same function causes b29.
