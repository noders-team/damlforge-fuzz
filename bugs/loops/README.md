# Loop bugs b17 to b21

This folder has five small programs that show loop bugs in DamlForge `v0.0.10-1-gc11b5fe` (`forge_version` 0.0.11), checked with Daml SDK 3.5.2.

The numbers continue b01 to b16 in [the analysis of the 20000-input report](../../reports/2026-10-19T18-45-34Z/analysis.md).
That analysis defines the categories. This folder uses three of them:

| Category | Input | What forge did |
| --- | --- | --- |
| A | Valid code | Wrote Daml that builds but gives a wrong result |
| B | Valid code | Wrote Daml that damlc rejects |
| E | Wrong code | Accepted it and wrote Daml that damlc rejects |

Each program was written by hand. It is not fuzzer output.
Each program has one template, `Iou` with the fields `issuer`, `owner`, and `amount`, and one choice.
b20 also has one top-level function.

## The five bugs

| Bug | Category | Code | What happens |
| --- | --- | --- | --- |
| [b17](#b17-create-inside-append-loses-the-import) | B | `cids.append(create(...))` in a loop in a choice | forge writes `foldlA` with no `import DA.Action`. damlc: `Variable not in scope: foldlA` |
| [b18](#b18-fetch-inside-a-sum-loses-the-import) | B | `total = total + fetch(c).amount` in a loop in a choice | The same as b17 |
| [b19](#b19-fetch-in-an-if-test-stays-in-a-pure-foldl) | B | `if fetch(c).amount > self.amount:` in a loop in a choice | forge writes `foldl`, and `fetch` stays in the test. damlc: a type error |
| [b20](#b20-a-top-level-function-gets-no-df1205-check) | E | `fetch(c)` in a top-level function without `@ledger_effect` | No DF1205 error. damlc: a type error |
| [b21](#b21-return-in-the-loop-works-as-continue) | A | `return` in a loop that creates a contract | `return` works as `continue`. damlc builds the Daml, and the choice creates contracts after the `return` |

Run all five programs with one command from the repository root.
This is the real output:

```
$ damlforge-fuzz check --damlc bugs/loops
BAD_DAML emit   bugs/loops/b17_create_append.vy  Variable not in scope: foldlA
BAD_DAML emit   bugs/loops/b18_fetch_in_sum.vy  Variable not in scope: foldlA
BAD_DAML emit   bugs/loops/b19_fetch_in_if_test.vy  Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_DAML emit   bugs/loops/b20_fetch_in_plain_function.vy  Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
OK       emit   bugs/loops/b21_return_in_create_loop.vy
```

The command exits with 1.
b21 is OK here, because its bug shows only when the contract runs. [The proof for b21](#the-proof-for-b21) runs it.

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
A runtime patch made forge test `has_return` first when a loop has no accumulator. With that patch, forge wrote the helper, and both scripts of the proof below passed.

b11 in the 20000-input analysis is a loop with an early `return` and an accumulator. For that loop, forge raises `CompilerPanic` at `emit.py:596`.

### The proof for b21

[`runtime/`](runtime/) is a Daml project with forge's Daml for b21 and a Daml Script test, [`runtime/daml/Test.daml`](runtime/daml/Test.daml).
The test has two scripts:

- `control_every_owner_gets_an_iou` exercises `GiveUntil` with `owners = [alice, bob]` and a `stop` that is not in the list. Every owner must get an `Iou`.
- `return_stops_the_loop` exercises `GiveUntil` with `owners = [alice, stop, bob]`. Only `alice` must get an `Iou`.

Run the test:

```sh
cd bugs/loops/runtime
dpm test
```

`dpm test` exits with 1. Its test summary has these two lines:

```
daml/Test.daml:control_every_owner_gets_an_iou: ok, 3 active contracts, 2 transactions.
daml/Test.daml:return_stops_the_loop: failed
```

The failure message is `expected ['alice-c812a76d','bob-9cefe94d'] == ['alice-c812a76d']`.
The left list has the owners that got an `Iou`. The right list has the owners that the `.vy` code gives an `Iou` to.
The 3 active contracts of the control are the issuer's own `Iou` and the `Iou`s of `alice` and `bob`.
The control passes, so the party allocation, the query, and the filter that leaves out the issuer's own `Iou` are correct.

### Where the Daml comes from

[`runtime/daml/B21ReturnInCreateLoop.daml`](runtime/daml/B21ReturnInCreateLoop.daml) is a copy of what forge wrote, with no change.
To make it again, run these commands from the repository root:

```sh
forge daml --no-i bugs/loops/b21_return_in_create_loop.vy -o /tmp/b21
cp /tmp/b21/B21ReturnInCreateLoop.daml bugs/loops/runtime/daml/
```

forge also writes the source map `B21ReturnInCreateLoop.map.json`. The test does not need it.
To check that the copy is still what forge writes, run the `forge daml` line again and compare:

```sh
diff /tmp/b21/B21ReturnInCreateLoop.daml bugs/loops/runtime/daml/B21ReturnInCreateLoop.daml
```

forge names the module after the file, so `b21_return_in_create_loop.vy` becomes the module `B21ReturnInCreateLoop`.
`Test.daml` imports that module. If you rename the `.vy` file, change the import in `Test.daml`.

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

- All output is from DamlForge `v0.0.10-1-gc11b5fe` (`forge_version` 0.0.11) and Daml SDK 3.5.2. No other version was tried.
- b19 and b20 also happen with no loop. They are in this folder because the loop work found them.
- The runtime patches for b19 and b21 ran in a scratch session. They test a cause. They are not fixes.
- Category E for b20 assumes that forge must give DF1205 for a top-level function, as its language reference says.

## Repeat these checks

Run these commands from the repository root:

```sh
damlforge-fuzz check --damlc bugs/loops
cd bugs/loops/runtime && dpm test
```

The first command needs DamlForge and dpm. The second command needs dpm and the Daml SDK 3.5.2.
