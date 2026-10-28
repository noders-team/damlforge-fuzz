# Analysis: import bugs on DamlForge 0.0.13

This analysis reads the report in this folder.
The run was `damlforge-fuzz run contracts/import_qualified contracts/import_sibling --damlc --count 20000 --random-seed 1`, on DamlForge `v0.0.12-4-g5da0584` (`forge_version` 0.0.13), dpm 1.0.22, and the Daml SDK 3.5.2.
The fuzzer was the code of unit 12 (imports), at commit ee09114 on `main`.

The run made 20000 inputs from the four import seeds: 3176 OK, 10783 rejected, 0 crash, and 6041 skipped.
The report has 0 crash groups, 21 bad Daml groups (`d01` to `d21`), and 0 import or loop groups.
Two more runs without damlc, with random seeds 2 and 3, also gave 0 crashes. Seed 2 gave one loop group.

The categories A to F have the same meaning as in [the loop report analysis](../2026-10-20T16-34-28Z/analysis.md).
In short: B is valid code that forge cannot compile right (bad Daml, or a DF error), C is valid code that crashes forge, and E is wrong code that forge accepts, and then damlc rejects the Daml.

## Summary

- Five bugs are open on 0.0.13. b31, b32, and b33 are import bugs, and their programs are in [`analysis/imports/`](analysis/imports/README.md). b34 and b35 are not import bugs, and their programs are in [`analysis/`](analysis/).
- b31 and b32 are DF1213 rejections of valid code.
- **b33** is new: after `import models` (no alias), a call `models.double(x)` gives Daml that damlc rejects.
- **b34** (a loop) and **b35** (a name clash) are new. The import seeds found them, but they are not import bugs.
- The import bugs b28, b29, and b30 are fixed on 0.0.13: forge gives `DF1213`. This analysis does not list them.
- The fuzzer found no import crash in 60000 inputs. forge now rejects most bad imports with a DF error.

The state of each bug was checked again on 2026-10-26, on damlforge-fuzz `main` at `2407b00`, with the same forge.

## The open bugs b31 to b35

Each program was written by hand. It is not fuzzer output.

| Bug | Category | Code | What happens | Program |
| --- | --- | --- | --- | --- |
| [b31](#b31-a-qualified-enum-value-is-rejected) | B | `import models as M`, then `M.Kind.CASH` | `DF1213: Uppercase member CASH cannot be selected from an expression` | [`analysis/imports/`](analysis/imports/README.md#b31-a-qualified-enum-value-is-rejected) |
| [b32](#b32-a-plain-module-import-cannot-name-a-type) | B | `import models`, then `models.Note` as a type | `DF1213: No builtin or user-defined type named models.Note` | [`analysis/imports/`](analysis/imports/README.md#b32-a-plain-module-import-cannot-name-a-type) |
| [b33](#b33-a-plain-module-import-gives-bad-daml-for-a-call) | B | `import models`, then `models.double(x)` | forge writes `models.double x`; damlc: `Variable not in scope: models` | [`analysis/imports/`](analysis/imports/README.md#b33-a-plain-module-import-gives-bad-daml-for-a-call) |
| [b34](#b34-a-value-set-in-a-loop-and-used-after-it) | B | `note = fetch(cid)` in a loop, then `note.lot.amount` after it | forge writes `fromSome x.lot`; damlc: `nonexistent field` | [`analysis/`](analysis/b34_loop_value_used_after_loop.vy) |
| [b35](#b35-a-template-with-the-name-of-an-enum-value) | B | `class Kind(Enum): CASH`, and `@template class CASH` | damlc: `Multiple declarations of ‘CASH’` | [`analysis/`](analysis/b35_template_named_like_enum_value.vy) |

This is the real output on `main`, for the two folders:

```
$ damlforge-fuzz check --damlc reports/2026-10-26T07-07-10Z/analysis/imports
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/imports/b31_qualified_enum_value.vy  DF1213: Uppercase member `CASH` cannot be selected from an expression; use an enum or module name
REJECTED check  reports/2026-10-26T07-07-10Z/analysis/imports/b32_plain_module_import_type.vy  DF1213: No builtin or user-defined type named `models.Note` (return type of `same`)
BAD_IMP  emit   reports/2026-10-26T07-07-10Z/analysis/imports/b33_plain_module_import_call.vy  I1: models. at Daml line 7 with no import that binds models; damlc rejects: Variable not in scope: models
OK       emit   reports/2026-10-26T07-07-10Z/analysis/imports/models.vy
```

```
$ damlforge-fuzz check --damlc reports/2026-10-26T07-07-10Z/analysis
BAD_DAML emit   reports/2026-10-26T07-07-10Z/analysis/b34_loop_value_used_after_loop.vy  Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘r0’
BAD_DAML emit   reports/2026-10-26T07-07-10Z/analysis/b35_template_named_like_enum_value.vy  Multiple declarations of ‘CASH’
```

### b31: a qualified enum value is rejected

forge rejects `M.Kind.CASH` after `import models as M`, with a message that is not correct: `M.Kind` is an enum name, not an expression.
The write-up is in [`analysis/imports/`](analysis/imports/README.md#b31-a-qualified-enum-value-is-rejected).
The run made 13 inputs of this kind, with three import forms: `import models as M`, `import models as Lib`, and `import models` (`models.Kind.CASH`).

### b32: a plain module import cannot name a type

forge rejects `models.Note` as a type after `import models`, but accepts `M.Note` after `import models as M`.
The write-up is in [`analysis/imports/`](analysis/imports/README.md#b32-a-plain-module-import-cannot-name-a-type).
The run made 18 inputs with this error, but most of them are correct rejections, such as `M.float` or `M.set`.

### b33: a plain module import gives bad Daml for a call

After `import models`, forge writes the call `models.double(x)` as `models.double x`. A Daml qualifier must be a module name, so damlc rejects it.
The write-up, with the damlc proof and two controls, is in [`analysis/imports/`](analysis/imports/README.md#b33-a-plain-module-import-gives-bad-daml-for-a-call).

This run did not find b33, for two reasons.
First, the import seeds use `M.Note` as a type, so when a rule changes `import models as M` to `import models`, b32 rejects the input before it gets to a call.
Second, the import check `I1` looked only at upper-case qualifiers.
After this run, `I1` finds b33 (commit `911d335`), and the seed `contracts/import_call/` imports only functions (commit `6003c7b`).
`run contracts/import_call --damlc --count 20000 --random-seed 1` finds b33 as group `i01`, first at input 4413, shrunk to 3 lines.

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
The control, the same program with the template named `Cash`, builds.
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
| 15 | `DF1213: Module alias … must start with an uppercase letter` (the fix of b30) |

Two small points:

- The import cycle message has the absolute path of the file, two times. A relative path is easier to read.
- forge supports `forge.models` only in `from forge.models import X`. `import forge.models as F` with `F.Decimal` gets `DF1213: No builtin or user-defined type named F.Decimal`. This is a limit, not a crash.

## Changes to the fuzzer after this run

- `contracts/loop_verify` has no `@ledger_effect`, which 0.0.13 rejects (commit `18dbd97`).
- `reports/2026-10-26T07-07-10Z/analysis/imports/` has only the open import bugs b31 to b33.
- `I1` finds b33, and the seed `contracts/import_call/` reaches it (commits `911d335` and `6003c7b`).
