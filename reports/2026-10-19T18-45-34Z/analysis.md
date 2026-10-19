# Analysis: which groups are real DamlForge bugs

This analysis reads the report in this folder: `damlforge-fuzz run --damlc --count 20000 --random-seed 1` on DamlForge `v0.0.10` (one commit later, `forge_version` 0.0.11).
The report has 14 crash groups (`g01` to `g14`) and 30 bad Daml groups (`d01` to `d30`).

Many inputs of a fuzzer are nonsense code, such as `len(x)(0)` or a field named `tuple[int, str]`.
For nonsense code, the correct result is a forge error with a DF code.
So this analysis asks one question for each group: **what must a correct forge do with this input?**

| Category | Input | What forge did | Is it a real bug? |
| --- | --- | --- | --- |
| A | Valid code | Wrote Daml that builds but gives a wrong result | Yes. The most serious kind. |
| B | Valid code | Wrote Daml that damlc rejects | Yes. A user cannot compile correct code. |
| C | Valid code | Crashed | Yes. A user gets a Python traceback for correct code. |
| D | Wrong code | Crashed instead of a DF error | Yes, in error handling. The user gets a traceback instead of a clear message. |
| E | Wrong code | Accepted it and wrote Daml that damlc rejects | A gap in forge's checks. The user still gets an error, but from damlc, in the generated Daml. |

For categories A to D, each bug has a small program in [`analysis/`](analysis/) that a user can really write.
Each program is not fuzzer output: it was written by hand to prove the bug.

## The 16 confirmed bugs

| Bug | Category | Code | What happens | Report groups |
| --- | --- | --- | --- | --- |
| [b01](#b01-list-assignment-does-nothing) | A | `xs[0] = 0` on a list | The assignment does nothing | `d10` |
| [b02](#b02-map-assignment-does-nothing) | A | `votes[voter] = True` on a `GenMap` | The assignment does nothing | (found in unit 1) |
| [b03](#b03-empty-observer-list) | B | `observer: list[Party] = []` | damlc: ambiguous type | `d16` |
| [b04](#b04-module-level-constant) | B | `limit = 10` at the top of the file | damlc: `limit` not in scope | `d17` |
| [b05](#b05-upper-case-local-name) | B | `FEE = 10` in a function | damlc: reads `FEE` as a constructor | `d14`, `d15`, `d29` |
| [b06](#b06-to-b08-genmap-operations) | B | `voter in votes` on a `GenMap` | damlc: type error | (found in unit 1) |
| [b07](#b06-to-b08-genmap-operations) | B | `voter not in votes` on a `GenMap` | damlc: type error | (found in unit 1) |
| [b08](#b06-to-b08-genmap-operations) | B | `votes.values()` on a `GenMap` | damlc: no field `values` | (found in unit 1) |
| [b09](#b09-and-b10-bitwise-operators) | C | `a >> 1` (also `<<`, `&`, `\|`, `^`) | `KeyError` at `forge/ir/lower.py:289` | `g07` |
| [b10](#b09-and-b10-bitwise-operators) | C | `~a` | `KeyError` at `forge/ir/lower.py:298` | `g14` |
| [b11](#b11-loop-with-a-total-and-an-early-return) | C | a `for` loop that adds to a total and can `return` early | `CompilerPanic` at `forge/codegen/emit.py:596` | `g11` |
| [b12](#b12-local-declaration-without-a-value) | C | `b: int` in a function | `CompilerPanic` at `forge/codegen/emit.py:271` | `g06`, `g10` |
| [b13](#b13-import-inside-a-function) | C | `import math` in a function | `CompilerPanic` at `forge/ir/lower.py:314` | `g01` |
| [b14](#b14-typo-in-the-forge-import) | D | `from forge.modles import ...` | `ModuleNotFoundError` at `forge/semantics/analysis/imports.py:108` | `g12` |
| [b15](#b15-wrong-indent-level) | D | a line that goes back to a wrong indent level | `IndentationError` at `forge/ast/pre_parser.py:304` | `g03` |
| [b16](#b16-unknown-name) | E | `return b` with no `b` | no DF error; damlc: `b` not in scope | `d02`, `d13`, `d25` |

Run all 16 programs with one command.
This is the real output:

```
$ damlforge-fuzz check --damlc reports/2026-10-19T18-45-34Z/analysis
OK       emit   .../analysis/b01_list_assign.vy
OK       emit   .../analysis/b02_map_assign.vy
BAD_DAML emit   .../analysis/b03_empty_observer.vy  Ambiguous type variable ‘a0’ arising from a use of ‘toParties’
BAD_DAML emit   .../analysis/b04_module_constant.vy  Variable not in scope: limit : Int
BAD_DAML emit   .../analysis/b05_upper_case_local.vy  Not in scope: data constructor ‘FEE’
BAD_DAML emit   .../analysis/b06_map_in.vy  Couldn't match expected type ‘[Party]’
BAD_DAML emit   .../analysis/b07_map_not_in.vy  Couldn't match expected type ‘[Party]’
BAD_DAML emit   .../analysis/b08_map_values.vy  Tried to access nonexistent field ‘values’ with type ‘[Bool]’ on value of type ‘Map
CRASH    lower  .../analysis/b09_bit_shift.vy  KeyError 'RShift' at forge/ir/lower.py:289
CRASH    lower  .../analysis/b10_bit_invert.vy  KeyError 'Invert' at forge/ir/lower.py:298
CRASH    emit   .../analysis/b11_loop_early_return.vy  CompilerPanic _translate_for: a `for` loop with both loop-carried accumulator mutation and an early `return` inside its body is not supported at forge/codegen/emit.py:596
CRASH    emit   .../analysis/b12_local_declaration.vy  CompilerPanic render_expr: unsupported IR expression NoneType at forge/codegen/emit.py:271
CRASH    lower  .../analysis/b13_import_in_function.vy  CompilerPanic lower_stmt: unsupported statement node Import at forge/ir/lower.py:314
CRASH    check  .../analysis/b14_import_typo.vy  ModuleNotFoundError No module named 'forge.modles' at forge/semantics/analysis/imports.py:108
CRASH    parse  .../analysis/b15_dedent_mismatch.vy  IndentationError unindent does not match any outer indentation level (<string>, line 4) at forge/ast/pre_parser.py:304
BAD_DAML emit   .../analysis/b16_undefined_name.vy  Variable not in scope: b : Int
```

## Category A: wrong results with no error

These two bugs are the most serious.
forge says OK, damlc builds the Daml, and the contract then does the wrong thing.
The fuzzer cannot find this kind of bug, because it sees only that forge and damlc agree.
`d10` led to b01: its input has `x[0] = datetime.now()`, and forge wrote `x._1 <- getTime`.

### b01: list assignment does nothing

```python
def reset_first(xs: list[int]) -> list[int]:
    xs[0] = 0
    return xs
```

forge writes this Daml:

```haskell
reset_first : [Int] -> [Int]
reset_first xs =
  let xs._1 = 0 in
  xs
```

The `let` does not change `xs`, so the function returns `xs` as it was.

### b02: map assignment does nothing

```python
def mark(votes: GenMap[Party, bool], voter: Party) -> GenMap[Party, bool]:
    votes[voter] = True
    return votes
```

forge writes `let (votes) !! (voter) = True in votes`.
This defines a local operator `!!` and returns `votes` as it was.
On DamlForge `v0.0.7`, damlc rejects this Daml with `parse error on input ‘!!’`.
On `v0.0.10`, damlc builds the same line.
So a change in forge made a bug that damlc reported into a silent one.

### The proof

[`analysis/runtime/`](analysis/runtime/) is a Daml project with forge's Daml for b01 and b02 and a test script.
`dpm test` in that folder gives:

```
daml/Test.daml:control_map_insert_works: ok, 0 active contracts, 0 transactions.
daml/Test.daml:map_assignment_adds_the_voter: failed
daml/Test.daml:list_assignment_sets_first_element: failed
```

The failures are `expected [5,6] == [0,6]` for b01 and `expected False == True` for b02.
The control test calls `Map.insert` directly and passes, so the test setup is correct.
The `.daml` files in `runtime/daml/` are a copy of what DamlForge `v0.0.10` wrote.

## Category B: valid code, Daml that damlc rejects

### b03: empty observer list

A contract with no observers is common in Daml.
`observer: list[Party] = []` in `iou.vy` becomes `observer []`, and damlc cannot find the type of `[]`.
forge must write the type, for example `observer ([] : [Party])`.
Group `d16` is the same bug with `signatory: list[Party] = []`.
An empty signatory list is not allowed in Daml, so for `d16` forge must give a DF error.

### b04: module-level constant

```python
limit = 10


def over_limit(a: int) -> bool:
    return a > limit
```

forge drops the assignment at the top of the file, so damlc reports `Variable not in scope: limit`.
With an upper-case name, `LIMIT = 10`, damlc reports `Data constructor not in scope: LIMIT`.
Group `d17` adds `x = 1` at the top of a file, and damlc stops with "this feature is not currently supported".

### b05: upper-case local name

Python code often uses upper-case names for constants, such as `FEE = 10`.
In Daml, a name that starts with an upper-case letter is a constructor or a type, so `let FEE = 10` is wrong.
forge must rename such names.
Groups `d14` (a struct field named `Party`), `d15` (a loop variable named `Decimal`), and `d29` (a local variable named `Ballot`) are the same bug.

### b06 to b08: GenMap operations

Unit 1 found these bugs while it wrote the seeds, and they are still in `v0.0.10`:

- `voter in votes` becomes a list `elem`, which needs a list, not a map.
- `voter not in votes` has the same problem.
- `votes.values()` becomes field access, `votes.values`.

The seed `ballot.vy` uses `M.insert(...)` and `M.values(...)` to avoid these bugs.
So the fuzzer seldom reaches them.

## Category C: valid code, forge crashes

### b09 and b10: bitwise operators

`a >> 1`, `a << 1`, `a & 1`, `a | 1`, `a ^ 1`, and `~a` are valid Python.
forge's check step accepts them, but the lower step has no entry for them in `_BIN_OPS` or `_UNARY_OPS`.
forge must translate them or reject them in the check step with a DF error.

### b11: loop with a total and an early return

```python
def first_large(xs: list[int]) -> int:
    total = 0
    for x in xs:
        if x > 100:
            return x
        total = total + x
    return total
```

forge's message says that this loop is not supported.
That is a known limit, but forge raises `CompilerPanic`, which is an internal error that asks the user to file a bug.
It must be a DF error.

### b12: local declaration without a value

`b: int` on its own line in a function is valid Python.
forge turns it into nothing, and the emit step crashes on the empty value.
Groups `g06` and `g10` are the same bug, with `organizer: Party` and `issuer: Party` in a function.

### b13: import inside a function

`import math` in a function is valid Python.
forge's check step accepts it, and the lower step has no handler for `Import`.
forge must reject it in the check step with a DF error.

## Category D: wrong code, forge crashes instead of a DF error

### b14: typo in the forge import

`from forge.modles import Party` raises Python's `ModuleNotFoundError`.
forge already has a DF error for unknown modules: `from str.models import ...` gives `DF1213: No module named str.models`.
Imports under `forge.` skip that check.
Group `g12` is the same bug with `from forge.AssetProposal import ...`.

### b15: wrong indent level

```python
def larger(a: int, b: int) -> int:
    if a > b:
        c = a
      return c
    return b
```

Line 4 goes back to an indent level that no earlier line has.
Python's tokenizer raises `IndentationError`, and forge's pre-parser does not catch it.
A line with too much indent is handled correctly: forge reports `SyntaxException: unexpected indent`.
Group `g03` has 249 inputs, the second most of all crash groups, and a user can easily make this mistake.

### Other crash groups in this category

These groups crash on code that is clearly wrong.
A user will seldom write it, but forge must still give a DF error.
The shrunk input of each group is in `groups/<id>/shrunk/`.

| Group | Wrong code | forge error |
| --- | --- | --- |
| `g02`, `g09` | a type before `:` in a field, such as `tuple[int, str]: EscrowTerms` | `AttributeError` at `forge/semantics/analysis/types.py:644` (template) and `:630` (struct). One fix for both: check that the field name is a plain name. |
| `g04` | a value as a field type, `amount: 0.0` | `CompilerPanic` at `forge/ir/lower.py:115`, in the check step |
| `g05` | a broken line with `for` in a comprehension | `AssertionError` at `forge/ast/parse.py:106` |
| `g08` | `"split "x" must ..."`, a name between two strings | `AssertionError` at `forge/ast/parse.py:110` |
| `g13` | `for in_favor "" answers:` | `IndexError` at `forge/ast/pre_parser.py:389` |

## Category E: wrong code that forge accepts

### b16: unknown name

```python
def broken(a: int) -> int:
    return b
```

forge has an error for this case, `DF1219: `b` is not defined`.
But it uses it only for a name before a dot, such as `b` in `b.x`.
So `return b` passes, and damlc reports `Variable not in scope: b`.
`docs/progress.md` recorded this gap in unit 1.
Groups `d02` (`len(x)`), `d13` (a renamed parameter), and `d25` (a parameter of another choice) are the same gap.

### The other bad Daml groups

In each of these groups, the fuzzer made wrong code, and forge did not see the error.
The user gets an error from damlc that points into the generated Daml, not into the `.vy` file.

| Kind of check that forge does not do | Groups |
| --- | --- |
| A call to a template or struct with a missing, unknown, or repeated field | `d01` (missing `owner`), `d07` (`float=`), `d18` (`issuer=` after the field was deleted), `d20` (`issuer=` two times; Python's `compile()` rejects this, but `ast.parse()` accepts it) |
| An unknown field of `self` | `d06` (`self.x`), `d23` (`self.consuming`) |
| Two declarations with one name | `d08` (field), `d11` (template), `d26` (function) |
| The return type | `d04` (returns `Iou`, not `ContractId[Iou]`), `d05` (a tuple of 1, not 2), `d12` (a function with `-> bool` and no `return`) |
| Other types | `d09` (`controller=True`), `d24` (`not in` on a time), `d30` (a template in the observer list) |
| A name that is not a type, in a type | `d03` (`ContractId[int](...)`), `d27` (`GenMap[self, bool]`), `d28` (the choice name `Reject` as a type) |
| A name that is valid in Python but not in Daml | `d19` (a choice `currency` next to a field `currency`), `d21` (a choice named `bool`), `d22` (a field named `self`) |

Groups `d10`, `d14`, `d15`, `d16`, `d17`, and `d29` are in the tables of bugs b01, b03, b04, and b05 above.

## Priority

1. **b01 and b02.** The contract gives wrong results, and no tool shows an error.
2. **b03, b04, b05, b11, b12.** Normal, correct code fails. An empty observer list, a constant, an upper-case constant, a loop with an early return, and a typed local variable are common in real contracts.
3. **b06, b07, b08.** Normal map code fails. Users can avoid it with the `M.` functions, as the seeds do.
4. **b09, b10, b13, b14, b15.** Correct or nearly correct code gives a Python traceback. A DF error is enough to fix each one.
5. **Category D table and category E.** Wrong code gets a bad message. Each fix is a new check in forge's check step.

## Limits of this analysis

- The report and the output above are from DamlForge `v0.0.10` (`v0.0.10-1-gc11b5fe`). On `v0.0.7`, all 16 programs give the same results, with other forge line numbers, except b02: there, damlc rejects its Daml (`parse error on input ‘!!’`).
- b01 to b16 are small programs written by hand. The fuzzer found the groups, and the programs show that the same bug happens with code that a user can write.
- Whether forge or damlc must catch a category E error is a design choice of DamlForge. This analysis assumes that forge must, because forge already has DF codes for several of these checks.
- A bad Daml group is one kind of damlc error, with the names hidden. One group can hold more than one forge bug. This analysis looked only at the first input of each group.

## Repeat this analysis

```sh
damlforge-fuzz check --damlc reports/2026-10-19T18-45-34Z/analysis
cd reports/2026-10-19T18-45-34Z/analysis/runtime && dpm test
```

The first command needs DamlForge and dpm. The second command needs dpm and the Daml SDK 3.5.2.
