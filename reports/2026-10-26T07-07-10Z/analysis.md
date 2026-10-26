# Analysis: import bugs on DamlForge 0.0.13

This analysis reads the report in this folder.
The run was `damlforge-fuzz run contracts/import_qualified contracts/import_sibling --damlc --count 20000 --random-seed 1`, on DamlForge `v0.0.12-4-g5da0584` (`forge_version` 0.0.13), dpm 1.0.22, and the Daml SDK 3.5.2.
The fuzzer was the code of unit 12 (imports), at commit c1d3dd4 on `main`.

The run made 20000 inputs from the four import seeds: 3176 OK, 10783 rejected, 0 crash, and 6041 skipped.
The report has 0 crash groups, 21 bad Daml groups (`d01` to `d21`), and 0 import or loop groups.
Two more runs without damlc, with random seeds 2 and 3, also gave 0 crashes. Seed 2 gave one loop group.

The categories A to F have the same meaning as in [the loop report analysis](../2026-10-20T16-34-28Z/analysis.md).
In short: B is valid code that forge cannot compile right (bad Daml, or a DF error), C is valid code that crashes forge, and E is wrong code that forge accepts, and then damlc rejects the Daml.

## Summary

- forge 0.0.13 fixed b28, b29, and b30. Each one now gets a clear `DF1213` error, not a crash or bad Daml.
- b31 and b32 are not fixed. forge now rejects the code with a `DF1213` error, but the code is valid.
- New import bug **b33**: after `import models` (no alias), a call `models.double(x)` gives Daml that damlc rejects.
- Two more new bugs come from the import seeds, but they are not import bugs: **b34** (a loop) and **b35** (a name clash).
- The fuzzer found no import crash in 60000 inputs. forge now rejects most bad imports with a DF error.

## The import bugs b28 to b35

The programs of b28 to b30 are in [`bugs/imports/`](../../bugs/imports/README.md).
The programs of b31 to b35 for this version are in [`analysis/`](analysis/). They import [`analysis/models.vy`](analysis/models.vy).
Each program was written by hand. It is not fuzzer output.

| Bug | Category | Code | Result on 0.0.13 | State |
| --- | --- | --- | --- | --- |
| b28 | C | `from . import models` | `DF1213: Relative imports are not supported` | Fixed |
| b29 | C | `import forge.math as m`, and an enum | `DF1213: No module named forge.math` | Fixed |
| b30 | B | `import models as m` | `DF1213: Module alias m must start with an uppercase letter` | Fixed (forge rejects; it does not rename) |
| [b31](#b31-a-qualified-enum-value-is-rejected) | B | `import models as M`, then `M.Kind.CASH` | `DF1213: Uppercase member CASH cannot be selected from an expression` | Open: was bad Daml, now rejected |
| [b32](#b32-a-plain-module-import-cannot-name-a-type) | B | `import models`, then `models.Note` as a type | `DF1213: No builtin or user-defined type named models.Note` | Open |
| [b33](#b33-a-plain-module-import-gives-bad-daml-for-a-call) | B | `import models`, then `models.double(x)` | forge writes `models.double x`; damlc: `Variable not in scope: models` | New. 0.0.12 has it too. |
| [b34](#b34-a-value-set-in-a-loop-and-used-after-it) | B | `note = fetch(cid)` in a loop, then `note.lot.amount` after it | forge writes `fromSome x.lot`; damlc: `nonexistent field` | New, not an import bug |
| [b35](#b35-a-template-with-the-name-of-an-enum-value) | B | `class Kind(Enum): CASH`, and `@template class CASH` | damlc: `Multiple declarations of ‘CASH’` | New, not an import bug |

This is the real output for the programs in `analysis/`:

```
$ damlforge-fuzz check --damlc reports/2026-10-26T07-07-10Z/analysis
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/b31_qualified_enum_value.vy  DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Note` (return type of `same`)
BAD_DAML emit   reports/2026-10-26T07-07-10Z/analysis/b33_plain_module_import_call.vy  Variable not in scope: models
BAD_DAML emit   reports/2026-10-26T07-07-10Z/analysis/b34_loop_value_used_after_loop.vy  Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘r0’
BAD_DAML emit   reports/2026-10-26T07-07-10Z/analysis/b35_template_named_like_enum_value.vy  Multiple declarations of ‘CASH’
OK       emit   reports/2026-10-26T07-07-10Z/analysis/models.vy
```

### b31: a qualified enum value is rejected

```python
import models as M


def cash() -> M.Kind:
    return M.Kind.CASH
```

On 0.0.12, forge wrote the bad Daml `(M.Kind).CASH`. On 0.0.13, forge rejects the code:

```
DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
```

The message is not correct. `M.Kind` is an enum name, not an expression.
The correct Daml is `M.CASH`.
`from models import Kind` with `Kind.CASH` compiles and builds.
The fuzzer made 13 inputs of this kind, with three import forms: `import models as M`, `import models as Lib`, and `import models` (`models.Kind.CASH`).

### b32: a plain module import cannot name a type

```python
from forge.models import ContractId
import models


def same(c: ContractId[models.Note]) -> ContractId[models.Note]:
    return c
```

forge rejects it with `DF1213: No builtin or user-defined type named models.Note (return type of same)`.
The same code with `import models as M` and `M.Note` compiles.
The first program of b32 in `bugs/imports/` stops at b31 first (`models.Kind.CASH`), so it looked fixed. It is not fixed. `bugs/imports/` now has this program.
The fuzzer made 18 inputs with this error, but most of them are correct rejections, such as `M.float` or `M.set`.

### b33: a plain module import gives bad Daml for a call

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
A Daml qualifier must be the module name or an upper-case alias, so damlc rejects `models.double`:

```
Variable not in scope: models
```

The correct call is `Models.double x`.
The control, `import models as Models` with `Models.double(x)`, builds.

The fuzzer did not find b33 in this run.
The import rules make `import models` from `import models as M`, and then rewrite every `M.` to `models.`.
The seeds use `M.Note` as a type, so b32 rejects those inputs before they get to the call.
The import check `I1` also does not see b33, because it checks only upper-case qualifiers. A lower-case `x.y` is usually a field access.

### b34: a value set in a loop and used after it

```python
@choice(controller=owner, consuming=False)
def Size(self, cid: ContractId[Note]) -> Decimal:
    for _k in range(0, 2):
        note = fetch(cid)
    return note.lot.amount
```

forge keeps the last `note` of the loop as an `Optional` value, and writes:

```
pure ((fromSome _damlforge__damlforge_post_note13.lot).amount)
```

In Daml, `.lot` binds before the function call, so this is `fromSome (x.lot)` on an `Optional` value. damlc rejects it:

```
Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘r0’
```

The correct Daml is `((fromSome x).lot).amount`.
That Daml, changed by hand, builds with `dpm build`.
Groups `d06`, `d15`, and `d19` have this shape. The full program is [`analysis/b34_loop_value_used_after_loop.vy`](analysis/b34_loop_value_used_after_loop.vy).

### b35: a template with the name of an enum value

```python
class Kind(Enum):
    CASH = auto()


@template
class CASH:
    owner: Party

    signatory: list[Party] = [owner]
```

In Python, `Kind.CASH` and the class `CASH` are different names.
In Daml, an enum value is a constructor at the top level of the module, so `data Kind = CASH` and `template CASH` declare `CASH` two times.
damlc: `Multiple declarations of ‘CASH’`.
forge must reject the code with a DF error, or rename one of the two.
Group `d14` shows it, in a sibling module (`models.vy`).

## The 21 bad Daml groups

Each group gets the category of the code that it shows.
"Wrong code" means that the input is not valid, and the correct result is a DF error from forge.

| Group | Count | Change to the seed | Category | Bug |
| --- | --- | --- | --- | --- |
| d01 | 159 | `return x + int` | E | a type name used as a value |
| d02 | 115 | a struct field named `Party` | B | b05 (upper-case name) |
| d03 | 33 | a function with no `return` | E | |
| d04 | 45 | `lot=Decimal` | E | a type name used as a value |
| d05 | 28 | `observer: list[Party] = []` | B | b03 (empty observer list) |
| d06 | 76 | `note = fetch(cid)` in a loop | B | b34 |
| d07 | 18 | `controller=-9223372036854775808` | E | |
| d08 | 6 | a function named `Int` | B | b05 (upper-case name) |
| d09 | 2 | `fetch` of `ContractId[TextMap[str]]` | E | |
| d10 | 7 | `note.lot.range(0, 3)` | E | |
| d11 | 22 | a choice named `ContractId` | E | a name clash with a Daml type |
| d12 | 37 | `amount: ContractId[int]` used as a `Decimal` | E | |
| d13 | 11 | `M.Note(str=...)`, `note.date(...)` | E | |
| d14 | 2 | `class CASH` in `models.vy` | B | b35 |
| d15 | 10 | `M.Party(...)` used as a template | E | first error; the input also has b34 |
| d16 | 15 | a new field `lot: Lot` in the struct `Lot`, and `Lot(...)` calls without it | E | a missing field in a constructor call |
| d17 | 2 | a choice returns a `Decimal` as `Party` | E | |
| d18 | 4 | a bare `return` in a function that returns `Lot` | E | |
| d19 | 1 | a loop, and a wrong return type | E | first error; the input also has b34 |
| d20 | 1 | `create(cid)` | E | |
| d21 | 1 | `[](kind=..., amount=...)` | E | |

Only `d15` and `d13` use a qualified import name (`M.Party`, `M.Note`), and both are wrong code.
`M.Party` is a name that `models.vy` imports, not a name that it declares. forge rejects `M.Party` as a type, but accepts it as a template call.

## Import errors that forge now gives

The 20000 inputs got these import errors. Each one is a correct DF error for wrong code, or a limit that forge states.
The counts come from a replay of the inputs with forge, without damlc.

| Count | forge's error |
| --- | --- |
| 117 | `DF1213: Relative imports are not supported` |
| 116 | `DF1213: No name … in module …` |
| 72 | `DF1213: Imports are only supported at module scope` |
| 70 | `DF1213: … is already imported earlier in this module` |
| 112 | `DF1213: No module named …` |
| 56 | `DF1213: Import cycle detected` (`models.vy` imports itself) |
| 37 | `DF1213: Aliased imports (from x import a as b) are not supported` |
| 15 | `DF1213: Module alias … must start with an uppercase letter` (b30) |

Two small points:

- The import cycle message has the absolute path of the file, two times. A relative path is easier to read.
- forge supports `forge.models` only in `from forge.models import X`. `import forge.models as F` with `F.Decimal` gets `DF1213: No builtin or user-defined type named F.Decimal`. This is a limit, not a crash.

## Other changes on 0.0.13

- The seed `contracts/loop_verify/loop_verify.vy` is now rejected: `DF1213: No name ledger_effect in module forge.models`. forge removed `ledger_effect` in commit `9d5387d`. A run on all of `contracts/` needs this seed changed.

## Open items for the fuzzer

- Make the import check see b33: a lower-case qualifier in the Daml that is the name of a plain `import X` in the `.vy` text. Done after this report: `I1` finds it.
- Add a seed that uses a plain `import models` only in calls, not in types, so that the import rules get past b32 to b33. Done after this report: `contracts/import_call/`. `run contracts/import_call --damlc --count 20000 --random-seed 1` finds b33 as group `i01`, first at input 4413, shrunk to 3 lines.
- Change `contracts/loop_verify` for 0.0.13. Done after this report: the seed has no `@ledger_effect`.
- Update `bugs/imports/README.md` for 0.0.13. Done after this report, with b33 added.
