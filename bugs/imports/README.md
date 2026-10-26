# Import bugs b28 to b33

This folder has six small programs that show import bugs in DamlForge.
b28 to b32 were found on `0413ac6` (`forge_version` 0.0.12).
On `5da0584` (`forge_version` 0.0.13), b28, b29, and b30 are fixed, and b31 and b32 are still open.
b33 was found on 0.0.13, and 0.0.12 has it too.
The numbers continue b01 to b27 ([the 20000-input analysis](../../reports/2026-10-19T18-45-34Z/analysis.md), [the loop report analysis](../../reports/2026-10-20T16-34-28Z/analysis.md)), and the categories are the categories of the 20000-input analysis.

b28 was found by hand. The fuzzer found b29, b30, and b31 with the import seeds (`contracts/import_*`), the import rules, and the import check (unit 12).
b33 was found by hand, in [the analysis of the 0.0.13 import run](../../reports/2026-10-26T07-07-10Z/analysis.md).
Each program here was then made by hand, as small as it can be.
`models.vy` is the sibling module that b30 to b33 import. It is not a bug program.

The two import bugs of the first report are fixed since 0.0.12. b13 (`import` in a function) and b14 (a typo in `from forge.X import ...`) get `DF1213`.

| Bug | Category | Code | 0.0.12 | 0.0.13 | State |
| --- | --- | --- | --- | --- | --- |
| [b28](#b28-a-relative-import-crashes) | C | `from . import models` | `AttributeError` at `forge/builtin_stubs.py:150` | `DF1213: Relative imports are not supported` | Fixed |
| [b29](#b29-an-aliased-import-of-a-missing-forge-module-crashes) | C | `import forge.math as m`, and an enum | `ModuleNotFoundError` at `forge/semantics/analysis/imports.py:108` | `DF1213: No module named forge.math` | Fixed |
| [b30](#b30-a-lower-case-module-alias-gives-bad-daml) | B | `import models as m`, then `m.double(x)` | `import qualified Models as m`; damlc: `parse error on input ‘m’` | `DF1213: Module alias m must start with an uppercase letter` | Fixed |
| [b31](#b31-a-qualified-enum-value-is-not-compiled) | B | `import models as M`, then `M.Kind.CASH` | `(M.Kind).CASH`; damlc: `Not in scope: data constructor ‘M.Kind’` | `DF1213: Uppercase member CASH cannot be selected from an expression` | Open |
| [b32](#b32-a-plain-module-import-cannot-name-a-type) | B | `import models`, then `models.Note` as a type | `DF1213: No builtin or user-defined type named models.Note` | the same | Open |
| [b33](#b33-a-plain-module-import-gives-bad-daml-for-a-call) | B | `import models`, then `models.double(x)` | `models.double x` in the Daml; import check `I1`, and damlc: `Variable not in scope: models` | the same | Open |

Category B is valid code that forge cannot compile right. Category C is code that makes forge crash with a Python traceback, where a DF error is the right answer.

Run all the programs with one command from the repository root.
This is the real output on 0.0.13:

```
$ damlforge-fuzz check bugs/imports
REJECTED check  bugs/imports/b28_relative_import.vy  DF1213: Relative imports are not supported; use an absolute module import
REJECTED check  bugs/imports/b29_missing_forge_module_with_alias.vy  DF1213: No module named `forge.math`
REJECTED check  bugs/imports/b30_lower_case_module_alias.vy  DF1213: Module alias `m` must start with an uppercase letter because Daml module aliases are constructors
REJECTED check  bugs/imports/b31_qualified_enum_value.vy  DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
REJECTED check  bugs/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Note` (return type of `same`)
BAD_IMP  emit   bugs/imports/b33_plain_module_import_call.vy  I1: models. at Daml line 7 with no import that binds models
OK       emit   bugs/imports/models.vy
```

The command exits with 1.
The import check finds b33 with no damlc.
With `--damlc`, damlc builds each program's Daml together with forge's Daml of `models.vy`, and proves b33. It needs dpm and the Daml SDK 3.5.2:

```
$ damlforge-fuzz check --damlc bugs/imports
REJECTED check  bugs/imports/b28_relative_import.vy  DF1213: Relative imports are not supported; use an absolute module import
REJECTED check  bugs/imports/b29_missing_forge_module_with_alias.vy  DF1213: No module named `forge.math`
REJECTED check  bugs/imports/b30_lower_case_module_alias.vy  DF1213: Module alias `m` must start with an uppercase letter because Daml module aliases are constructors
REJECTED check  bugs/imports/b31_qualified_enum_value.vy  DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
REJECTED check  bugs/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Note` (return type of `same`)
BAD_IMP  emit   bugs/imports/b33_plain_module_import_call.vy  I1: models. at Daml line 7 with no import that binds models; damlc rejects: Variable not in scope: models
OK       emit   bugs/imports/models.vy
```

## b28: a relative import crashes

```python
from . import models
```

On 0.0.12, forge crashed while it built the module's scope, before its import checks ran:

```
forge/semantics/__init__.py:9, analyze_module
  -> forge/builtin_stubs.py:162, scope_of
  -> forge/builtin_stubs.py:155, _stub_imports
  -> forge/builtin_stubs.py:150, _root
       return module.split(".", 1)[0]
```

`_root` expected `stmt.module` to be a string. Python's parser sets `ImportFrom.module` to `None` for `from . import X`.

On 0.0.13, forge rejects every relative import: `DF1213: Relative imports are not supported; use an absolute module import`.
This also fixes a related point of 0.0.12, which read `from ..models import X` as `models.vy` next to the file.

## b29: an aliased import of a missing forge module crashes

```python
from enum import Enum, auto

import forge.math as m


class Kind(Enum):
    CASH = auto()
```

`forge.math` does not exist. On 0.0.12, forge crashed:

```
forge/semantics/analysis/types.py:289, known_type_names
  -> forge/semantics/analysis/types.py:271, _qualified_import_type_names
       mod = ImportsBuilder._import_real_module(alias.name)
  -> forge/semantics/analysis/imports.py:108, _import_real_module
       return importlib.import_module(module_path)
ModuleNotFoundError: No module named 'forge.math'
```

On 0.0.13, forge gives `DF1213: No module named forge.math`.

## b30: a lower-case module alias gives bad Daml

```python
from forge.models import Decimal
import models as m


def twice(x: Decimal) -> Decimal:
    return m.double(x)
```

On 0.0.12, forge wrote `import qualified Models as m`.
A Daml module alias must start with an upper-case letter, so damlc rejected it: `./B30.daml:3:28: error: parse error on input ‘m’`.

On 0.0.13, forge rejects the alias: `DF1213: Module alias m must start with an uppercase letter because Daml module aliases are constructors`.
forge does not rename the alias, but the error tells the user what to change.

## b31: a qualified enum value is not compiled

```python
import models as M


def cash() -> M.Kind:
    return M.Kind.CASH
```

On 0.0.12, forge wrote `(M.Kind).CASH`, and damlc rejected it: `./B31.daml:7:4: error: Not in scope: data constructor ‘M.Kind’`.

On 0.0.13, forge rejects the code:

```
DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
```

The code is valid, and the message is not correct: `M.Kind` is an enum name, not an expression.
In Daml, the qualified value is `M.CASH`.
With `from models import Kind` and `Kind.CASH`, forge writes the right `CASH`, and the Daml builds.
The same error comes with `import models` and `models.Kind.CASH`.

## b32: a plain module import cannot name a type

```python
from forge.models import ContractId
import models


def same(c: ContractId[models.Note]) -> ContractId[models.Note]:
    return c
```

forge rejects it with `DF1213: No builtin or user-defined type named models.Note (return type of same)`.
The same code with `import models as M` and `M.Note` compiles.
On 0.0.12, the cause was in `_qualified_import_type_names` (`forge/semantics/analysis/types.py:263`), which adds the type names of an imported module only for an import with an alias: `if alias.asname is None: continue`.

The program of b32 was first `-> models.Kind` with `return models.Kind.CASH`.
On 0.0.13, that program stops at b31 first, so it looked fixed.
The program now uses `models.Note`, which shows b32 alone.

## b33: a plain module import gives bad Daml for a call

```python
from forge.models import Decimal
import models


def twice(x: Decimal) -> Decimal:
    return models.double(x)
```

forge writes:

```
module B33PlainModuleImportCall where

import Models

twice : Decimal -> Decimal
twice x =
  models.double x
```

forge changes the module name to `Models` in the import line, but keeps the Python name `models` in the call.
A Daml qualifier must be a module name or an upper-case alias, so damlc rejects `models.double`.
forge must write `Models.double x`.

Proof with damlc (SDK 3.5.2), building forge's Daml of this program together with forge's `Models.daml` of `models.vy`:

```
./B33PlainModuleImportCall.daml:7:3: error:
    Variable not in scope: models
```

Two controls build.
The first is forge's Daml with only `models.double` changed to `Models.double`.
The second is the program with `import models as Models` and `Models.double(x)`.
