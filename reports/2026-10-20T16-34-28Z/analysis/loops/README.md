# Loop bugs b17 to b23

This folder has seven small programs that show loop bugs in DamlForge `v0.0.10-1-gc11b5fe` (`forge_version` 0.0.11), checked with Daml SDK 3.5.2.

> [!NOTE]
> DamlForge 0.0.12 fixed all seven bugs.
> On DamlForge 0.0.13, `damlforge-fuzz check --damlc --compare reports/2026-10-20T16-34-28Z/analysis/loops` gives `OK` for each program.
> The output and the Daml on this page, and the files in `runtime/`, are from DamlForge 0.0.11, the version with the bugs.
> The programs that call `create` or `fetch` import them from `forge.builtins.daml_lang`, because DamlForge 0.0.13 needs this import.
> DamlForge 0.0.11 accepts the import and gives the same output.

The numbers continue b01 to b16 in [the analysis of the 20000-input report](../../../2026-10-19T18-45-34Z/analysis.md).
That analysis defines the categories. This folder uses three of them:

| Category | Input | What forge did |
| --- | --- | --- |
| A | Valid code | Wrote Daml that builds but gives a wrong result |
| B | Valid code | Wrote Daml that damlc rejects |
| E | Wrong code | Accepted it and wrote Daml that damlc rejects |

Each program was written by hand. It is not fuzzer output.
Each program has one template, `Iou` with the fields `issuer`, `owner`, and `amount`, and one choice.
b20 and b22 also have one top-level function.

## The seven bugs

| Bug | Category | Code | What happens |
| --- | --- | --- | --- |
| [b17](#b17-create-inside-append-loses-the-import) | B | `cids.append(create(...))` in a loop in a choice | forge writes `foldlA` with no `import DA.Action`. damlc: `Variable not in scope: foldlA` |
| [b18](#b18-fetch-inside-a-sum-loses-the-import) | B | `total = total + fetch(c).amount` in a loop in a choice | The same as b17 |
| [b19](#b19-fetch-in-an-if-test-stays-in-a-pure-foldl) | B | `if fetch(c).amount > self.amount:` in a loop in a choice | forge writes `foldl`, and `fetch` stays in the test. damlc: a type error |
| [b20](#b20-a-top-level-function-gets-no-df1205-check) | E | `fetch(c)` in a top-level function without `@ledger_effect` | No DF1205 error. damlc: a type error |
| [b21](#b21-return-in-the-loop-works-as-continue) | A | `return` in a loop that creates a contract | `return` works as `continue`. damlc builds the Daml, and the choice creates contracts after the `return` |
| [b22](#b22-return-in-an-inner-loop-removes-both-loops) | A | `return` in a loop inside another loop, in a function | forge writes no code for the loops. damlc builds the Daml, and the function always returns the value after the loops |
| [b23](#b23-pass-drops-the-rest-of-its-block) | A | `pass` before an `assert` in a loop in a choice | forge drops the statements after `pass`. damlc builds the Daml, and the choice accepts a number that the `assert` rejects |

Run all seven programs with one command from the repository root.
This is the real output:

```
$ damlforge-fuzz check --damlc reports/2026-10-20T16-34-28Z/analysis/loops
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action; damlc rejects: Variable not in scope: foldlA
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action; damlc rejects: Variable not in scope: foldlA
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20; damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7; damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b21_return_in_create_loop.vy  L3: the return in a loop of choice GiveUntil at Daml line 14 is lost (1 loop with a return, 0 early-return helpers); damlc builds
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b22_return_in_inner_loop.vy  L3: the return in a loop of function first_positive at Daml line 3 is lost (2 loops with a return, 0 early-return helpers); damlc builds
OK       emit   reports/2026-10-20T16-34-28Z/analysis/loops/b23_pass_in_loop.vy
```

The command exits with 1.
Each `BAD_LOOP` line names the checks of the [loop check](../../../../README.md#loop-check) that the program fails, and ends with the verdict of `damlc`.
b21, b22, and b23 are the only programs whose Daml `damlc` builds, because their bugs show only when the code runs.
The loop check finds b21 and b22 without a run: a `return` in a loop has no early-return helper in the Daml (`L3`).
No loop check finds b23, so `check` prints `OK` for it.

`--compare` runs the code.
b21, b22, and b23 each have a calls file next to them, such as `b23_pass_in_loop.calls.yaml`.
`check --compare` calls each function or choice of that file in Python, on the `.vy` code, and with Daml Script, on the Daml that forge writes.
It needs dpm and the Daml SDK 3.5.2:

```
$ damlforge-fuzz check --compare reports/2026-10-20T16-34-28Z/analysis/loops
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20
BAD_LOOP emit   reports/2026-10-20T16-34-28Z/analysis/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/loops/b21_return_in_create_loop.vy  contracts in Iou.GiveUntil #1: returns None, makes 1 contract: Iou(issuer=issuer, owner=alice, amount=1.0); loop check L3
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/loops/b22_return_in_inner_loop.vy  result in first_positive #1: returns 3; loop check L3
BAD_RUN  emit   reports/2026-10-20T16-34-28Z/analysis/loops/b23_pass_in_loop.vy  daml_passes in Iou.Check #2: fails: positive
```

A `BAD_RUN` line gives the kind of the difference, the call, and what the `.vy` code does in Python.
For b23, the second call of `Check` fails in Python on the `assert`, but the Daml runs it (`daml_passes`).
b17 to b20 have no calls file, and `damlc` rejects their Daml, so they cannot run.
[Compare the Daml with the .vy code](../../../../README.md#compare-the-daml-with-the-vy-code) in the main README tells more.
[The proof for b21](#the-proof-for-b21), [the proof for b22](#the-proof-for-b22), and [the proof for b23](#the-proof-for-b23) run the code with Daml Script by hand.

## How forge writes a loop

`.vy` has one loop, `for x in xs:`.
When the body has no ledger action, forge writes the loop as `foldl`.
When the body has a ledger action in an `Update`, forge writes `foldlA`, which needs `import DA.Action (foldlA)`.

forge looks at a loop in two steps:

1. The lower step decides the import. `_lower_module` ends with `prepare_ir_module` (`forge/ir/lower.py:838`), which calls `required_imports` in `forge/ir/imports.py`. For each choice and each `@ledger_effect` function, `_body_requires_foldl_a` (`imports.py:155`) looks for a loop with a ledger action.
2. The emit step writes the loop. `BodyTranslator.render_body` (`forge/codegen/emit.py:376`) first calls `LoopAnalyzer.normalize` (`forge/codegen/loops.py:362`). `normalize` moves a ledger action out of an `append` call (`rewrite_appends`) and out of a larger expression (`hoist_nested_effects`), into a statement of its own. Then `_translate_for` (`emit.py:590`) gets a plan from `LoopAnalyzer.plan` (`loops.py:366`) and picks the form.

Each step has its own copy of the test for a ledger action: `_body_has_ledger_effect` (`imports.py:118`) and `LoopAnalysis.body_has_ledger_effect` (`loops.py:184`).
Both copies find a call such as `fetch(c)` only when the call is the whole value of a statement, as in `i = fetch(c)`.
The lower step reads the loop body before `normalize`, and the emit step reads it after.

## Category A: a wrong result with no error

### b21: `return` in the loop works as `continue`

```python
    @choice(controller=issuer, consuming=False)
    def GiveUntil(self, owners: list[Party], stop: Party) -> None:
        for o in owners:
            if o == stop:
                return
            create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
```

The choice must give an `Iou` to each owner before `stop`, and then stop.
forge writes this Daml:

```haskell
        _ <-
          foldlA
            (\() o -> do
              let _damlforge_cont1 = do
                    create (Iou with issuer = self.issuer, owner = o, amount = self.amount)
                    pure ()
              if o == stop
                then do
                  pure ()
                else do
                  _damlforge_cont1)
            () owners
        pure ()
```

The `return` became `pure ()` in the `then` branch.
`pure ()` ends only the current step of `foldlA`, and `foldlA` goes on with the next owner.
So with `owners = [alice, stop, bob]`, `bob` also gets an `Iou`.
The Daml has no type error, so damlc builds it.

The cause is the order of the tests in `_translate_for` (`forge/codegen/emit.py:604` to `611`):

```python
        if plan.accumulators or plan.in_update_block:
            return self._translate_fold(...)
        if plan.has_return:
            return self._translate_early_return_loop(...)
```

The loop has a `create`, so `plan.in_update_block` is `True` (`loops.py:383` to `385`).
forge picks the fold before it looks at `has_return`.
In the fold body, a `return` with no value becomes `pure ()` (`emit.py:439` to `440`).

forge already has a correct form for this loop.
`_translate_early_return_loop` (`emit.py:688`) writes a recursive helper that stops at the first `return`, and the helper works in an `Update` (`emit.py:707` and `715`).
A runtime patch made forge test `has_return` first when a loop has no accumulator. With that patch, forge wrote the helper, and both scripts for b21 in the proof below passed.

b11 in the 20000-input analysis is a loop with an early `return` and an accumulator. For that loop, forge raises `CompilerPanic` at `emit.py:596`.

The same lost `return` happens when the `return` is in an inner loop of a choice that creates contracts:

```python
    @choice(controller=owner, consuming=False)
    def Give(self, groups: list[list[Party]], stop: Party) -> None:
        for g in groups:
            for o in g:
                if o == stop:
                    return
                create(Iou(issuer=self.issuer, owner=o, amount=self.amount))
```

forge writes `foldlA` for both loops, and in the inner `foldlA` the `return` becomes `pure ()`, as in b21.
damlc builds this Daml, and `check --damlc` gives `L3` with `2 loops with a return, 0 early-return helpers` and `damlc builds`.
This program has no number of its own, because its inner loop has the cause of b21.
But a fix for b21 alone is not enough, because the outer loop also has the cause of [b22](#b22-return-in-an-inner-loop-removes-both-loops).
With the runtime patch for b21 alone, forge wrote a helper for the inner loop, but the outer loop stayed a `foldlA` that goes on with the next group.

### The proof for b21

[`runtime/`](runtime/) is a Daml project with forge's Daml for b21, b22, and b23 and a Daml Script test, [`runtime/daml/Test.daml`](runtime/daml/Test.daml).
The test has two scripts for b21, two scripts for [b22](#the-proof-for-b22), and two scripts for [b23](#the-proof-for-b23).
The scripts for b21 are:

- `control_every_owner_gets_an_iou` exercises `GiveUntil` with `owners = [alice, bob]` and a `stop` that is not in the list. Every owner must get an `Iou`.
- `return_stops_the_loop` exercises `GiveUntil` with `owners = [alice, stop, bob]`. Only `alice` must get an `Iou`.

Run the test:

```sh
cd reports/2026-10-20T16-34-28Z/analysis/loops/runtime
dpm test
```

`dpm test` exits with 1. Its test summary has these six lines:

```
daml/Test.daml:return_in_inner_loop_gives_the_first_positive: failed
daml/Test.daml:control_no_positive_gives_0: ok, 0 active contracts, 0 transactions.
daml/Test.daml:control_positive_numbers_pass: ok, 1 active contracts, 2 transactions.
daml/Test.daml:pass_keeps_the_assert: failed
daml/Test.daml:control_every_owner_gets_an_iou: ok, 3 active contracts, 2 transactions.
daml/Test.daml:return_stops_the_loop: failed
```

Two of these lines are for b21, two are for b22, and two are for b23.
The failure message of `return_stops_the_loop` is `expected ['alice-9cefe94d','bob-05e8b107'] == ['alice-9cefe94d']`.
The left list has the owners that got an `Iou`. The right list has the owners that the `.vy` code gives an `Iou` to.
The 3 active contracts of the control are the issuer's own `Iou` and the `Iou`s of `alice` and `bob`.
The control passes, so the party allocation, the query, and the filter that leaves out the issuer's own `Iou` are correct.

### b22: `return` in an inner loop removes both loops

```python
def first_positive(rows: list[list[int]]) -> int:
    for row in rows:
        for x in row:
            if x > 0:
                return x
    return 0
```

The function must return the first positive number in `rows`, or 0 when `rows` has no positive number.
The choice `FirstPositive` returns `first_positive(rows)`.
forge writes this Daml for the function:

```haskell
first_positive : [[Int]] -> Int
first_positive rows =
  0
```

The Daml has no loop. The function always returns 0.
So `first_positive [[0, -1], [3, 4]]` gives 0, not 3.
The Daml has no type error, so damlc builds it.

The cause is that `LoopAnalysis.body_has_return` (`forge/codegen/loops.py:290` to `298`) looks for a `return` in the branches of an `if`, but not in the body of a nested `for`.
The body of the outer loop is only the inner `for`, so `plan` sets `has_return` to `False` for the outer loop (`loops.py:382`).
The other two tests of a loop body do look into a nested `for`: `collect_accumulators` (`loops.py:107`) and `body_has_ledger_effect` (`loops.py:203`).

`_translate_for` (`emit.py:590`) picks the form of a loop in this order (`emit.py:600` to `612`):

```python
        if plan.assertion is not None:
            return self._translate_assertion_loop(...)
        if plan.accumulators or plan.in_update_block:
            return self._translate_fold(...)
        if plan.has_return:
            return self._translate_early_return_loop(...)
        return make_tail(indent, frozenset(), renames)
```

The outer loop has no `assert` and no accumulator.
`first_positive` is a pure function, so `in_update_block` is `False` (`emit.py:958`). `has_return` is also `False`.
So `_translate_for` gets to the last line (`emit.py:612`), which writes only the code after the loop.
The inner loop is in the body of the outer loop, so forge does not write it either.
The last line is correct for a loop with no effect. The outer loop has an effect, its `return`, but `has_return` does not see it.

The loop check counts both loops as loops with a `return`, so its line for b22 has `2 loops with a return, 0 early-return helpers`.
DamlForge `v0.0.7` writes the same Daml for b22. Its `body_has_return` (`forge/codegen/loops.py:233`) has the same gap.

A runtime patch made `body_has_return` also look into a nested `for`.
With that patch, forge wrote a helper for each loop, but damlc rejected the Daml: `Couldn't match expected type ‘Optional a’ with actual type ‘Int’`.
`_wrap_returns_as_some` (`emit.py:571` to `588`) has the same gap.
It changes `return x` to `return Some x` in the branches of an `if`, but not in a nested `for`.
So the helper of the outer loop returns the value of the inner helper with no `Some`, in the line `Some _damlforge_early2 -> _damlforge_early2`.
A second patch made `_wrap_returns_as_some` also look into a nested `for`.
With both patches, damlc built forge's Daml, and both scripts of the proof below passed.

### The proof for b22

[`runtime/daml/Test.daml`](runtime/daml/Test.daml) has two scripts for b22. They call `first_positive` directly:

- `control_no_positive_gives_0` calls `first_positive [[0, -1], [-2]]`. No number is positive, so the result must be 0.
- `return_in_inner_loop_gives_the_first_positive` calls `first_positive [[0, -1], [3, 4]]`. The result must be 3.

The `dpm test` run in [the proof for b21](#the-proof-for-b21) also runs these scripts.
Its test summary has these two lines for b22:

```
daml/Test.daml:return_in_inner_loop_gives_the_first_positive: failed
daml/Test.daml:control_no_positive_gives_0: ok, 0 active contracts, 0 transactions.
```

The failure message is `expected 0 == 3`.
The left value is what forge's `first_positive` returns. The right value is what the `.vy` code returns.
The control passes, because 0 is also the correct result when no number is positive.

### b23: `pass` drops the rest of its block

```python
    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> None:
        for x in xs:
            pass
            assert x > Decimal(0), "positive"
```

The choice must fail when a number in `xs` is not positive.
forge writes this Daml for the choice:

```haskell
        _ <-
          foldlA
            (\() x -> do
              pure ())
            () xs
        pure ()
```

The `assert` is gone, so `Check` accepts `[1.0, -1.0]`.
The Daml has no type error, so damlc builds it.
No loop check finds the bug: the loop is a `foldlA` with its import, it has no `return`, and it uses no ledger action as a value.
The fuzzer found b23 with `--compare` (input 2936 of `damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1 --compare`, a `pass` above the `if` in `GiveAll`).
There the `create` after the `pass` is lost, so `GiveAll` creates no contract.

The cause is the branch for `pass` in `BodyTranslator._translate` (`forge/codegen/emit.py:448` to `449`):

```python
        if isinstance(first, IRPass):
            return [f"{pad}pure ()"]
```

`_translate` writes a block one statement at a time: it writes `first`, then the statements after it, `rest`.
The branch for `pass` writes `pure ()` and stops, as the branch for a `return` with no value above it does (`emit.py:438` to `440`).
So forge drops every statement after a `pass` in the same block.
In a choice, an `assert` in a loop counts as a ledger action (`LoopAnalysis.body_has_ledger_effect`, `forge/codegen/loops.py:186`), so `_translate_for` writes `foldlA` (`emit.py:604`), and the body of the `foldlA` goes through `_translate`.

A `pass` that is not first also drops statements: all the statements after it in its block.
These are the results of small programs on DamlForge 0.0.11:

- A `pass` in the `if` branch of a loop in a choice, above a `create`: the `create` is lost, and damlc builds the Daml. The fuzzer found this one too (input 75 of `damlforge-fuzz run contracts/loop_* --count 136 --random-seed 251 --compare`).
- A `pass` between two assignments in a loop of a plain function: the second assignment is lost, and the fold step becomes `pure ()`. damlc rejects the Daml.
- A `pass` as the first statement of a choice that returns a `Decimal`: the whole body is lost, and the result is `pure ()`. damlc rejects the Daml.
- A `pass` as the first statement of a plain function that returns a `Decimal`: the function body becomes `pure ()`. damlc rejects the Daml.

So damlc builds the Daml only when `pure ()` has the type that the block needs, as in the step of a `foldlA` with no accumulator, or in a choice that returns `None`.

A runtime patch made the branch for `pass` translate the statements after it: `return self._translate(rest, indent, in_update_block, make_tail, known, renames)`.
With that patch, forge wrote `assertMsg "positive" (x > (0.0 : Decimal))` in the `foldlA`, and both scripts for b23 in the proof below passed.
The patch also gave the correct Daml for the four programs in the list above.
The patch tests the cause. It is not a fix.
DamlForge `v0.0.7` writes the same Daml for b23. Its branch for `pass` is at `forge/codegen/emit.py:392`.

In a plain function, the same loop loses its `assert` for a second reason.
`_translate_for` writes no code for a loop that has no accumulator, no ledger action, and no `return` (`emit.py:612`), unless its body is exactly one `assert` (`LoopAnalyzer._is_assertion_only_loop`, `loops.py:389`).
With `pass` first, the body has two statements, so forge writes no code for the loop.
A loop body of two `assert` statements, with no `pass`, loses both of them in the same way. For a plain function `two_asserts` with such a loop and `return True`, forge writes `two_asserts xs = True`.
The patch above does not change this. In a choice, two `assert` statements in a loop give a correct `foldlA`.
`--compare` cannot show this case: in a plain function, a failed `assert` is a Daml `error`, which Daml Script cannot catch, so `--compare` does not compare a call of a plain function that fails in Python.

### The proof for b23

[`runtime/daml/Test.daml`](runtime/daml/Test.daml) has two scripts for b23. Each one creates an `Iou` and exercises `Check`:

- `control_positive_numbers_pass` exercises `Check` with `xs = [1.0, 2.0]`. Both numbers are positive, so the choice must run.
- `pass_keeps_the_assert` exercises `Check` with `xs = [1.0, -1.0]` in `submitMustFail`. The `assert` must reject `-1.0`, so the choice must fail.

The `dpm test` run in [the proof for b21](#the-proof-for-b21) also runs these scripts.
Its test summary has these two lines for b23:

```
daml/Test.daml:control_positive_numbers_pass: ok, 1 active contracts, 2 transactions.
daml/Test.daml:pass_keeps_the_assert: failed
```

The failure message is `Expected submit to fail but it succeeded`.
The control passes, because the Daml of `Check` accepts every list.

### Where the Daml comes from

[`runtime/daml/B21ReturnInCreateLoop.daml`](runtime/daml/B21ReturnInCreateLoop.daml), [`runtime/daml/B22ReturnInInnerLoop.daml`](runtime/daml/B22ReturnInInnerLoop.daml), and [`runtime/daml/B23PassInLoop.daml`](runtime/daml/B23PassInLoop.daml) are copies of what forge wrote, with no change.
To make them again, run these commands from the repository root:

```sh
forge daml --no-i reports/2026-10-20T16-34-28Z/analysis/loops/b21_return_in_create_loop.vy -o /tmp/b21
cp /tmp/b21/B21ReturnInCreateLoop.daml reports/2026-10-20T16-34-28Z/analysis/loops/runtime/daml/
forge daml --no-i reports/2026-10-20T16-34-28Z/analysis/loops/b22_return_in_inner_loop.vy -o /tmp/b22
cp /tmp/b22/B22ReturnInInnerLoop.daml reports/2026-10-20T16-34-28Z/analysis/loops/runtime/daml/
forge daml --no-i reports/2026-10-20T16-34-28Z/analysis/loops/b23_pass_in_loop.vy -o /tmp/b23
cp /tmp/b23/B23PassInLoop.daml reports/2026-10-20T16-34-28Z/analysis/loops/runtime/daml/
```

forge also writes a source map for each file, such as `B21ReturnInCreateLoop.map.json`. The test does not need them.
To check that the copies are still what forge writes, run the `forge daml` lines again and compare:

```sh
diff /tmp/b21/B21ReturnInCreateLoop.daml reports/2026-10-20T16-34-28Z/analysis/loops/runtime/daml/B21ReturnInCreateLoop.daml
diff /tmp/b22/B22ReturnInInnerLoop.daml reports/2026-10-20T16-34-28Z/analysis/loops/runtime/daml/B22ReturnInInnerLoop.daml
diff /tmp/b23/B23PassInLoop.daml reports/2026-10-20T16-34-28Z/analysis/loops/runtime/daml/B23PassInLoop.daml
```

forge names the module after the file, so `b21_return_in_create_loop.vy` becomes the module `B21ReturnInCreateLoop`.
`Test.daml` imports the three modules. If you rename a `.vy` file, change its import in `Test.daml`.
All three modules have a template `Iou`, so `Test.daml` imports only `first_positive` from `B22ReturnInInnerLoop`, and it imports `B23PassInLoop` as `B23`.

## Category B: valid code, Daml that damlc rejects

### b17: `create` inside `append` loses the import

```python
    @choice(controller=issuer, consuming=False)
    def GiveEach(self, owners: list[Party]) -> list[ContractId[Iou]]:
        cids: list[ContractId[Iou]] = []
        for o in owners:
            cids.append(create(Iou(issuer=self.issuer, owner=o, amount=self.amount)))
        return cids
```

forge writes this Daml, and the module has no `import DA.Action`:

```haskell
        _damlforge_cids3 <-
          foldlA
            (\cids o -> do
              _damlforge_cids_item1 <- create (Iou with issuer = self.issuer, owner = o, amount = self.amount)
              let _damlforge_cids2 = cids <> [_damlforge_cids_item1]
              pure _damlforge_cids2)
            cids owners
```

damlc's full message is:

```
Variable not in scope:
  foldlA
    : ([ContractId Iou] -> Party -> Update [ContractId Iou])
      -> [ContractId Iou] -> [Party] -> Update [ContractId Iou]
```

The cause is that the lower step decides the import before `normalize`.
There, the loop statement is `cids.append(create(...))`.
Its value is a call to `cids.append`, and `_is_effect_call` (`imports.py:139`) counts only a call to a plain name, such as `create`.
So `_body_requires_foldl_a` returns `False`, and forge adds no import.
In the emit step, `rewrite_appends` (`loops.py:64` to `72`) moves the `create` into a statement of its own, `_damlforge_cids_item1 <- create (...)`.
Now `body_has_ledger_effect` finds it, and `_translate_for` writes `foldlA` (`emit.py:604` and `669`).

`required_imports` also adds the import for any IR name `foldlA` (`imports.py:194`).
The IR name check does not help here, because the emit step writes `foldlA` as text, not as an IR name.

A user can avoid the bug with a name for the new contract ID: `cid = create(...)`, then `cids.append(cid)`.
`check --damlc` gives OK for that program.

### b18: `fetch` inside a sum loses the import

```python
    @choice(controller=owner, consuming=False)
    def Total(self, cids: list[ContractId[Iou]]) -> Decimal:
        total = Decimal(0)
        for c in cids:
            total = total + fetch(c).amount
        return total
```

forge again writes `foldlA`, and the module has no import:

```haskell
          foldlA
            (\total c -> do
              _damlforge_effect1 <- fetch c
              let _damlforge_total2 = total + _damlforge_effect1.amount
              pure _damlforge_total2)
            total cids
```

damlc's full message is:

```
Variable not in scope:
  foldlA
    : (b0 -> ContractId r0 -> Update b0)
      -> Decimal -> [ContractId Iou] -> Update Decimal
```

The cause is the same as in b17.
Before `normalize`, the loop statement is `total = total + fetch(c).amount`.
Its value is an addition, not a call, so the lower step finds no ledger action (`imports.py:124`).
In the emit step, `hoist_nested_effects` (`loops.py:139` to `143`) moves `fetch(c)` into `_damlforge_effect1 <- fetch c`, and forge writes `foldlA`.

Outside a loop, the same kind of line builds. `total = fetch(a).amount + fetch(b).amount` in a choice gives OK.
The import is for the whole module. So if another loop in the module adds the import, b18 builds.
A second choice with `i = fetch(c)` in a loop is enough to hide the bug.

A user can avoid the bug with `i = fetch(c)`, then `total = total + i.amount`.
`check --damlc` gives OK for that program.

### b19: `fetch` in an `if` test stays in a pure `foldl`

```python
    @choice(controller=owner, consuming=False)
    def CountLarger(self, cids: list[ContractId[Iou]]) -> int:
        n = 0
        for c in cids:
            if fetch(c).amount > self.amount:
                n = n + 1
        return n
```

forge writes a pure `foldl`, and `fetch c` stays in the test:

```haskell
        let _damlforge_n2 =
              foldl
                (\n c ->
                  if (fetch c).amount > self.amount
                    then
                      let _damlforge_n1 = n + 1 in
                      _damlforge_n1
                    else
                      n)
                n cids
```

damlc's full message starts with:

```
• Possible Daml-specific reason for the following type error:
  Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
                                                                                     Iou’
• No instance for (GetField "amount" (Update Iou) Decimal)
    arising from a use of ‘getField’
```

The cause is that `hoist_nested_effects` does not look at the test of an `if` statement.
It makes the `if` again with new branches, but it keeps the test as it is (`loops.py:129` to `134`).
`body_has_ledger_effect` also reads only the branches of an `if` (`loops.py:198` to `202`).
It finds no ledger action, so `plan` sets `in_update_block` to `False` (`loops.py:383` to `385`), and `_translate_fold` writes `foldl` (`emit.py:677`).

The loop is not needed for this bug. The same `if` in a choice with no loop gives the same damlc error.
The same gap is in two more places:

- The test of an `assert`, as in `assert fetch(c).amount > self.amount`.
- The list of a `for`, as in `for p in fetch(c).others:`.

Both give the same kind of damlc error.
`hoist_nested_effects` lifts a call only from the value of a `return`, an assignment, or an expression statement (`loops.py:139`).
`_lift_effects`, which `hoist_nested_effects` calls, does lift a call from the test of a conditional expression (`loops.py:149` to `150`).
So `n = n + 1 if fetch(c).amount > self.amount else n` gets `foldlA`, and then fails like b18 with `Variable not in scope: foldlA`.

A fix in `hoist_nested_effects` alone is not enough.
A runtime patch made `hoist_nested_effects` lift the call out of the `if` test. Then forge wrote `foldlA` with `_damlforge_effect1 <- fetch c`, but damlc reported `Variable not in scope: foldlA`, as in b17.
The lower step still reads the body before `normalize`, and its `_body_has_ledger_effect` also reads only the branches of an `if` (`imports.py:129` to `133`).

## Category E: wrong code that forge accepts

### b20: a top-level function gets no DF1205 check

```python
def total_of(cids: list[ContractId[Iou]]) -> Decimal:
    total = Decimal(0)
    for c in cids:
        i = fetch(c)
        total = total + i.amount
    return total
```

The choice `Total` calls `total_of(cids)`.
DamlForge's language reference says that a plain `def` that calls `fetch`, `exercise`, `create`, `archive`, or `lookup` must have `@ledger_effect`.
The rule is in the section "Hidden ledger effects" of `.claude/skills/damlforge-vy-lang/reference.md` in the DamlForge repository.
Its error code is DF1205.

forge gives no error. It writes a pure function with `let i = fetch c in`:

```haskell
total_of : [ContractId Iou] -> Decimal
total_of cids =
  let total = (0.0 : Decimal) in
  let _damlforge_total2 =
        foldl
          (\total c ->
            let i = fetch c in
            let _damlforge_total1 = total + i.amount in
            _damlforge_total1)
          total cids
  in
  _damlforge_total2
```

damlc's full message starts with:

```
• Possible Daml-specific reason for the following type error:
  Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
                                                                                     Iou’
• No instance for (GetField "amount" (Update Iou) Decimal)
    arising from a use of ‘getField’
```

The cause is where forge runs the check.
`check_hidden_ledger_effects` (`forge/semantics/analysis/structure.py:220`) gives DF1205.
`check_container` calls it only for a template (`structure.py:471`) and an interface (`structure.py:478`).
`check_container` has no branch for a top-level function. So forge checks the methods of a template, but never a top-level `def`.

The loop is not needed for this bug.
A top-level function without `@ledger_effect` that does `return fetch(c).amount` gives the same damlc error.
The same loop in a template method that is not a choice gets the correct error:

```
DF1205: `Iou.total_of` calls `fetch` but is not decorated `@ledger_effect` and is not a `@choice`
```

With `@ledger_effect` above `total_of`, forge writes `foldlA` and the import, and `check --damlc` gives OK.

## Limits of this write-up

- All output is from DamlForge `v0.0.10-1-gc11b5fe` (`forge_version` 0.0.11) and Daml SDK 3.5.2. No other version was tried, except that DamlForge `v0.0.7` writes the same Daml for b22 and b23.
- b19 and b20 also happen with no loop. They are in this folder because the loop work found them.
- The runtime patches for b19, b21, b22, and b23 ran outside the repository. They test a cause. They are not fixes.
- Category E for b20 assumes that forge must give DF1205 for a top-level function, as its language reference says.

## Repeat these checks

Run these commands from the repository root:

```sh
damlforge-fuzz check --damlc reports/2026-10-20T16-34-28Z/analysis/loops
damlforge-fuzz check --compare reports/2026-10-20T16-34-28Z/analysis/loops
cd reports/2026-10-20T16-34-28Z/analysis/loops/runtime && dpm test
```

The first two commands need DamlForge and dpm. The last command needs dpm and the Daml SDK 3.5.2.
