# Analysis: which groups are real DamlForge bugs

This analysis reads the report in this folder.
The run was `damlforge-fuzz run contracts/loop_* --damlc --compare --count 20000 --random-seed 1`, on DamlForge `v0.0.10-1-gc11b5fe` (`forge_version` 0.0.11) and the Daml SDK 3.5.2.
The fuzzer was the code of unit 11 (`--compare`), at commit 1fab1bc on `main`.

The run made 20000 inputs from the five loop seeds: 4092 OK, 10205 rejected, 1643 crash, and 4060 skipped.
The report has 12 crash groups (`g01` to `g12`), 33 bad Daml groups (`d01` to `d33`), 5 loop groups (`l01` to `l05`), and 3 run groups (`r01` to `r03`).

Many inputs of a fuzzer are nonsense code, such as `len(x) + x` on a number or a field named `tuple[int, str]`.
For nonsense code, the correct result is a forge error with a DF code.
So this analysis asks one question for each group: **what must a correct forge do with this input?**

The categories A to E have the same meaning as in [the analysis of the first 20000-input report](../2026-10-19T18-45-34Z/analysis.md). Category F is new.

| Category | Input | What forge did | Is it a real bug? |
| --- | --- | --- | --- |
| A | Valid code | Wrote Daml that builds but gives a wrong result | Yes. The most serious kind. |
| B | Valid code | Wrote Daml that damlc rejects | Yes. A user cannot compile correct code. |
| C | Valid code | Crashed | Yes. A user gets a Python traceback for correct code. |
| D | Wrong code | Crashed instead of a DF error | Yes, in error handling. The user gets a traceback instead of a clear message. |
| E | Wrong code | Accepted it and wrote Daml that damlc rejects | A gap in forge's checks. The user still gets an error, but from damlc, in the generated Daml. |
| F | Wrong code, with one name declared two times | Kept one declaration with no error, and wrote Daml that damlc builds | Yes, in error handling. No tool gives an error, and the contract does what only one of the two declarations says. |

The first analysis put "two declarations with one name" in category E, because damlc rejected the Daml.
For b25, and for one form of b26, damlc builds the Daml, so category E does not fit.
If DamlForge decides that the last declaration wins, as in Python, these bugs are category A.

The loop groups and the run groups fit categories A, B, and E.
They still get [a section of their own](#loop-and-run-groups), for two reasons.
First, the loop work is the customer's priority.
Second, one loop group or run group can hold more than one bug.
A loop group holds all the inputs with the same first loop check and the same damlc verdict.
A run group holds all the inputs with the same kind of difference and the same first loop check.
For example, `l01` holds inputs of b21 and of b22.

For each new bug, b24 to b27, a small program in [`analysis/`](analysis/) shows that a user can really write the code.
Each program was written by hand. It is not fuzzer output.

## The confirmed bugs

b01 to b16 are from [the first analysis](../2026-10-19T18-45-34Z/analysis.md), and b17 to b23 are from [`bugs/loops/`](../../bugs/loops/README.md).
Their write-ups are there. This analysis gives only the groups of this report that show them.
b24 to b27 are new.

| Bug | Category | Code | What happens | Groups in this report |
| --- | --- | --- | --- | --- |
| [b01](../2026-10-19T18-45-34Z/analysis.md#b01-list-assignment-does-nothing) | A | `xs[0] = 0` on a list | The assignment does nothing | none |
| [b02](../2026-10-19T18-45-34Z/analysis.md#b02-map-assignment-does-nothing) | A | `votes[voter] = True` on a `GenMap` | The assignment does nothing | none |
| [b03](../2026-10-19T18-45-34Z/analysis.md#b03-empty-observer-list) | B | `observer: list[Party] = []` | damlc: ambiguous type | `d14` |
| [b04](../2026-10-19T18-45-34Z/analysis.md#b04-module-level-constant) | B | `limit = 10` at the top of the file | forge drops the line. damlc: `limit` not in scope | none |
| [b05](../2026-10-19T18-45-34Z/analysis.md#b05-upper-case-local-name) | B | An upper-case name, such as `FEE = 10` | damlc reads the name as a constructor | `d09`, `d21` |
| [b06 to b08](../2026-10-19T18-45-34Z/analysis.md#b06-to-b08-genmap-operations) | B | `in`, `not in`, and `.values()` on a `GenMap` | damlc: type error | none |
| [b09](../2026-10-19T18-45-34Z/analysis.md#b09-and-b10-bitwise-operators) | C | `a >> 1` (also `<<`, `&`, `\|`, `^`) | `KeyError` at `forge/ir/lower.py:289` | `g09` |
| [b10](../2026-10-19T18-45-34Z/analysis.md#b09-and-b10-bitwise-operators) | C | `~a` | `KeyError` at `forge/ir/lower.py:298` | `g11` |
| [b11](../2026-10-19T18-45-34Z/analysis.md#b11-loop-with-a-total-and-an-early-return) | C | A loop that adds to a total and can `return` early | `CompilerPanic` at `forge/codegen/emit.py:596` | `g03` |
| [b12](../2026-10-19T18-45-34Z/analysis.md#b12-local-declaration-without-a-value) | C | `b: int` in a function | `CompilerPanic` at `forge/codegen/emit.py:271`, or at `forge/codegen/loops.py:354` after a loop | `g07`, `g12` |
| [b13](../2026-10-19T18-45-34Z/analysis.md#b13-import-inside-a-function) | C | `import math` in a function | `CompilerPanic` at `forge/ir/lower.py:314` | `g04` |
| [b14](../2026-10-19T18-45-34Z/analysis.md#b14-typo-in-the-forge-import) | D | `from forge.modles import ...` | `ModuleNotFoundError` at `forge/semantics/analysis/imports.py:108` | `g06` |
| [b15](../2026-10-19T18-45-34Z/analysis.md#b15-wrong-indent-level) | D | A line that goes back to a wrong indent level | `IndentationError` at `forge/ast/pre_parser.py:304` | `g02` |
| [b16](../2026-10-19T18-45-34Z/analysis.md#b16-unknown-name) | E | `return b` with no `b` | No DF error. damlc: `b` not in scope | `d04`, `d05`, `d06`, `d08`, `d16`, `d33` |
| [b17](../../bugs/loops/README.md#b17-create-inside-append-loses-the-import) | B | `cids.append(create(...))` in a loop in a choice | `foldlA` with no import | `l04` |
| [b18](../../bugs/loops/README.md#b18-fetch-inside-a-sum-loses-the-import) | B | `total = total + fetch(c).amount` in a loop in a choice | `foldlA` with no import | none |
| [b19](../../bugs/loops/README.md#b19-fetch-in-an-if-test-stays-in-a-pure-foldl) | B | `if fetch(c).amount > ...:` in a loop in a choice | `fetch` stays in the test. damlc: type error | `l02`, and 11 inputs of `l03` |
| [b20](../../bugs/loops/README.md#b20-a-top-level-function-gets-no-df1205-check) | E | `fetch(c)` in a top-level function without `@ledger_effect` | No DF1205. damlc: type error | `l03` |
| [b21](../../bugs/loops/README.md#b21-return-in-the-loop-works-as-continue) | A | `return` in a loop of a choice that has a ledger action or an `assert` | `return` works as `continue` | `l05` (a `return` with a value, which damlc rejects), and 17 inputs of `l01` |
| [b22](../../bugs/loops/README.md#b22-return-in-an-inner-loop-removes-both-loops) | A | `return` in an inner loop of a function | forge writes no code for the loops | `l01`, `r01` |
| [b23](../../bugs/loops/README.md#b23-pass-drops-the-rest-of-its-block) | A | `pass` in a block | forge drops the statements after the `pass` | `r02`, `r03` |
| [b24](#b24-a-loop-in-a-plain-function-loses-its-asserts) | A | A loop in a plain function whose body is not one `assert` alone | forge writes no code for the loop, so every `assert` in it is lost | none |
| [b25](#b25-a-second-signatory-observer-or-ensure-line-is-lost) | F | Two `signatory`, `observer`, or `ensure` lines in a template | forge keeps the first line and drops the second | none. Input 11691 is in `d08`. |
| [b26](#b26-a-template-method-that-is-not-a-choice-is-lost) | B, F | A method without `@choice` in a template | forge drops the method with no error | none |
| [b27](#b27-an-int-literal-next-to-a-decimal) | B | `amount > 0` with a `Decimal` `amount` | forge writes `0`, which is an `Int` in Daml. damlc: type error | `d23` |

Run the programs of the new bugs with one command.
This is the real output. The command exits with 1:

```
$ damlforge-fuzz check --damlc --compare reports/2026-10-20T16-34-28Z/analysis
CRASH    emit   reports/2026-10-20T16-34-28Z/analysis/b12_declaration_after_loop.vy  CompilerPanic apply_renames: unsupported IR expression NoneType at forge/codegen/loops.py:354
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/b21_return_value_in_choice_loop.vy  L3: the return in a loop of choice FirstLarge at Daml line 14 is lost (1 loop with a return, 0 early-return helpers); damlc rejects: Couldn't match type ‘Numeric 10’ with ‘()’
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/b24_assert_in_if_in_function.vy  daml_passes in Iou.Check #2: fails: over the limit
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/b24_two_asserts_in_function.vy  daml_passes in Iou.Check #2: fails: positive
OK       emit   reports/2026-10-20T16-34-28Z/analysis/b25_two_ensure_lines.vy
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/b25_two_signatory_lines.vy  daml_passes in Iou.Give #1: fails: create of Iou without the authority of its signatories
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/b26_choice_and_method_same_name.vy  result in Iou.Fee #1: returns 2.0, makes no contract
BAD_DAML emit   reports/2026-10-20T16-34-28Z/analysis/b26_helper_method.vy  Tried to access nonexistent field ‘fee’ with type ‘Decimal’ on value of type ‘Iou’
BAD_DAML emit   reports/2026-10-20T16-34-28Z/analysis/b27_int_literal_with_decimal.vy  Couldn't match type ‘Int’ with ‘Numeric 10’
```

A `BAD_RUN` line gives what the `.vy` code does in Python. The sections below give what forge's Daml does.
`b25_two_ensure_lines.vy` is `OK` because no check finds that form of b25. [b25](#b25-a-second-signatory-observer-or-ensure-line-is-lost) shows its Daml.
Two programs show a known bug in a new form. `b12_declaration_after_loop.vy` is valid code for group `g12`, and `b21_return_value_in_choice_loop.vy` is valid code for group `l05`.

## Every loop bug found so far

This table has one row for each loop bug that the fuzzer or the analyses found, also when this report has no group for it.
b25 and b26 are not loop bugs. They are here because unit 11 found them with `--compare`, together with b23 and b24.

| Bug | Code shape | What happens | damlc | Category | Groups in this report | Found by |
| --- | --- | --- | --- | --- | --- | --- |
| b11 | A loop that adds to a total and has a `return` | `CompilerPanic` at `forge/codegen/emit.py:596` | No Daml | C | `g03` | crash |
| b17 | `cids.append(create(...))` in a loop in a choice | `foldlA` with no `import DA.Action` | rejects | B | `l04` | `L1` |
| b18 | `total = total + fetch(c).amount` in a loop in a choice | `foldlA` with no `import DA.Action` | rejects | B | none | `L1` |
| b19 | `if fetch(c).amount > ...:` in a loop in a choice. Also the test of an `assert` and the list of a `for` | `fetch c` stays in the test, as an `Update` | rejects | B | `l02`, 11 inputs of `l03` | `L2` and `L4`, or only `L4` when the loop is already a `foldlA` |
| b20 | `fetch(c)` in a loop of a top-level function without `@ledger_effect` | No DF1205. `let i = fetch c` in a pure `foldl` | rejects | E | `l03` | `L2` and `L4` |
| b21 | `return` in a loop of a choice that has a `create` or an `assert` | `return` works as `continue` | builds when the `return` has no value. Rejects when it has a value | A (B with a value) | `l05`, 17 inputs of `l01` | `L3`, and `--compare` when the data shows the difference |
| b22 | `return` in an inner loop of a function | No code for the loops | builds | A | `l01`, `r01` | `L3`, `--compare` |
| b23 | `pass` above other statements in a block | The statements after the `pass` are lost | builds when `pure ()` fits the block | A | `r02`, `r03` | `--compare` only |
| b24 | A loop in a plain function with two `assert` statements, or with an `assert` in an `if` | No code for the loop | builds | A | none | `--compare`, only through a choice that calls the function |
| b25 | Two `signatory`, `observer`, or `ensure` lines in a template | forge keeps the first line | builds when the first line is valid | F | none. Input 11691 is in `d08`. | `--compare` for `signatory`. No check for `observer` and `ensure` |
| b26 | A `@choice` and a plain method with one name. Also any template method without `@choice` | forge drops the plain method | builds for the same name. Rejects a call of the method | F, B | none | `--compare` for the same name. damlc for a call |

Why five of these bugs have no group of their own in this report:

- **b18.** All 17 inputs with `L1` as their first check are b17. A b18 input needs a `fetch` in a sum, in a module with no other ledger action in a loop, because the import is for the whole module. The only seed with a sum next to a `fetch`, `loop_verify.vy`, also has an `assert` in that loop, and the `assert` makes forge add the import. Input 125 of this run is an example. The rule `inline_var` wrote `total = total + fetch(c).amount`, and forge's Daml has `import DA.Action (foldlA)`.
- **b21.** b21 is in this report, but it has no group of its own and no run group. [b21 in this report](#b21-in-this-report) tells why.
- **b24.** `--compare` does not compare a call of a plain function that fails in Python, because the Daml `error` of a failed `assert` stops Daml Script. So b24 shows only through a choice that calls the function. In the loop seeds, the only plain function that a choice calls is `total_of` in `loop_pure.vy`, and its loop adds to `total`, so it has an accumulator.
- **b25.** One input of this run has two `signatory` lines with different values, input 11691. Its first line is `signatory: list[Party] = [p]`, and the template has no `p`. forge keeps that line, and damlc rejects the Daml with `Variable not in scope: p`, so the input is in the bad Daml group `d08`. A b25 input that damlc builds needs two changes: a copy of the `signatory` line, and a valid change to one of the two copies.
- **b26.** No `OK` input of this run has two methods with one name in a template. Unit 11 found b25 in its runs with the random seeds 2 and 3, and b26 in a prototype run with random seed 1 (input 4172).

All seven programs in [`bugs/loops/`](../../bugs/loops/README.md) still give their bug.
This is the real output. The command exits with 1:

```
$ damlforge-fuzz check --damlc --compare bugs/loops
BAD_LOOP emit   bugs/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action; damlc rejects: Variable not in scope: foldlA
BAD_LOOP emit   bugs/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action; damlc rejects: Variable not in scope: foldlA
BAD_LOOP emit   bugs/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20; damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_LOOP emit   bugs/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7; damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_RUN  emit   bugs/loops/b21_return_in_create_loop.vy  contracts in Iou.GiveUntil #1: returns None, makes 1 contract: Iou(issuer=issuer, owner=alice, amount=1.0); loop check L3
BAD_RUN  emit   bugs/loops/b22_return_in_inner_loop.vy  result in first_positive #1: returns 3; loop check L3
BAD_RUN  emit   bugs/loops/b23_pass_in_loop.vy  daml_passes in Iou.Check #2: fails: positive
```

b24 to b26 are in [the first command](#the-confirmed-bugs).
b11 is in the first analysis. Its program still crashes at the same line:

```
$ damlforge-fuzz check --damlc reports/2026-10-19T18-45-34Z/analysis/b11_loop_early_return.vy
CRASH    emit   reports/2026-10-19T18-45-34Z/analysis/b11_loop_early_return.vy  CompilerPanic _translate_for: a `for` loop with both loop-carried accumulator mutation and an early `return` inside its body is not supported at forge/codegen/emit.py:596
```

`damlforge-fuzz check --damlc reports/2026-10-19T18-45-34Z/analysis` gives the same 16 results as in the first analysis, with the same forge lines.

## Every group, one line each

For a crash group and a bad Daml group, this analysis read only the first input. The Daml line is the line of damlc's first error.
For a loop group, it also counted all the inputs of the group. [The census of the loop inputs](#the-census-of-the-loop-inputs) tells how.

### Crash groups

| Group | Bug | Category | The input and the evidence |
| --- | --- | --- | --- |
| `g01` | Wrong code, [table](#other-crash-groups-on-wrong-code) | D | `signatory: 9223372036854775807[Party]`, a number as a type. `CompilerPanic lower_type` at `forge/ir/lower.py:115`, in the check step. |
| `g02` | b15 | D | A line `total = total + x` with 12 spaces, inserted below `class Iou:`. The next line, `issuer: Party`, has 4 spaces, a level that no line above it has. `IndentationError` at `forge/ast/pre_parser.py:304`. |
| `g03` | b11 | C | `if c == c:` and `return n` above `n = n + 1` in the loop of `Count`. `CompilerPanic` at `forge/codegen/emit.py:596`. |
| `g04` | b13 | C | `import os` in the choice `Many`. `CompilerPanic` at `forge/ir/lower.py:314`. |
| `g05` | Wrong code, [table](#other-crash-groups-on-wrong-code) | D | `tuple[int, str]: Party`, a type as a field name. `AttributeError` at `forge/semantics/analysis/types.py:644`. |
| `g06` | b14 | D | `from forge.Iou import ...`. `ModuleNotFoundError` at `forge/semantics/analysis/imports.py:108`. |
| `g07` | b12 | C | `owner: Party` in the function `verify`. `CompilerPanic render_expr` at `forge/codegen/emit.py:271`. |
| `g08` | Wrong code, [table](#other-crash-groups-on-wrong-code) | D | `for row for rows:`. `IndexError` at `forge/ast/pre_parser.py:389`. |
| `g09` | b09's line, on wrong code | D | `total = total & x` on two `Decimal` values. Python raises `TypeError` for `&` on a `Decimal`, so the code is wrong. `KeyError 'BitAnd'` at `forge/ir/lower.py:289`. |
| `g10` | Wrong code, [table](#other-crash-groups-on-wrong-code) | D | `[x for x in xs](1)`, a call of a list. `AssertionError` at `forge/ast/parse.py:106`. That line checks that the pre-parser used every `for` annotation. |
| `g11` | b10's line, on wrong code | D | `~x` in `GiveAll`, which has no `x`. `KeyError 'Invert'` at `forge/ir/lower.py:298`. |
| `g12` | b12 | C | `issuer: Party` below the loop of `verify`. `CompilerPanic apply_renames` at `forge/codegen/loops.py:354`. This is a new crash line for b12. [b12 after a loop](#b12-after-a-loop) tells more. |

### Bad Daml groups

| Group | Bug or check | Category | The input and the evidence |
| --- | --- | --- | --- |
| `d01` | A repeated field | E | `create(Iou(issuer=self.issuer, issuer=o, ...))`. Daml line 26 has `issuer =` two times. |
| `d02` | The return type | E | The `return total` of `verify` (`-> Decimal`) is deleted. Daml line 16 is `pure ()`. |
| `d03` | Not a type in a type | E | `cids: list[o[Iou]]`, with the loop variable `o` as a type. Daml line 20 is `let (cids : [o Iou]) = []`. |
| `d04` | b16 | E | `total = owner + x` in `grid_sum`, which has no `owner`. At Daml line 28, damlc reads `owner` as the field function of `Iou`, of type `Iou -> Party`. |
| `d05` | b16 | E | `total = amount + i.amount` in `verify`, which has no `amount`. Daml line 13. |
| `d06` | b16 | E | `if o != observer.owner:` in `Many`. Daml line 24. forge gives DF1219 for `other.owner`, but not for `observer.owner`, because `observer` is a name in the class body. |
| `d07` | Other types | E | `total = len(x) + x`, with `len` of an `int`. Daml line 28 is `length x + x`. |
| `d08` | b16 | E | `if x:` and `pass` in the loop of `Many`, which has no `x`. Daml line 24 is `if x`. |
| `d09` | b05 | B | A field `Int: Party`. Daml line 47 is `Int : Party`. The input also has `if x:` at the top of the file, and forge drops it with no error, as in b04. |
| `d10` | An unknown field in a call | E | The field `issuer: Party` is deleted, and `create(Iou(issuer=self.issuer, ...))` stays. Daml line 25. |
| `d11` | Two declarations | E | `owner: Party` two times. Daml lines 8 and 9. |
| `d12` | The return type | E | `return Decimal`, a type as a value. Daml line 16 is `pure (Decimal)`. |
| `d13` | A call with a wrong number of arguments | E | `cids.append()`. Daml line 27 is `cids.append`. |
| `d14` | b03 | B | `observer: list[Party] = []`. Daml line 25 is `observer []`. |
| `d15` | Other types | E | `controller=-9223372036854775808`. Daml line 17. |
| `d16` | b16 | E | `x += 1` in `has_party`, which has no `x`. forge writes `let x = x + 1 in`, a value that uses itself, and damlc stops with "this feature is not currently supported". |
| `d17` | A name that is valid in Python but not in Daml | E | A choice named `Party`. damlc reports `Ambiguous occurrence ‘Party’`. |
| `d18` | An assignment to a type | E | `ContractId[int] = Decimal(0)`. Daml line 9 is `let (ContractId) !! (int) = (0.0 : Decimal)`. forge writes every assignment to a subscript in this way, which is the cause of b01. |
| `d19` | A statement with no effect | E | A line `amount` alone in `Count`. At Daml line 21, `amount` is a statement of a `do` block, and a `Decimal` is not an action. |
| `d20` | Not a type in a type | E | The return type `set[int][ContractId[Iou]]`. |
| `d21` | b05 | E | `for Iou in owners:`. Daml line 22 is `(\() Iou -> do`. The code is also wrong, because the loop body still uses `o` and calls `Iou(...)`. |
| `d22` | Other types | E | `1.5.append(cid)`. Daml line 27 is `(1.5).append cid`. |
| `d23` | b27 | B | `if i.amount > (1):`. Daml line 27 is `if i.amount > 1`. The input also has `list[int] = n + 1`, which is wrong code. |
| `d24` | An unknown field in a call | E | `create=self.amount` in `Iou(...)`. Daml line 26. |
| `d25` | Other types | E | `create(o(...))`, with a party as a template. Daml line 26. The input also has `assert False` at the top of the file, and forge drops it, as in b04. |
| `d26` | Two declarations | E | A second `def verify` line. Daml lines 3 and 8 both declare `verify`. |
| `d27` | An assignment to a type | E | `tuple[int, str] = create(...)`. Daml line 28 is `(tuple) !! ((int, str)) <- create (...)`. |
| `d28` | A name that is valid in Python but not in Daml | E | A field named `self`. Daml line 9. |
| `d29` | A missing field in a call | E | `observer: list[Party] = [owner]` became `stop: list[Party] = [owner]`, a field with a default value. forge drops the default with no error, so `create(Iou(...))` at Daml line 26 lacks `stop`. |
| `d30` | A name that is valid in Python but not in Daml | E | A field named `total_of`, the name of a function of the module. Daml line 3. |
| `d31` | Other types | E | `cids: list[ContractId[float]]`, a contract ID of a number. Daml line 24 is `i <- fetch c`. |
| `d32` | A name that is valid in Python but not in Daml | E | A choice named `owner` next to the field `owner`. Daml-LF reports `name collision between choice LoopMany:Iou.Owner and field LoopMany:Iou.owner`. |
| `d33` | b16 | E | `for total in row:` leaves `x` with no value. Daml line 27 is `(\total total ->`, so the first error is the two names `total`. |

### Loop groups and run groups

| Group | Bug | Category | damlc | The first input and the evidence |
| --- | --- | --- | --- | --- |
| `l01` | b22. Also b21 in 17 of its 28 inputs | A | builds | In `has_party`, `return True` is in `for _k in range(0, 2):`. Daml line 39 is `False`, and the function has no loop. |
| `l02` | b19 | B | rejects | `if fetch(c).amount > Decimal(1):` in the loop of `Count`. Daml line 30 is `if (fetch c).amount > (1.0 : Decimal)`. |
| `l03` | b20. Also b19 in 11 of its 77 inputs | E | rejects | `@ledger_effect` above `verify` became `@list`. Daml line 9 is `let i = fetch c in`, in a pure `foldl`. |
| `l04` | b17 | B | rejects | `cids.append(create(Iou(...)))` in the loop of `Many`. Daml line 20 is `foldlA`, and the module has no `import DA.Action`. |
| `l05` | b21, with a value | B | rejects | `if x == x:` and `return total_of(xs)` above the `assert` in the loop of `Check`. The Daml has `pure (total_of xs)` in a `foldlA` step of type `Update ()`. |
| `r01` | b22 | A | builds | The same input as `l01`. `has_party` returns `True` in Python and `False` in Daml. |
| `r02` | b23 | A | builds | `pass` above the `if` in the loop of `GiveAll`. The `foldlA` step is only `pure ()`, so `GiveAll` creates no contract. |
| `r03` | b23 | A | builds | `pass` above the `assert` in the loop of `Check`. The `foldlA` step is only `pure ()`, so `Check` accepts a negative number. |

## Loop and run groups

forge writes a loop as `foldl` when its body has no ledger action, and as `foldlA` when it has one.
In a choice, an `assert` also counts as a ledger action.
A loop with an early `return` needs a recursive helper, `_damlforge_loopN`.
[How forge writes a loop](../../bugs/loops/README.md#how-forge-writes-a-loop) tells the details.
Each group below names its bug, why the bug matters for a contract, and whether damlc catches it.

### The census of the loop inputs

The run is deterministic, so a script can make its inputs again.
`python scripts/show_inputs.py contracts/loop_* --count 20000 --random-seed 1` prints 188 `BAD_LOOP` results, the same number as the report.
That script prints the seed, the change rules, and the changed lines of each input.
For this analysis, a script in the scratch folder of the session called `fuzz()` with the same arguments, wrote the 188 inputs into files, and ran `check --damlc` on them.
That script is not in the repository. These are its counts by first check and seed:

| First check | Group | Inputs | Seeds and shapes |
| --- | --- | --- | --- |
| `L1` | `l04` | 17 | All 17 are `loop_many.vy` with `cids.append(create(...))` (b17). |
| `L2` | `l03` | 77 | 66 are `loop_verify.vy` with `@ledger_effect` deleted or replaced (b20). 11 are `loop_count.vy` with `if fetch(c).amount > Decimal(1):` (b19). |
| `L3`, builds | `l01` | 28 | 11 are `loop_pure.vy` with `return True` in `for _k in range(0, 2):` (b22). 17 are `loop_give.vy` with a `return` in the loop of `GiveAll` (b21). |
| `L3`, rejects | `l05` | 29 | 9 each from `loop_give.vy`, `loop_pure.vy`, and `loop_verify.vy`, and 1 each from `loop_count.vy` and `loop_many.vy`. Their first damlc errors differ. 16 are a `Couldn't match type` error, and 11 of these are between `Numeric 10` and `()`, as in the first input. 4 are `Duplicate field name`, and 4 are `Variable not in scope`. |
| `L4` | `l02` | 37 | 13 are `loop_count.vy`, with a `fetch` in the test of an `if`. 17 are `loop_verify.vy`, mostly with a `fetch` in the test of an `assert`. The other 7 are from the other three seeds, and most of them are wrong code, such as `fetch(x)` on a `Decimal`. |

### l01: a lost return, and damlc builds the Daml

The first input puts `return True` of `has_party` into `for _k in range(0, 2):` (the rule `wrap_in_loop`) and deletes the line `if q == p:` above it:

```python
def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
            for _k in range(0, 2):
                return True
    return False
```

forge writes this Daml:

```haskell
has_party : [Party] -> Party -> Bool
has_party ps p =
  False
```

This is b22. The `return` is in an inner loop, `body_has_return` does not look into a nested `for`, and forge writes no code for either loop.
For a contract, a function that checks whether a party is in a list always gives the value after the loop.
A choice that uses such a function to allow or refuse an action gives the wrong answer, and damlc builds the Daml.
The loop check finds it (`L3`), and the comparison finds it (`r01`).

17 of the 28 inputs of `l01` are b21, with a `return` in the loop of the choice `GiveAll`. [b21 in this report](#b21-in-this-report) tells about them.

### l02: a fetch in an if test

The first input puts `i = fetch(c)` into `for _k in range(0, 2):` and changes the test to `if fetch(c).amount > Decimal(1):`.
The other `fetch` makes the loop a `foldlA`, so the check is `L4` and not `L2`.
In the Daml, `(fetch c).amount` reads a field of an `Update`, and damlc rejects it:

```
Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
```

This is b19. `hoist_nested_effects` does not lift a call out of the test of an `if` (`forge/codegen/loops.py:129` to `134`).
For a contract, a choice that reads other contracts in a loop condition cannot compile.
damlc catches it, but its message points into the generated Daml.
The group also has the two related forms that the b19 write-up names.
One is a `fetch` in the test of an `assert`, such as `assert fetch(c).issuer == p, "issuer"` in `loop_verify.vy`.
The other is a `fetch` in the list of a `for`, such as `for o in fetch(x):` in input 19381, which is also wrong code.

### l03: a top-level function that fetches without @ledger_effect

The first input replaces `@ledger_effect` above `verify` with `@list`.
forge accepts `@list` as a decorator and treats `verify` as a pure function. It writes `foldl` and `let i = fetch c in`, and damlc rejects it:

```
Tried to access nonexistent field ‘issuer’ with type ‘Party’ on value of type ‘Update
```

This is b20. forge must give DF1205, but `check_container` checks only the methods of a template and of an interface (`forge/semantics/analysis/structure.py:471` and `478`).
For a contract, the user forgot a decorator and gets a type error about `Update` in generated code instead of the DF1205 message.
66 of the 77 inputs have this shape.
The other 11 are b19 in `loop_count.vy`. There the loop has no other ledger action, so forge writes a pure `foldl` (`L2`).

### l04: create inside append

All 17 inputs have `cids.append(create(Iou(...)))`, from the rule `inline_var`.
forge writes `foldlA` with no `import DA.Action`, and damlc rejects it with `Variable not in scope: foldlA`.
This is b17. The lower step decides the import before `normalize` lifts the `create` out of the `append` call.
For a contract, a choice that creates contracts in a loop and collects their IDs cannot compile, and the error names a function that the user did not write.

### l05: a return with a value in a choice loop

The first input adds a `return` with a value above the `assert` in the loop of `Check`:

```python
    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> Decimal:
        for x in xs:
            if x == x:
                return total_of(xs)
            assert x > Decimal(0), "positive"
        return total_of(xs)
```

forge writes a `foldlA`, and the `return` becomes `pure (total_of xs)` in a step of type `Update ()`:

```haskell
          foldlA
            (\() x -> do
              let _damlforge_cont1 = do
                    assertMsg "positive" (x > (0.0 : Decimal))
                    pure ()
              if x == x
                then do
                  pure (total_of xs)
                else do
                  _damlforge_cont1)
            () xs
```

damlc rejects it with `Couldn't match type ‘Numeric 10’ with ‘()’`.
This is the cause of b21. `_translate_for` picks the fold because the loop is in an `Update` (`forge/codegen/emit.py:604`), before it looks at `has_return` (`emit.py:608`).
In a choice, the `assert` alone puts the loop in an `Update`.
With no value, the `return` becomes `pure ()`, and damlc builds the Daml, as in b21. With a value, the types do not match, so damlc catches it.

[`analysis/b21_return_value_in_choice_loop.vy`](analysis/b21_return_value_in_choice_loop.vy) is valid code with this cause.
Its choice `FirstLarge` checks each amount and returns the first one that is larger than the contract's amount.
`check --damlc` gives `L3` and `damlc rejects`, as the output of the first command shows.
For a contract, a choice that returns the first match of a checked list cannot compile.

### r01: the lost return, run

`r01` has the same first input as `l01`. The run compared its calls, and the third and fourth calls differ.
`dpm test` in a copy of `groups/r01` gives these lines:

```
daml/Test.daml:c3_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c2_result: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c2_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c1_result: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c4_result: failed
daml/Test.daml:c4_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c3_result: failed
daml/Test.daml:c1_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c5_contracts: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c5_result: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c5_runs: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c6_fails: ok, 1 active contracts, 2 transactions.
```

The failure message is `expected False == True`. The left value is from Daml, and the right value is from Python.
Calls 3 and 4 are `has_party` with `ps: [alice, bob]`. The changed code returns `True` for any list that is not empty, and forge's Daml returns `False`.
10 of the 11 b22 inputs of `l01` are in `r01`.
The 11th input, 18956, has a `break` line at the top level of the file, and the run does not compare a file with a statement there.

### r02: pass drops the creates

The first input adds `pass` as the first line of the loop body of `GiveAll`:

```python
        for o in owners:
            pass
            if o != stop:
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
```

forge writes a `foldlA` whose step is only `pure ()`, so the `if` and the `create` are lost.
`dpm test` in a copy of `groups/r02` gives:

```
daml/Test.daml:c1_contracts: failed
daml/Test.daml:c1_result: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c1_runs: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c2_contracts: failed
daml/Test.daml:c2_result: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c2_runs: ok, 1 active contracts, 2 transactions.
```

The first failure message is `expected [] == [Iou {issuer = 'alice-d4d95138', owner = 'alice-d4d95138', amount = 1.0},Iou {issuer = 'alice-d4d95138', owner = 'bob-4f1df03a', amount = 1.0}]`.
The Daml makes no contract, and Python makes two.
This is b23. The branch for `pass` in `BodyTranslator._translate` writes `pure ()` and drops the rest of the block (`forge/codegen/emit.py:448` to `449`).
For a contract, a `pass` left in as a placeholder makes the choice create nothing.
damlc builds the Daml, and no loop check finds it. Only the comparison finds it.

### r03: pass drops the assert

The first input adds `pass` as the first line of the loop body of `Check`, above the `assert`.
forge writes a `foldlA` whose step is only `pure ()`.
`dpm test` in a copy of `groups/r03` gives these lines:

```
daml/Test.daml:c3_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c2_result: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c2_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c1_result: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c4_result: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c4_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c3_result: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c1_runs: ok, 0 active contracts, 0 transactions.
daml/Test.daml:c5_contracts: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c5_result: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c5_runs: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c6_fails: failed
```

The failure message of `c6_fails` is `Expected submit to fail but it succeeded`.
This is b23 again, with the same shape as the program `bugs/loops/b23_pass_in_loop.vy`.
For a contract, the choice accepts `[1.0, -1.0]`, so a rule of the contract is gone. damlc builds the Daml.

### b21 in this report

b21 has no group of its own and no run group in this report. But its inputs are in the report.
17 of the 28 inputs of `l01` add a `return` to the loop of `GiveAll`.
16 of them have `if o == o:` and `return` from the rule `early_return`, such as input 44:

```python
        for o in owners:
            if o == o:
                return
            if o != stop:
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
```

forge writes `foldlA`, and the `return` becomes `pure ()`, as in b21. damlc builds the Daml, and the loop check finds it (`L3`).
The first input of `l01` is b22, so the group shows b22.

The comparison finds no difference in these 17 inputs. `check --compare` on them gives 17 `BAD_LOOP` lines and no `BAD_RUN` line.
The cause is the rule. `early_return` writes `if v == v:` with the loop's name, and that test is always true.
So the `return` comes before every `create` of the loop, in Python and in Daml.
Python returns at the first owner and makes no contract.
In forge's Daml, each step takes the branch `pure ()`, and the `create` is in the other branch, so the Daml also makes no contract.
In the 17th input, 17191, a `return` line is the first statement of the loop body. forge writes `pure ()` and drops the statements after it (`forge/codegen/emit.py:439` to `440`), so again neither side makes a contract.

The run with random seed 4 shows b21 as a run group.
This is the real output, with `<scratch>` in place of the scratch folder of the session:

```
$ damlforge-fuzz run contracts/loop_* --compare --count 5000 --random-seed 4 --reports <scratch>/u11-rs4-check
random seed 4, 5 seeds, 5000 inputs
random seed 4: 5000 inputs, 1058 OK, 2480 rejected, 405 crash, 1057 skipped
loops: 44 inputs with loop findings, 4 loop groups
compare: 380 inputs compared, 1 differs, 1 run group
12 crash groups, report in <scratch>/u11-rs4-check/2026-10-20T16-38-47Z
```

Its group `r01` is `contracts` in `Iou.GiveAll #1`, with the first loop check `L3`.
In its input, the `create` is out of the `if`, below the `return`:

```python
        for o in owners:
            if o != stop:
                if o == o:
                    return
            create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
```

Python returns at the first owner, `alice`, and makes no contract.
In the Daml, the `return` is `pure ()`. The loop goes on, and the step for `stop` creates an `Iou`.
`dpm test` in a copy of that group gives `daml/Test.daml:c1_contracts: failed`, with the message `expected [Iou {issuer = 'alice-d4d95138', owner = 'stop-9b3970be', amount = 1.0}] == []`.
So the Daml gives an `Iou` to `stop`, the one party that the choice must not give one to.

## Category A: wrong results with no error

b21, b22, and b23 are in [Loop and run groups](#loop-and-run-groups). b24 is new.

### b24: a loop in a plain function loses its asserts

```python
def check_amounts(xs: list[Decimal]) -> bool:
    for x in xs:
        assert x > Decimal(0), "positive"
        assert x < Decimal(1000), "below 1000"
    return True
```

The function must fail when an amount is not positive or not below 1000.
forge writes this Daml:

```haskell
check_amounts : [Decimal] -> Bool
check_amounts xs =
  True
```

The loop and both `assert` statements are gone.
The same happens when the `assert` is in an `if`, as in [`analysis/b24_assert_in_if_in_function.vy`](analysis/b24_assert_in_if_in_function.vy):

```python
def under_limit(xs: list[Decimal], limit: Decimal) -> bool:
    for x in xs:
        if x > Decimal(0):
            assert x <= limit, "over the limit"
    return True
```

forge writes `under_limit xs limit = True`.

The cause is in `_translate_for` (`forge/codegen/emit.py:590` to `612`).
A plain function is not in an `Update` (`emit.py:958`), and these loops have no accumulator and no `return`.
`_translate_for` has a form for such a loop only when its body is exactly one `assert` (`LoopAnalyzer._is_assertion_only_loop`, `forge/codegen/loops.py:389` to `394`).
For any other body, it gets to its last line, `return make_tail(indent, frozenset(), renames)` (`emit.py:612`), which writes only the code after the loop.
That line is correct for a loop with no effect. An `assert` is an effect, but the test does not see it.
In a choice, the same loop gives a correct `foldlA`, because there an `assert` counts as a ledger action.

The proof is at runtime.
`--compare` does not compare a call of a plain function that fails in Python. So each program has a choice `Check` that returns the result of the function.
The calls file gives one good list and one list that the `assert` must reject.
`check --compare` gives `daml_passes in Iou.Check #2: fails: positive` for the first program and `daml_passes in Iou.Check #2: fails: over the limit` for the second.
So the choice fails in Python, and the Daml runs it.
For a contract, a validation function with a loop checks nothing, and damlc builds the Daml.

## Category B: valid code, Daml that damlc rejects

b17 and b19 are in [Loop and run groups](#loop-and-run-groups). b03 (`d14`) and b05 (`d09`, `d21`) are in the first analysis. b26 and b27 are new.

### b27: an int literal next to a Decimal

```python
@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    ensure: bool = amount > 0
```

`amount > 0` is valid Python, and forge's check step accepts it.
forge writes `ensure amount > 0`, and damlc rejects it with `Couldn't match type ‘Int’ with ‘Numeric 10’`.
In Daml, `0` is an `Int`, and a `Decimal` needs `0.0`.
Group `d23` is the same bug, with `if i.amount > (1):`. `a + 1` and `a * 2` with a `Decimal` `a` give the same damlc error.

forge's check step accepts this code on purpose.
`_literal` gives an int literal the type `Decimal` when a `Decimal` is expected (`forge/semantics/analysis/typecheck.py:305` to `308`).
But the lower step loses that type. `_lower_expr_literal` makes `IRConstant(0)` with no type (`forge/ir/lower.py:243` to `244`), and `render_constant` writes the number as it is (`forge/codegen/emit.py:158`).
Only `Decimal(0)` becomes `(0.0 : Decimal)` (`emit.py:295`).
forge must write `(0.0 : Decimal)` for a literal that the check step typed as a `Decimal`.
If DamlForge decides that `.vy` code must write `Decimal(0)`, this bug is category E, and forge must give a DF error.

### b26: a template method that is not a choice is lost

```python
@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]

    def fee(self) -> Decimal:
        return self.amount / Decimal(100)

    @choice(controller=owner, consuming=False)
    def Fee(self) -> Decimal:
        return self.fee()
```

forge writes the choice as `pure (self.fee)`, and it writes no `fee` function.
damlc rejects it with `Tried to access nonexistent field ‘fee’ with type ‘Decimal’ on value of type ‘Iou’`.
A method that is not a choice is part of the language.
forge gives DF1205 for such a method when it calls `fetch`, as [the b20 write-up](../../bugs/loops/README.md#b20-a-top-level-function-gets-no-df1205-check) shows for `Iou.total_of`.

The cause is `lower_template` (`forge/ir/lower.py:651`).
Its loop over the template body (`lower.py:678` to `694`) keeps `__init__`, `@checked_fetch`, `@view`, and `@choice` methods. It drops every other method with no error.

Unit 11 recorded b26 as "of two `def` with the same name, forge keeps the first".
This analysis found a different rule. forge keeps the choice:

- With a `@choice` method `Fee` and then a plain method `Fee`, forge writes the choice. Python keeps the last `def`, the plain method. This is [`analysis/b26_choice_and_method_same_name.vy`](analysis/b26_choice_and_method_same_name.vy). With `amount` 100.0, `check --compare` gives `result in Iou.Fee #1: returns 2.0`, and the Daml choice returns `self.amount / (100.0 : Decimal)`, which is 1.0. damlc builds the Daml, so this form is category F.
- With a plain method `Fee` and then a `@choice` method `Fee`, forge writes the choice, and `check --damlc` gives `OK`. Python also keeps the choice, because it is last.
- With two `@choice` methods `Fee`, forge writes both, and damlc reports `Multiple declarations of ‘Fee’`.
- With two top-level `def fee`, forge writes both, and damlc reports `Duplicate type signatures for ‘fee’`. Group `d26` is this case.

The last three results are from programs in the scratch folder of the session, with `check --damlc`.

## Category C: valid code, forge crashes

| Bug | Groups | Evidence |
| --- | --- | --- |
| b11 | `g03` | `if c == c:` and `return n` in a loop that adds to `n`. `CompilerPanic` at `forge/codegen/emit.py:596`. |
| b12 | `g07`, `g12` | `owner: Party` in a function (`emit.py:271`), and `issuer: Party` after a loop (`forge/codegen/loops.py:354`). |
| b13 | `g04` | `import os` in a choice. `CompilerPanic` at `forge/ir/lower.py:314`. |

`g09` and `g11` crash at the lines of b09 and b10, but their inputs are wrong code, so they are in category D.
One fix for b09 and b10 fixes both groups.

### b12 after a loop

```python
def count(xs: list[int]) -> int:
    n = 0
    for x in xs:
        n = n + 1
    limit: int
    return n
```

This is valid code. forge crashes with `CompilerPanic apply_renames: unsupported IR expression NoneType at forge/codegen/loops.py:354`, not at `emit.py:271`.
The cause is the same as in b12. `_lower_stmt_AnnAssign` makes an assignment whose value is `None` when the line has no value (`forge/ir/lower.py:323` to `329`).
After a loop, the code after the loop goes through `apply_renames`, which meets the `None` first.
So a fix only in `render_expr` does not fix `g12`. The fix belongs in the lower step.

## Category D: wrong code, forge crashes instead of a DF error

b14 (`g06`, `from forge.Iou import ...`) and b15 (`g02`) are in the first analysis.

### Other crash groups on wrong code

The shrunk input of each group is in `groups/<id>/shrunk/`.

| Group | Wrong code | forge error |
| --- | --- | --- |
| `g01` | A number as a type, `signatory: 9223372036854775807[Party]` | `CompilerPanic` at `forge/ir/lower.py:115`, in the check step. The first analysis had the same crash for `amount: 0.0`. |
| `g05` | A type as a field name, `tuple[int, str]: Party` | `AttributeError` at `forge/semantics/analysis/types.py:644`, as in the first analysis |
| `g08` | `for row for rows:` | `IndexError` at `forge/ast/pre_parser.py:389`, as in the first analysis |
| `g09` | `total & x` on two `Decimal` values | `KeyError 'BitAnd'` at `forge/ir/lower.py:289` (b09's line). forge must give a type error. |
| `g10` | `[x for x in xs](1)`, a call of a list | `AssertionError` at `forge/ast/parse.py:106`, as in the first analysis |
| `g11` | `~x` with no `x` | `KeyError 'Invert'` at `forge/ir/lower.py:298` (b10's line). forge must give DF1219. |

## Category E: wrong code that forge accepts

### b16: unknown name

Six groups are b16: `d04`, `d05`, `d06`, `d08`, `d16`, and `d33`.
In `d04` and `d05`, the unknown name is a field of the template, `owner` or `amount`, in a top-level function.
damlc then reads the name as the field function of the template, so its message is a type error, such as `Couldn't match expected type ‘Iou -> Party’`.
`d06` is a related gap. forge gives DF1219 for an unknown name before a dot, such as `other.owner`.
But it accepts `observer.owner` in a choice, because `observer` is a name in the class body. In Python, a method cannot see that name without `self.`.

### The other bad Daml groups

In each of these groups, the fuzzer made wrong code, and forge did not see the error.

| Kind of check that forge does not do | Groups |
| --- | --- |
| A call to a template with a missing, unknown, or repeated field | `d01` (`issuer=` two times), `d10` (`issuer=` after the field was deleted), `d24` (`create=`), `d29` (no `stop=`) |
| Two declarations with one name | `d11` (field), `d26` (function) |
| The return type | `d02` (a function with `-> Decimal` and no `return`), `d12` (`return Decimal`) |
| Other types | `d07` (`len` of an `int`), `d13` (`append()` with no argument), `d15` (a number as the controller), `d22` (`1.5.append(cid)`), `d25` (a party as a template), `d31` (`ContractId[float]`) |
| A name that is not a type, in a type | `d03` (`list[o[Iou]]`), `d20` (`set[int][ContractId[Iou]]`) |
| An assignment to a type | `d18` (`ContractId[int] = ...`), `d27` (`tuple[int, str] = ...`) |
| A statement with no effect | `d19` (a line `amount`) |
| A name that is valid in Python but not in Daml | `d17` (a choice named `Party`), `d28` (a field named `self`), `d30` (a field with the name of a function), `d32` (a choice `owner` next to the field `owner`) |

`d29` also shows that forge drops the default value of a field with no error.
For `amount: Decimal = Decimal(0)` in a template, forge writes `amount : Decimal` and gives no error.

Groups `d09`, `d14`, `d21`, and `d23` are in the tables of b03, b05, and b27.
`d21` is wrong code, but its first damlc error comes from b05, the upper-case loop variable `Iou`.

## Category F: wrong code that forge silently changes

### b25: a second signatory, observer, or ensure line is lost

```python
@template
class Iou:
    issuer: Party
    owner: Party
    amount: Decimal

    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    signatory: list[Party] = [issuer, owner]

    @choice(controller=issuer, consuming=False)
    def Give(self, new_owner: Party) -> None:
        create(Iou(issuer=self.issuer, owner=new_owner, amount=self.amount))
```

A user who changes the signatories can add a second line and leave the first one.
Python keeps the last line, `[issuer, owner]`. forge keeps the first line and writes `signatory [issuer]`, with no error.
So in the Daml, the issuer can give an `Iou` to any party, and that party does not sign it.
The calls file exercises `Give` with `new_owner: carol`.
`check --compare` gives `daml_passes in Iou.Give #1: fails: create of Iou without the authority of its signatories`.
In Python, `carol` must sign the new `Iou` and does not, so the call fails. In the Daml, `alice` alone can create it, so the call runs.

`observer` and `ensure` have the same bug. [`analysis/b25_two_ensure_lines.vy`](analysis/b25_two_ensure_lines.vy) has these lines:

```python
    signatory: list[Party] = [issuer]
    observer: list[Party] = [owner]
    ensure: bool = amount > Decimal(0)
    ensure: bool = amount < Decimal(1000)
```

forge writes only `ensure amount > (0.0 : Decimal)`, so the Daml has no upper limit on `amount`.
`check --damlc --compare` gives `OK` for this program. It has no calls file, and no loop check or damlc error finds it.

The cause is three functions with the same loop: `_find_signatory`, `_find_observer`, and `_find_ensure` (`forge/ir/lower.py:471`, `483`, and `495`).
Each one returns the value of the first line with its name.
forge must give a DF error for a second line with the same name, as for any other name declared two times.

### b26, same name

The form of b26 with a choice and a plain method of one name is also category F. [b26](#b26-a-template-method-that-is-not-a-choice-is-lost) has the details.

## Priority

1. **b21, b22, b23, b24.** A loop loses a `return`, a `create`, or an `assert`. damlc builds the Daml, and the contract does the wrong thing. b23 and b24 show only with `--compare`. These are the customer's loop bugs.
2. **b25, b26 (same name), b01, b02.** The contract does something other than what the code says, and no tool gives an error. b25 can drop a signatory or an `ensure` condition.
3. **b27.** A user can easily write `amount > 0`, and forge's own check step accepts it.
4. **b17, b18, b19, b26, b03, b04, b05, b06 to b08.** Normal, correct code fails in damlc. The loop bugs b17 to b19 come first.
5. **b11, b12, b13, b09, b10.** Correct code gives a Python traceback. For b12, the fix must be in the lower step, so that it covers `g07` and `g12`.
6. **b14, b15, the category D table, b16, b20, and the category E table.** Wrong code gets a bad message. Each fix is a new check in forge's check step.

## Limits of this analysis

- All output is from DamlForge `v0.0.10-1-gc11b5fe` (`forge_version` 0.0.11) and Daml SDK 3.5.2. No other version was tried.
- For a crash group and a bad Daml group, this analysis looked only at the first input. A bad Daml group is one kind of damlc error with the names hidden, so it can hold more than one forge bug.
- For the loop groups, this analysis counted all 188 inputs by first check, seed, and damlc verdict. It read the changes of the `L1`, `L2`, and `L4` inputs and of the `L3` inputs that damlc builds. It did not read each input of `l05`, whose first damlc errors are of several kinds.
- `dpm test` writes a `.daml` folder into the folder where it runs. So the runs of `dpm test` in this analysis were in copies of `groups/r01`, `groups/r02`, and `groups/r03`, not in the report folder.
- "A wrong result" means a difference from Python on the calls of the calls file, with the stand-ins of `--compare`. For b25 and b26, that assumes that the last declaration wins, as in Python.
- The categories of b25, b26, and b27 depend on design choices of DamlForge. If the last declaration must win, b25 and the same-name form of b26 are category A. If `.vy` code must write `Decimal(0)`, b27 is category E.
- Category E assumes that forge must catch these errors, because forge already has DF codes for several of them.
- The programs in `analysis/` are small programs written by hand. The fuzzer found groups `d23` and `g12`, and unit 11 found b24 to b26. The programs show that a user can write the same code.
- The census script and the programs for the last three results of b26 are in the scratch folder of the session, not in the repository. `scripts/show_inputs.py` gives the same inputs.

## Repeat this analysis

Run these commands from the repository root:

```sh
damlforge-fuzz check --damlc --compare reports/2026-10-20T16-34-28Z/analysis
damlforge-fuzz check --damlc --compare bugs/loops
damlforge-fuzz check --damlc reports/2026-10-19T18-45-34Z/analysis
python scripts/show_inputs.py contracts/loop_* --count 20000 --random-seed 1 | grep -c "result: BAD_LOOP"
damlforge-fuzz run contracts/loop_* --compare --count 5000 --random-seed 4
```

The first three commands and the last command need DamlForge and dpm. The fourth command prints `188`.
To run the test of a run group, copy its folder first, because `dpm test` writes into the folder:

```sh
cp -r reports/2026-10-20T16-34-28Z/groups/r01 r01-copy
cd r01-copy && dpm test
```

`dpm test` needs dpm and the Daml SDK 3.5.2.
