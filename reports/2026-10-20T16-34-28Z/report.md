# damlforge-fuzz run 2026-10-20T16:34:28Z

- Random seed: 1
- Limit: 20000 inputs
- Seeds: `contracts/loop_count/loop_count.vy`, `contracts/loop_give/loop_give.vy`, `contracts/loop_many/loop_many.vy`, `contracts/loop_pure/loop_pure.vy`, `contracts/loop_verify/loop_verify.vy`
- DamlForge: 0.0.11

## Totals

20000 inputs: 4092 OK, 10205 rejected, 1643 crash, 4060 skipped.

## 12 crash groups

| Group | Count | Exception | Stage | Seed | First seen | Input | Shrunk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| g01 | 481 | CompilerPanic at forge/ir/lower.py:115 | check | contracts/loop_give/loop_give.vy | input 19, 0.03 s | [loop_give.vy](groups/g01/loop_give.vy) | [3 of 18 lines](groups/g01/shrunk/loop_give.vy) |
| g02 | 601 | IndentationError at forge/ast/pre_parser.py:304 | parse | contracts/loop_verify/loop_verify.vy | input 43, 0.05 s | [loop_verify.vy](groups/g02/loop_verify.vy) | [2 of 26 lines](groups/g02/shrunk/loop_verify.vy) |
| g03 | 169 | CompilerPanic at forge/codegen/emit.py:596 | emit | contracts/loop_count/loop_count.vy | input 63, 0.07 s | [loop_count.vy](groups/g03/loop_count.vy) | [12 of 21 lines](groups/g03/shrunk/loop_count.vy) |
| g04 | 158 | CompilerPanic at forge/ir/lower.py:314 | lower | contracts/loop_many/loop_many.vy | input 210, 0.15 s | [loop_many.vy](groups/g04/loop_many.vy) | [8 of 21 lines](groups/g04/shrunk/loop_many.vy) |
| g05 | 99 | AttributeError at forge/semantics/analysis/types.py:644 | check | contracts/loop_pure/loop_pure.vy | input 226, 0.16 s | [loop_pure.vy](groups/g05/loop_pure.vy) | [3 of 40 lines](groups/g05/shrunk/loop_pure.vy) |
| g06 | 9 | ModuleNotFoundError at forge/semantics/analysis/imports.py:108 | check | contracts/loop_give/loop_give.vy | input 300, 0.2 s | [loop_give.vy](groups/g06/loop_give.vy) | [4 of 18 lines](groups/g06/shrunk/loop_give.vy) |
| g07 | 19 | CompilerPanic at forge/codegen/emit.py:271 | emit | contracts/loop_verify/loop_verify.vy | input 825, 0.48 s | [loop_verify.vy](groups/g07/loop_verify.vy) | [6 of 27 lines](groups/g07/shrunk/loop_verify.vy) |
| g08 | 14 | IndexError at forge/ast/pre_parser.py:389 | parse | contracts/loop_pure/loop_pure.vy | input 1091, 0.64 s | [loop_pure.vy](groups/g08/loop_pure.vy) | [2 of 40 lines](groups/g08/shrunk/loop_pure.vy) |
| g09 | 8 | KeyError at forge/ir/lower.py:289 | lower | contracts/loop_pure/loop_pure.vy | input 1139, 0.67 s | [loop_pure.vy](groups/g09/loop_pure.vy) | [2 of 40 lines](groups/g09/shrunk/loop_pure.vy) |
| g10 | 72 | AssertionError at forge/ast/parse.py:106 | parse | contracts/loop_count/loop_count.vy | input 1165, 0.69 s | [loop_count.vy](groups/g10/loop_count.vy) | [4 of 21 lines](groups/g10/shrunk/loop_count.vy) |
| g11 | 10 | KeyError at forge/ir/lower.py:298 | lower | contracts/loop_give/loop_give.vy | input 6342, 3.42 s | [loop_give.vy](groups/g11/loop_give.vy) | [8 of 20 lines](groups/g11/shrunk/loop_give.vy) |
| g12 | 3 | CompilerPanic at forge/codegen/loops.py:354 | emit | contracts/loop_verify/loop_verify.vy | input 9263, 5.02 s | [loop_verify.vy](groups/g12/loop_verify.vy) | [10 of 26 lines](groups/g12/shrunk/loop_verify.vy) |

## Stages

- `parse`: forge reads the .vy text and makes a syntax tree (forge.ast.parse_to_ast). A crash here means forge failed while it read the code.
- `check`: forge checks names, types, imports, and the rules for templates and choices (forge.semantics.analyze_module). Wrong code must stop here with a DF error.
- `lower`: forge changes the checked program into its internal form, IR (forge.ir.lower_module). A crash here usually means that check let through code that forge cannot translate.
- `emit`: forge writes the Daml code from the IR (forge.codegen.generate_daml).

The stage is the step that was running, not the folder of the forge file, so a crash can have stage `check` and a line in `forge/ir/lower.py`.

## Shrunk inputs

### g01: CompilerPanic at forge/ir/lower.py:115

```python
@template
class Iou:
    signatory: 9223372036854775807[Party] = [issuer]
```

### g02: IndentationError at forge/ast/pre_parser.py:304

```python
            total = total + x
    issuer: Party
```

### g03: CompilerPanic at forge/codegen/emit.py:596

```python
from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Count(self, cids: list[ContractId[Iou]]) -> int:
        n = 0
        for c in cids:
                if c == c:
                    return n
                n = n + 1
```

### g04: CompilerPanic at forge/ir/lower.py:314

```python
from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Many(self, owners: list[Party]) -> list[ContractId[Iou]]:
        import os
```

### g05: AttributeError at forge/semantics/analysis/types.py:644

```python
@template
class Iou:
    tuple[int, str]: Party
```

### g06: ModuleNotFoundError at forge/semantics/analysis/imports.py:108

```python
from forge.Iou import Decimal, Party, choice, template
@template
class Iou:
    issuer: Party
```

### g07: CompilerPanic at forge/codegen/emit.py:271

```python
from forge.models import ContractId, Decimal, Party, choice, ledger_effect, template
def verify(cids: list[ContractId[Iou]], p: Party) -> Decimal:
    owner: Party
@template
class Iou:
    signatory: list[Party] = [issuer]
```

### g08: IndexError at forge/ast/pre_parser.py:389

```python
    for row for rows:
        for x in row:
```

### g09: KeyError at forge/ir/lower.py:289

```python
def total_of(xs: list[Decimal]) -> Decimal:
            total = total & x
```

### g10: AssertionError at forge/ast/parse.py:106

```python
@template
class Iou:
            if i.amount > [x for x in xs](1):
                n = n + 1
```

### g11: KeyError at forge/ir/lower.py:298

```python
from forge.models import Decimal, Party, choice, template
@template
class Iou:
    issuer: Party
    signatory: list[Party] = [issuer]
    @choice(controller=issuer, consuming=False)
    def GiveAll(self, owners: list[Party], stop: Party) -> None:
                ~x
```

### g12: CompilerPanic at forge/codegen/loops.py:354

```python
from forge.models import ContractId, Decimal, Party, choice, ledger_effect, template
def verify(cids: list[ContractId[Iou]], p: Party) -> Decimal:
    total = Decimal(0)
    for c in cids:
        i = fetch(c)
        total = total + i.amount
    issuer: Party
@template
class Iou:
    signatory: list[Party] = [issuer]
```

## Bad Daml

BAD_DAML means that forge said OK and wrote Daml, but damlc, the Daml compiler, rejects that Daml. That is a bug in forge: its check stage let through a program that it then translated to wrong Daml. Each group folder has the input, its daml.yaml, and forge's Daml, so `dpm build` in the folder shows the error again.

damlc built 1303 distinct Daml texts of the OK inputs in 9.99 s. It rejected 1124, which 2017 OK inputs have.

## 33 bad Daml groups

| Group | Count | damlc error | damlc stage | Seed | First seen | Input | Daml |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | 1 | duplicate field name ‘…’ in record construction | typecheck | contracts/loop_many/loop_many.vy | input 4, 0.01 s | [loop_many.vy](groups/d01/loop_many.vy) | [LoopMany.daml](groups/d01/LoopMany.daml) |
| d02 | 280 | Couldn't match type ‘…’ with ‘…’ | typecheck | contracts/loop_verify/loop_verify.vy | input 8, 0.02 s | [loop_verify.vy](groups/d02/loop_verify.vy) | [LoopVerify.daml](groups/d02/LoopVerify.daml) |
| d03 | 9 | You cannot bind scoped type variable ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 21, 0.03 s | [loop_many.vy](groups/d03/loop_many.vy) | [LoopMany.daml](groups/d03/LoopMany.daml) |
| d04 | 86 | Couldn't match expected type ‘…’ | typecheck | contracts/loop_pure/loop_pure.vy | input 29, 0.04 s | [loop_pure.vy](groups/d04/loop_pure.vy) | [LoopPure.daml](groups/d04/LoopPure.daml) |
| d05 | 2 | Tried to get field ‘…’ with type ‘…’ | typecheck | contracts/loop_verify/loop_verify.vy | input 54, 0.05 s | [loop_verify.vy](groups/d05/loop_verify.vy) | [LoopVerify.daml](groups/d05/LoopVerify.daml) |
| d06 | 187 | Tried to access nonexistent field ‘…’ with type ‘…’ on value of type ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 55, 0.06 s | [loop_many.vy](groups/d06/loop_many.vy) | [LoopMany.daml](groups/d06/LoopMany.daml) |
| d07 | 82 | Couldn't match expected type ‘…’ with actual type ‘…’ | typecheck | contracts/loop_pure/loop_pure.vy | input 76, 0.07 s | [loop_pure.vy](groups/d07/loop_pure.vy) | [LoopPure.daml](groups/d07/LoopPure.daml) |
| d08 | 570 | Variable not in scope: … | typecheck | contracts/loop_many/loop_many.vy | input 97, 0.08 s | [loop_many.vy](groups/d08/loop_many.vy) | [LoopMany.daml](groups/d08/LoopMany.daml) |
| d09 | 97 | parse error on input ‘…’ | parser | contracts/loop_pure/loop_pure.vy | input 126, 0.1 s | [loop_pure.vy](groups/d09/loop_pure.vy) | [LoopPure.daml](groups/d09/LoopPure.daml) |
| d10 | 136 | Not in scope: ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 181, 0.12 s | [loop_many.vy](groups/d10/loop_many.vy) | [LoopMany.daml](groups/d10/LoopMany.daml) |
| d11 | 270 | Duplicate field name …. Original definition at …. | parser | contracts/loop_give/loop_give.vy | input 185, 0.13 s | [loop_give.vy](groups/d11/loop_give.vy) | [LoopGive.daml](groups/d11/LoopGive.daml) |
| d12 | 110 | Data constructor not in scope: … | typecheck | contracts/loop_verify/loop_verify.vy | input 284, 0.19 s | [loop_verify.vy](groups/d12/loop_verify.vy) | [LoopVerify.daml](groups/d12/LoopVerify.daml) |
| d13 | 23 | Tried to access nonexistent field ‘…’ with type ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 417, 0.26 s | [loop_many.vy](groups/d13/loop_many.vy) | [LoopMany.daml](groups/d13/LoopMany.daml) |
| d14 | 38 | Ambiguous type variable ‘…’ arising from a use of ‘…’ | typecheck | contracts/loop_verify/loop_verify.vy | input 464, 0.28 s | [loop_verify.vy](groups/d14/loop_verify.vy) | [LoopVerify.daml](groups/d14/LoopVerify.daml) |
| d15 | 16 | No instance for (IsParties …) | typecheck | contracts/loop_many/loop_many.vy | input 492, 0.3 s | [loop_many.vy](groups/d15/loop_many.vy) | [LoopMany.daml](groups/d15/LoopMany.daml) |
| d16 | 30 | Failure to process Daml program, this feature is not currently supported. | Core to Daml-LF | contracts/loop_pure/loop_pure.vy | input 521, 0.31 s | [loop_pure.vy](groups/d16/loop_pure.vy) | [LoopPure.daml](groups/d16/LoopPure.daml) |
| d17 | 6 | Ambiguous occurrence ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 725, 0.43 s | [loop_many.vy](groups/d17/loop_many.vy) | [LoopMany.daml](groups/d17/LoopMany.daml) |
| d18 | 47 | Not in scope: data constructor ‘…’ | typecheck | contracts/loop_verify/loop_verify.vy | input 809, 0.47 s | [loop_verify.vy](groups/d18/loop_verify.vy) | [LoopVerify.daml](groups/d18/LoopVerify.daml) |
| d19 | 3 | Couldn't match kind ‘…’ with ‘…’ | typecheck | contracts/loop_count/loop_count.vy | input 914, 0.53 s | [loop_count.vy](groups/d19/loop_count.vy) | [LoopCount.daml](groups/d19/LoopCount.daml) |
| d20 | 4 | Couldn't match type ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 3258, 1.8 s | [loop_many.vy](groups/d20/loop_many.vy) | [LoopMany.daml](groups/d20/LoopMany.daml) |
| d21 | 1 | The constructor ‘…’ should have 3 arguments, but has been given none | typecheck | contracts/loop_many/loop_many.vy | input 4500, 2.44 s | [loop_many.vy](groups/d21/loop_many.vy) | [LoopMany.daml](groups/d21/LoopMany.daml) |
| d22 | 3 | Ambiguous type variable ‘…’ arising from the literal ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 4893, 2.65 s | [loop_many.vy](groups/d22/loop_many.vy) | [LoopMany.daml](groups/d22/LoopMany.daml) |
| d23 | 4 | Tried to get field ‘…’ with type ‘…’ on value of type ‘…’, but that field has type ‘…’ | typecheck | contracts/loop_count/loop_count.vy | input 5459, 2.97 s | [loop_count.vy](groups/d23/loop_count.vy) | [LoopCount.daml](groups/d23/LoopCount.daml) |
| d24 | 2 | Constructor ‘…’ does not have field ‘…’ | typecheck | contracts/loop_many/loop_many.vy | input 6749, 3.64 s | [loop_many.vy](groups/d24/loop_many.vy) | [LoopMany.daml](groups/d24/LoopMany.daml) |
| d25 | 1 | No instance for (HasCreate …) | typecheck | contracts/loop_give/loop_give.vy | input 6890, 3.71 s | [loop_give.vy](groups/d25/loop_give.vy) | [LoopGive.daml](groups/d25/LoopGive.daml) |
| d26 | 2 | Duplicate type signatures for ‘…’ | typecheck | contracts/loop_verify/loop_verify.vy | input 7197, 3.89 s | [loop_verify.vy](groups/d26/loop_verify.vy) | [LoopVerify.daml](groups/d26/LoopVerify.daml) |
| d27 | 1 | Parse error in pattern: … | parser | contracts/loop_many/loop_many.vy | input 7832, 4.24 s | [loop_many.vy](groups/d27/loop_many.vy) | [LoopMany.daml](groups/d27/LoopMany.daml) |
| d28 | 1 | `self' is a prohibited field name, please use something else. | parser | contracts/loop_give/loop_give.vy | input 7970, 4.32 s | [loop_give.vy](groups/d28/loop_give.vy) | [LoopGive.daml](groups/d28/LoopGive.daml) |
| d29 | 1 | Constructor ‘…’ does not have the required strict field(s): … | typecheck | contracts/loop_give/loop_give.vy | input 13531, 7.31 s | [loop_give.vy](groups/d29/loop_give.vy) | [LoopGive.daml](groups/d29/LoopGive.daml) |
| d30 | 1 | The type signature for ‘…’ lacks an accompanying binding | typecheck | contracts/loop_pure/loop_pure.vy | input 13589, 7.34 s | [loop_pure.vy](groups/d30/loop_pure.vy) | [LoopPure.daml](groups/d30/LoopPure.daml) |
| d31 | 1 | No instance for (HasFetch …) | typecheck | contracts/loop_count/loop_count.vy | input 13609, 7.35 s | [loop_count.vy](groups/d31/loop_count.vy) | [LoopCount.daml](groups/d31/LoopCount.daml) |
| d32 | 1 | name collision between choice … and field … | Daml-LF typechecker | contracts/loop_many/loop_many.vy | input 15968, 8.64 s | [loop_many.vy](groups/d32/loop_many.vy) | [LoopMany.daml](groups/d32/LoopMany.daml) |
| d33 | 1 | Conflicting definitions for ‘…’ | typecheck | contracts/loop_pure/loop_pure.vy | input 18880, 10.22 s | [loop_pure.vy](groups/d33/loop_pure.vy) | [LoopPure.daml](groups/d33/LoopPure.daml) |

### First error lines

- d01, LoopMany.daml line 26: `duplicate field name ‘issuer’ in record construction`
- d02, LoopVerify.daml line 16: `Couldn't match type ‘()’ with ‘Numeric 10’`
- d03, LoopMany.daml line 20: `You cannot bind scoped type variable ‘o’`
- d04, LoopPure.daml line 33: `Couldn't match expected type ‘Iou -> Party’`
- d05, LoopVerify.daml line 13: `Tried to get field ‘amount’ with type ‘Iou`
- d06, LoopMany.daml line 24: `Tried to access nonexistent field ‘owner’ with type ‘Party’ on value of type ‘t0`
- d07, LoopPure.daml line 28: `Couldn't match expected type ‘Int’ with actual type ‘[a0]’`
- d08, LoopMany.daml line 24: `Variable not in scope: x : Bool`
- d09, LoopPure.daml line 47: `parse error on input ‘Int’`
- d10, LoopMany.daml line 25: `Not in scope: ‘issuer’`
- d11, LoopGive.daml line 9: `Duplicate field name owner. Original definition at LoopGive.daml:8:5-9.`
- d12, LoopVerify.daml line 16: `Data constructor not in scope: Decimal : Decimal`
- d13, LoopMany.daml line 27: `Tried to access nonexistent field ‘append’ with type ‘Update`
- d14, LoopVerify.daml line 25: `Ambiguous type variable ‘a0’ arising from a use of ‘toParties’`
- d15, LoopMany.daml line 17: `No instance for (IsParties Int) arising from a use of ‘toParties’`
- d16, LoopPure.daml line 38: `Failure to process Daml program, this feature is not currently supported.`
- d17, LoopMany.daml line 1: `Ambiguous occurrence ‘Party’`
- d18, LoopVerify.daml line 9: `Not in scope: data constructor ‘ContractId’`
- d19, LoopCount.daml line 21: `Couldn't match kind ‘GHC.Types.Nat’ with ‘*’`
- d20, LoopMany.daml line 1: `Couldn't match type ‘[ContractId Iou]’`
- d21, LoopMany.daml line 22: `The constructor ‘Iou’ should have 3 arguments, but has been given none`
- d22, LoopMany.daml line 27: `Ambiguous type variable ‘n0’ arising from the literal ‘1.5’`
- d23, LoopCount.daml line 27: `Tried to get field ‘amount’ with type ‘Int’ on value of type ‘Iou’, but that field has type ‘Decimal’`
- d24, LoopMany.daml line 26: `Constructor ‘Iou’ does not have field ‘create’`
- d25, LoopGive.daml line 26: `No instance for (HasCreate Party) arising from a use of ‘create’`
- d26, LoopVerify.daml line 8: `Duplicate type signatures for ‘verify’`
- d27, LoopMany.daml line 28: `Parse error in pattern: (tuple)`
- d28, LoopGive.daml line 9: `` `self' is a prohibited field name, please use something else. ``
- d29, LoopGive.daml line 26: `Constructor ‘Iou’ does not have the required strict field(s): stop`
- d30, LoopPure.daml line 3: `The type signature for ‘total_of’ lacks an accompanying binding`
- d31, LoopCount.daml line 24: `No instance for (HasFetch Decimal) arising from a use of ‘fetch’`
- d32, LoopMany.daml line 1: `name collision between choice LoopMany:Iou.Owner and field LoopMany:Iou.owner`
- d33, LoopPure.daml line 27: `Conflicting definitions for ‘total’`

## Loop check

BAD_LOOP means that forge said OK and wrote Daml, but the loop check finds a loop bug, L1 to L4, in that Daml. The check reads forge's Daml and the .vy text, with no damlc. An input goes to the group of its first check. With --damlc, the groups are also split by whether damlc builds the Daml. A group that builds is the most serious case: damlc accepts the wrong code. Each group folder has the input, its daml.yaml when the seed has one, forge's Daml, and in shrunk/ the shrunk input and its Daml.

188 OK inputs have loop bugs.

- `L1`: forge writes `foldlA`, the fold for a loop with a ledger action, but does not import it from `DA.Action`. damlc rejects the Daml.
- `L2`: forge writes the pure fold `foldl` for a loop whose body has a ledger action, such as `fetch` or `create`. A ledger action needs `foldlA` in an `Update`.
- `L3`: A `return` in a loop of the .vy code has no early-return helper (`_damlforge_loopN`) in the Daml, so the return is lost: the loop goes on, or the function returns another value. damlc can build this Daml.
- `L4`: A ledger action, in a loop or not, is used as a value: it is not bound with `<-` and is not a statement of a `do` block, so the code gets an `Update`, not its result.

## 5 loop groups

| Group | Check | Checks | Count | damlc | Seed | First seen | Input | Daml | Shrunk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| l01 | L3 | L3 | 28 | builds | contracts/loop_pure/loop_pure.vy | input 13, 0.02 s | [loop_pure.vy](groups/l01/loop_pure.vy) | [LoopPure.daml](groups/l01/LoopPure.daml) | [5 of 40 lines](groups/l01/shrunk/loop_pure.vy) |
| l02 | L4 | L4 | 37 | rejects | contracts/loop_count/loop_count.vy | input 68, 0.07 s | [loop_count.vy](groups/l02/loop_count.vy) | [LoopCount.daml](groups/l02/LoopCount.daml) | [9 of 21 lines](groups/l02/shrunk/loop_count.vy) |
| l03 | L2 | L2 L4 | 77 | rejects | contracts/loop_verify/loop_verify.vy | input 127, 0.1 s | [loop_verify.vy](groups/l03/loop_verify.vy) | [LoopVerify.daml](groups/l03/LoopVerify.daml) | [9 of 25 lines](groups/l03/shrunk/loop_verify.vy) |
| l04 | L1 | L1 | 17 | rejects | contracts/loop_many/loop_many.vy | input 456, 0.28 s | [loop_many.vy](groups/l04/loop_many.vy) | [LoopMany.daml](groups/l04/LoopMany.daml) | [10 of 19 lines](groups/l04/shrunk/loop_many.vy) |
| l05 | L3 | L3 | 29 | rejects | contracts/loop_pure/loop_pure.vy | input 710, 0.42 s | [loop_pure.vy](groups/l05/loop_pure.vy) | [LoopPure.daml](groups/l05/LoopPure.daml) | [13 of 43 lines](groups/l05/shrunk/loop_pure.vy) |

### Loop bugs

- l01, LoopPure.daml line 37: `the return in a loop of function has_party at Daml line 37 is lost (2 loops with a return, 0 early-return helpers)`
- l02, LoopCount.daml line 30: `fetch at Daml line 30 is used as a value, not bound with <-`. damlc: `Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update`
- l03, LoopVerify.daml line 9: `fetch at Daml line 9 in the pure foldl of line 7`. damlc: `Tried to access nonexistent field ‘issuer’ with type ‘Party’ on value of type ‘Update`
- l04, LoopMany.daml line 20: `foldlA at Daml line 20 with no import DA.Action`. damlc: `Variable not in scope: foldlA`
- l05, LoopPure.daml line 56: `the return in a loop of choice Check at Daml line 56 is lost (1 loop with a return, 0 early-return helpers)`. damlc: `Couldn't match type ‘Numeric 10’ with ‘()’`

## Shrunk loop inputs

### l01: L3, damlc builds

```python
def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
            for _k in range(0, 2):
                return True
    return False
```

```daml
module LoopPure where

has_party : [Party] -> Party -> Bool
has_party ps p =
  False
```

### l02: L4, damlc rejects

```python
from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Count(self, cids: list[ContractId[Iou]]) -> int:
            if fetch(c).amount > Decimal(1):
                n = n + 1
```

```daml
module LoopCount where

template Iou
  with
    owner : Party
  where
    signatory [issuer]

    nonconsuming choice Count : Int
      with
        cids : [ContractId Iou]
      controller owner
      do
        let self = this
        if (fetch c).amount > (1.0 : Decimal)
          then do
            let n = n + 1
            pure ()
          else do
            pure ()
```

### l03: L2, damlc rejects

```python
from forge.models import ContractId, Decimal, Party, choice, ledger_effect, template
def verify(cids: list[ContractId[Iou]], p: Party) -> Decimal:
    total = Decimal(0)
    for c in cids:
        i = fetch(c)
        total = total + i.amount
@template
class Iou:
    signatory: list[Party] = [issuer]
```

```daml
module LoopVerify where

verify : [ContractId Iou] -> Party -> Decimal
verify cids p =
  let total = (0.0 : Decimal) in
  let _damlforge_total2 =
        foldl
          (\total c ->
            let i = fetch c in
            let _damlforge_total1 = total + i.amount in
            _damlforge_total1)
          total cids
  in
  ()

template Iou
  where
    signatory [issuer]
```

### l04: L1, damlc rejects

```python
from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Many(self, owners: list[Party]) -> list[ContractId[Iou]]:
        cids: list[ContractId[Iou]] = []
        for o in owners:
                cids.append(create(Iou(issuer=self.issuer, owner=o, amount=self.amount)))
```

```daml
module LoopMany where

template Iou
  with
    owner : Party
  where
    signatory [issuer]

    nonconsuming choice Many : [ContractId Iou]
      with
        owners : [Party]
      controller owner
      do
        let self = this
        let (cids : [ContractId Iou]) = []
        _damlforge_cids3 <-
          foldlA
            (\cids o -> do
              _damlforge_cids_item1 <- create (Iou with issuer = self.issuer, owner = o, amount = self.amount)
              let _damlforge_cids2 = cids <> [_damlforge_cids_item1]
              pure _damlforge_cids2)
            cids owners
        pure ()
```

### l05: L3, damlc rejects

```python
from forge.models import Decimal, Party, choice, template
def total_of(xs: list[Decimal]) -> Decimal:
    total = Decimal(0)
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=False)
    def Check(self, xs: list[Decimal]) -> Decimal:
        for x in xs:
            if x == x:
                return total_of(xs)
            assert x > Decimal(0), "positive"
```

```daml
module LoopPure where

import DA.Action (foldlA)

total_of : [Decimal] -> Decimal
total_of xs =
  let total = (0.0 : Decimal) in
  ()

template Iou
  with
    owner : Party
  where
    signatory [issuer]

    nonconsuming choice Check : Decimal
      with
        xs : [Decimal]
      controller owner
      do
        let self = this
        _ <-
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
        pure ()
```

## Run and compare

BAD_RUN means that forge said OK and wrote Daml that damlc builds, but the Daml does not do what the .vy code does. The run calls each function and choice of the seed's calls file in Python, on the .vy code, and in Daml Script, on forge's Daml, with the same data, and compares the results and the contracts that each call makes. An input goes to the group of its first difference, in calls file order, and its first loop check. Each group folder is a Daml project with the input, its calls file, forge's Daml, and a test, so `dpm test` in the folder shows the difference again.

The run compared 1462 OK inputs in 100.39 s, and 13 differ. Python could run no call of 1868, and damlc rejects the Daml or the test of 762. 60 calls of the compared inputs were not compared.

## 3 run groups

| Group | Difference | Call | Loop check | Count | Seed | First seen | Input | Test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r01 | result | has_party #3 | L3 | 10 | contracts/loop_pure/loop_pure.vy | input 13, 0.02 s | [loop_pure.vy](groups/r01/loop_pure.vy) | [Test.daml](groups/r01/daml/Test.daml) |
| r02 | contracts | Iou.GiveAll #1 | - | 2 | contracts/loop_give/loop_give.vy | input 2936, 1.64 s | [loop_give.vy](groups/r02/loop_give.vy) | [Test.daml](groups/r02/daml/Test.daml) |
| r03 | daml_passes | Iou.Check #6 | - | 1 | contracts/loop_pure/loop_pure.vy | input 19839, 10.76 s | [loop_pure.vy](groups/r03/loop_pure.vy) | [Test.daml](groups/r03/daml/Test.daml) |

### What Python does

- r01, has_party #3: `returns True`. Run `dpm test` in groups/r01 to see what Daml does.
- r02, Iou.GiveAll #1: `returns None, makes 2 contracts: Iou(issuer=alice, owner=alice, amount=1.0), Iou(issuer=alice, owner=bob, amount=1.0)`. Run `dpm test` in groups/r02 to see what Daml does.
- r03, Iou.Check #6: `fails: positive`. Run `dpm test` in groups/r03 to see what Daml does.
