# Import bugs b31 to b33

This folder has three small programs that show import bugs in DamlForge `5da0584` (`forge_version` 0.0.13).
All three were checked again on 2026-10-26, on damlforge-fuzz `main` at `2407b00`.
The numbers continue b01 to b30 ([the 20000-input analysis](../../../2026-10-19T18-45-34Z/analysis.md), [the loop report analysis](../../../2026-10-20T16-34-28Z/analysis.md), [the 0.0.13 import analysis](../../analysis.md)), and the categories are the categories of the 20000-input analysis.
The import bugs b28, b29, and b30 are fixed on 0.0.13, so this folder no longer has them. Commit `205b074` has their last programs and write-ups.

The fuzzer found b31 with the import seeds and the import check (unit 12).
b33 was found by hand on 0.0.13, and the fuzzer now finds it too, with the seed `contracts/import_call/`.
Each program here was made by hand, as small as it can be.
`models.vy` is the sibling module that the three programs import. It is not a bug program.

| Bug | Category | Code | What happens | Proof |
| --- | --- | --- | --- | --- |
| [b31](#b31-a-qualified-enum-value-is-rejected) | B | `import models as M`, then `M.Kind.CASH` | `DF1213: Uppercase member CASH cannot be selected from an expression` | forge's error; with `from models import Kind`, the code builds |
| [b32](#b32-a-plain-module-import-cannot-name-a-type) | B | `import models`, then `models.Note` as a type | `DF1213: No builtin or user-defined type named models.Note` | forge's error; with `import models as M`, the code builds |
| [b33](#b33-a-plain-module-import-gives-bad-daml-for-a-call) | B | `import models`, then `models.double(x)` | forge writes `models.double x` in the Daml | import check `I1`, and damlc: `Variable not in scope: models` |

Category B is valid code that forge cannot compile right.

Run all the programs with one command from the repository root.
This is the real output:

```
$ damlforge-fuzz check reports/2026-10-26T07-07-10Z/analysis/imports
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/imports/b31_qualified_enum_value.vy  DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Note` (return type of `same`)
BAD_IMP  emit   reports/2026-10-26T07-07-10Z/analysis/imports/b33_plain_module_import_call.vy  I1: models. at Daml line 7 with no import that binds models
OK       emit   reports/2026-10-26T07-07-10Z/analysis/imports/models.vy
```

The command exits with 1.
With `--damlc`, damlc builds each program's Daml together with forge's Daml of `models.vy`, and proves b33. It needs dpm and the Daml SDK 3.5.2:

```
$ damlforge-fuzz check --damlc reports/2026-10-26T07-07-10Z/analysis/imports
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/imports/b31_qualified_enum_value.vy  DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Note` (return type of `same`)
BAD_IMP  emit   reports/2026-10-26T07-07-10Z/analysis/imports/b33_plain_module_import_call.vy  I1: models. at Daml line 7 with no import that binds models; damlc rejects: Variable not in scope: models
OK       emit   reports/2026-10-26T07-07-10Z/analysis/imports/models.vy
```

## b31: a qualified enum value is rejected

```python
import models as M


def cash() -> M.Kind:
    return M.Kind.CASH
```

forge rejects the code:

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
The same code with `import models as M` and `M.Note` compiles, and the Daml builds.
On 0.0.12, the cause was in `_qualified_import_type_names` (`forge/semantics/analysis/types.py:263`), which adds the type names of an imported module only for an import with an alias: `if alias.asname is None: continue`.

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
0.0.12 has this bug too.

Proof with damlc (SDK 3.5.2), building forge's Daml of this program together with forge's `Models.daml` of `models.vy`:

```
./B33PlainModuleImportCall.daml:7:3: error:
    Variable not in scope: models
```

Two controls build.
The first is forge's Daml with only `models.double` changed to `Models.double`.
The second is the program with `import models as Models` and `Models.double(x)`.
