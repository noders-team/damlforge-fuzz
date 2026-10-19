# damlforge-fuzz run 2026-10-19T18:45:34Z

- Random seed: 1
- Limit: 20000 inputs
- Seeds: `contracts/asset_proposal/asset_proposal.vy`, `contracts/ballot/ballot.vy`, `contracts/escrow/escrow.vy`, `contracts/iou/iou.vy`
- DamlForge: 0.0.11

## Totals

20000 inputs: 3692 OK, 13742 rejected, 1138 crash, 1428 skipped.

## 14 crash groups

| Group | Count | Exception | Stage | Seed | First seen | Input | Shrunk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| g01 | 89 | CompilerPanic at forge/ir/lower.py:314 | lower | contracts/iou/iou.vy | input 7, 0.01 s | [iou.vy](groups/g01/iou.vy) | [8 of 37 lines](groups/g01/shrunk/iou.vy) |
| g02 | 114 | AttributeError at forge/semantics/analysis/types.py:644 | check | contracts/escrow/escrow.vy | input 24, 0.03 s | [escrow.vy](groups/g02/escrow.vy) | [3 of 42 lines](groups/g02/shrunk/escrow.vy) |
| g03 | 249 | IndentationError at forge/ast/pre_parser.py:304 | parse | contracts/asset_proposal/asset_proposal.vy | input 28, 0.03 s | [asset_proposal.vy](groups/g03/asset_proposal.vy) | [2 of 36 lines](groups/g03/shrunk/asset_proposal.vy) |
| g04 | 567 | CompilerPanic at forge/ir/lower.py:115 | check | contracts/escrow/escrow.vy | input 45, 0.04 s | [escrow.vy](groups/g04/escrow.vy) | [2 of 43 lines](groups/g04/shrunk/escrow.vy) |
| g05 | 72 | AssertionError at forge/ast/parse.py:106 | parse | contracts/iou/iou.vy | input 119, 0.12 s | [iou.vy](groups/g05/iou.vy) | [4 of 36 lines](groups/g05/shrunk/iou.vy) |
| g06 | 8 | CompilerPanic at forge/codegen/emit.py:271 | emit | contracts/ballot/ballot.vy | input 212, 0.2 s | [ballot.vy](groups/g06/ballot.vy) | [2 of 32 lines](groups/g06/shrunk/ballot.vy) |
| g07 | 6 | KeyError at forge/ir/lower.py:289 | lower | contracts/iou/iou.vy | input 369, 0.35 s | [iou.vy](groups/g07/iou.vy) | [12 of 36 lines](groups/g07/shrunk/iou.vy) |
| g08 | 1 | AssertionError at forge/ast/parse.py:110 | parse | contracts/iou/iou.vy | input 1049, 0.97 s | [iou.vy](groups/g08/iou.vy) | [3 of 36 lines](groups/g08/shrunk/iou.vy) |
| g09 | 13 | AttributeError at forge/semantics/analysis/types.py:630 | check | contracts/escrow/escrow.vy | input 1582, 1.42 s | [escrow.vy](groups/g09/escrow.vy) | [2 of 41 lines](groups/g09/shrunk/escrow.vy) |
| g10 | 2 | CompilerPanic at forge/codegen/loops.py:354 | emit | contracts/ballot/ballot.vy | input 1719, 1.54 s | [ballot.vy](groups/g10/ballot.vy) | [5 of 33 lines](groups/g10/shrunk/ballot.vy) |
| g11 | 2 | CompilerPanic at forge/codegen/emit.py:596 | emit | contracts/ballot/ballot.vy | input 1954, 1.73 s | [ballot.vy](groups/g11/ballot.vy) | [6 of 33 lines](groups/g11/shrunk/ballot.vy) |
| g12 | 5 | ModuleNotFoundError at forge/semantics/analysis/imports.py:108 | check | contracts/asset_proposal/asset_proposal.vy | input 2454, 2.16 s | [asset_proposal.vy](groups/g12/asset_proposal.vy) | [1 of 34 lines](groups/g12/shrunk/asset_proposal.vy) |
| g13 | 2 | IndexError at forge/ast/pre_parser.py:389 | parse | contracts/ballot/ballot.vy | input 2913, 2.58 s | [ballot.vy](groups/g13/ballot.vy) | [2 of 33 lines](groups/g13/shrunk/ballot.vy) |
| g14 | 8 | KeyError at forge/ir/lower.py:298 | lower | contracts/asset_proposal/asset_proposal.vy | input 7163, 6.16 s | [asset_proposal.vy](groups/g14/asset_proposal.vy) | [8 of 33 lines](groups/g14/shrunk/asset_proposal.vy) |

## Stages

- `parse`: forge reads the .vy text and makes a syntax tree (forge.ast.parse_to_ast). A crash here means forge failed while it read the code.
- `check`: forge checks names, types, imports, and the rules for templates and choices (forge.semantics.analyze_module). Wrong code must stop here with a DF error.
- `lower`: forge changes the checked program into its internal form, IR (forge.ir.lower_module). A crash here usually means that check let through code that forge cannot translate.
- `emit`: forge writes the Daml code from the IR (forge.codegen.generate_daml).

The stage is the step that was running, not the folder of the forge file, so a crash can have stage `check` and a line in `forge/ir/lower.py`.

## Shrunk inputs

### g01: CompilerPanic at forge/ir/lower.py:314

```python
from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=True)
    def Transfer(self, new_owner: Party) -> ContractId[Iou]:
        import os
```

### g02: AttributeError at forge/semantics/analysis/types.py:644

```python
@template
class Escrow:
    tuple[int, str]: EscrowTerms
```

### g03: IndentationError at forge/ast/pre_parser.py:304

```python
            )
    @choice(controller=owner, consuming=True)
```

### g04: CompilerPanic at forge/ir/lower.py:115

```python
struct EscrowTerms:
    amount: 0.0
```

### g05: AssertionError at forge/ast/parse.py:106

```python
@template
class Iou:
        return {k: v for k, v in m}(
        )
```

### g06: CompilerPanic at forge/codegen/emit.py:271

```python
def count_yes(votes: GenMap[Party, bool]) -> int:
    organizer: Party
```

### g07: KeyError at forge/ir/lower.py:289

```python
from forge.models import ContractId, Decimal, Party, choice, template
@template
class Iou:
    owner: Party
    signatory: list[Party] = [issuer]
    @choice(controller=owner, consuming=True)
    def Transfer(self, new_owner: Party) -> ContractId[Iou]:
        rest = create(
            Iou(
                amount=self.amount >> split_amount,
            )
        )
```

### g08: AssertionError at forge/ast/parse.py:110

```python
@template
class Iou:
        assert split_amount < self.amount, "split "x" must be less than the full amount"
```

### g09: AttributeError at forge/semantics/analysis/types.py:630

```python
struct EscrowTerms:
    ContractId[int]: Decimal
```

### g10: CompilerPanic at forge/codegen/loops.py:354

```python
def count_yes(votes: GenMap[Party, bool]) -> int:
    count = 0
    for in_favor in answers:
            count = count + 1
    issuer: Party
```

### g11: CompilerPanic at forge/codegen/emit.py:596

```python
def count_yes(votes: GenMap[Party, bool]) -> int:
    count = 0
    for in_favor in answers:
        return
        if in_favor:
            count = count + 1
```

### g12: ModuleNotFoundError at forge/semantics/analysis/imports.py:108

```python
from forge.AssetProposal import ContractId, Party, choice, template
```

### g13: IndexError at forge/ast/pre_parser.py:389

```python
    for in_favor "" answers:
        if [x for x in xs]:
```

### g14: KeyError at forge/ir/lower.py:298

```python
from forge.models import ContractId, Party, choice, template
@template
class Asset:
    owner: Party
    signatory: list[Party] = [issuer, owner]
    @choice(controller=owner, consuming=True)
    def Reject(self) -> None:
        ~x
```

## Bad Daml

BAD_DAML means that forge said OK and wrote Daml, but damlc, the Daml compiler, rejects that Daml. That is a bug in forge: its check stage let through a program that it then translated to wrong Daml. Each group folder has the input, its daml.yaml, and forge's Daml, so `dpm build` in the folder shows the error again.

damlc built 1437 distinct Daml texts of the OK inputs in 14.75 s. It rejected 1177, which 1721 OK inputs have.

## 30 bad Daml groups

| Group | Count | damlc error | damlc stage | Seed | First seen | Input | Daml |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | 114 | Constructor ‘…’ does not have the required strict field(s): … | typecheck | contracts/ballot/ballot.vy | input 3, 0.01 s | [ballot.vy](groups/d01/ballot.vy) | [Ballot.daml](groups/d01/Ballot.daml) |
| d02 | 321 | Variable not in scope: … | typecheck | contracts/iou/iou.vy | input 9, 0.01 s | [iou.vy](groups/d02/iou.vy) | [Iou.daml](groups/d02/Iou.daml) |
| d03 | 61 | Data constructor not in scope: … | typecheck | contracts/escrow/escrow.vy | input 25, 0.03 s | [escrow.vy](groups/d03/escrow.vy) | [Escrow.daml](groups/d03/Escrow.daml) |
| d04 | 170 | Couldn't match type ‘…’ with ‘…’ | typecheck | contracts/iou/iou.vy | input 41, 0.03 s | [iou.vy](groups/d04/iou.vy) | [Iou.daml](groups/d04/Iou.daml) |
| d05 | 21 | Couldn't match type ‘…’ | typecheck | contracts/iou/iou.vy | input 100, 0.09 s | [iou.vy](groups/d05/iou.vy) | [Iou.daml](groups/d05/Iou.daml) |
| d06 | 128 | Tried to access nonexistent field ‘…’ with type ‘…’ on value of type ‘…’ | typecheck | contracts/iou/iou.vy | input 106, 0.1 s | [iou.vy](groups/d06/iou.vy) | [Iou.daml](groups/d06/Iou.daml) |
| d07 | 128 | Not in scope: ‘…’ | typecheck | contracts/escrow/escrow.vy | input 109, 0.1 s | [escrow.vy](groups/d07/escrow.vy) | [Escrow.daml](groups/d07/Escrow.daml) |
| d08 | 304 | Duplicate field name …. Original definition at …. | parser | contracts/ballot/ballot.vy | input 128, 0.13 s | [ballot.vy](groups/d08/ballot.vy) | [Ballot.daml](groups/d08/Ballot.daml) |
| d09 | 25 | No instance for (IsParties …) | typecheck | contracts/escrow/escrow.vy | input 195, 0.18 s | [escrow.vy](groups/d09/escrow.vy) | [Escrow.daml](groups/d09/Escrow.daml) |
| d10 | 9 | Parse error in pattern: … | parser | contracts/escrow/escrow.vy | input 288, 0.28 s | [escrow.vy](groups/d10/escrow.vy) | [Escrow.daml](groups/d10/Escrow.daml) |
| d11 | 6 | Multiple declarations of ‘…’ | typecheck | contracts/escrow/escrow.vy | input 313, 0.3 s | [escrow.vy](groups/d11/escrow.vy) | [Escrow.daml](groups/d11/Escrow.daml) |
| d12 | 42 | Couldn't match expected type ‘…’ with actual type ‘…’ | typecheck | contracts/ballot/ballot.vy | input 427, 0.42 s | [ballot.vy](groups/d12/ballot.vy) | [Ballot.daml](groups/d12/Ballot.daml) |
| d13 | 69 | Couldn't match expected type ‘…’ | typecheck | contracts/ballot/ballot.vy | input 582, 0.56 s | [ballot.vy](groups/d13/ballot.vy) | [Ballot.daml](groups/d13/Ballot.daml) |
| d14 | 105 | parse error on input ‘…’ | parser | contracts/escrow/escrow.vy | input 670, 0.63 s | [escrow.vy](groups/d14/escrow.vy) | [Escrow.daml](groups/d14/Escrow.daml) |
| d15 | 29 | Not in scope: data constructor ‘…’ | typecheck | contracts/ballot/ballot.vy | input 757, 0.71 s | [ballot.vy](groups/d15/ballot.vy) | [Ballot.daml](groups/d15/Ballot.daml) |
| d16 | 22 | Ambiguous type variable ‘…’ arising from a use of ‘…’ | typecheck | contracts/ballot/ballot.vy | input 786, 0.73 s | [ballot.vy](groups/d16/ballot.vy) | [Ballot.daml](groups/d16/Ballot.daml) |
| d17 | 12 | Failure to process Daml program, this feature is not currently supported. | Core to Daml-LF | contracts/asset_proposal/asset_proposal.vy | input 877, 0.82 s | [asset_proposal.vy](groups/d17/asset_proposal.vy) | [AssetProposal.daml](groups/d17/AssetProposal.daml) |
| d18 | 51 | Constructor ‘…’ does not have field ‘…’ | typecheck | contracts/asset_proposal/asset_proposal.vy | input 1002, 0.92 s | [asset_proposal.vy](groups/d18/asset_proposal.vy) | [AssetProposal.daml](groups/d18/AssetProposal.daml) |
| d19 | 5 | name collision between choice … and field … | Daml-LF typechecker | contracts/iou/iou.vy | input 1126, 1.05 s | [iou.vy](groups/d19/iou.vy) | [Iou.daml](groups/d19/Iou.daml) |
| d20 | 44 | duplicate field name ‘…’ in record construction | typecheck | contracts/iou/iou.vy | input 1262, 1.16 s | [iou.vy](groups/d20/iou.vy) | [Iou.daml](groups/d20/Iou.daml) |
| d21 | 23 | Ambiguous occurrence ‘…’ | typecheck | contracts/ballot/ballot.vy | input 1417, 1.3 s | [ballot.vy](groups/d21/ballot.vy) | [Ballot.daml](groups/d21/Ballot.daml) |
| d22 | 5 | `self' is a prohibited field name, please use something else. | parser | contracts/asset_proposal/asset_proposal.vy | input 1734, 1.54 s | [asset_proposal.vy](groups/d22/asset_proposal.vy) | [AssetProposal.daml](groups/d22/AssetProposal.daml) |
| d23 | 12 | Tried to access nonexistent field ‘…’ with type ‘…’ | typecheck | contracts/ballot/ballot.vy | input 2142, 1.91 s | [ballot.vy](groups/d23/ballot.vy) | [Ballot.daml](groups/d23/Ballot.daml) |
| d24 | 3 | Tried to get field ‘…’ with type ‘…’ on value of type ‘…’, but that field has type ‘…’ | typecheck | contracts/escrow/escrow.vy | input 3246, 2.85 s | [escrow.vy](groups/d24/escrow.vy) | [Escrow.daml](groups/d24/Escrow.daml) |
| d25 | 2 | Tried to get field ‘…’ with type ‘…’ | typecheck | contracts/iou/iou.vy | input 3780, 3.31 s | [iou.vy](groups/d25/iou.vy) | [Iou.daml](groups/d25/Iou.daml) |
| d26 | 1 | Duplicate type signatures for ‘…’ | typecheck | contracts/ballot/ballot.vy | input 6068, 5.23 s | [ballot.vy](groups/d26/ballot.vy) | [Ballot.daml](groups/d26/Ballot.daml) |
| d27 | 6 | You cannot bind scoped type variable ‘…’ | typecheck | contracts/ballot/ballot.vy | input 6492, 5.63 s | [ballot.vy](groups/d27/ballot.vy) | [Ballot.daml](groups/d27/Ballot.daml) |
| d28 | 1 | Expected kind ‘…’, but ‘…’ has kind ‘…’ | typecheck | contracts/asset_proposal/asset_proposal.vy | input 6725, 5.82 s | [asset_proposal.vy](groups/d28/asset_proposal.vy) | [AssetProposal.daml](groups/d28/AssetProposal.daml) |
| d29 | 1 | The constructor ‘…’ should have 3 arguments, but has been given none | typecheck | contracts/ballot/ballot.vy | input 6916, 5.98 s | [ballot.vy](groups/d29/ballot.vy) | [Ballot.daml](groups/d29/Ballot.daml) |
| d30 | 1 | No instance for (IsParties | typecheck | contracts/iou/iou.vy | input 10590, 9.08 s | [iou.vy](groups/d30/iou.vy) | [Iou.daml](groups/d30/Iou.daml) |

### First error lines

- d01, Ballot.daml line 44: `Constructor ‘Ballot’ does not have the required strict field(s): owner`
- d02, Iou.daml line 28: `Variable not in scope: x : [a0]`
- d03, Escrow.daml line 35: `Data constructor not in scope: ContractId : [ContractId Payout]`
- d04, Iou.daml line 1: `Couldn't match type ‘Iou’ with ‘ContractId Iou’`
- d05, Iou.daml line 1: `Couldn't match type ‘ContractId Iou’`
- d06, Iou.daml line 30: `Tried to access nonexistent field ‘_1’ with type ‘Party’ on value of type ‘r0’`
- d07, Escrow.daml line 33: `Not in scope: ‘float’`
- d08, Ballot.daml line 27: `Duplicate field name organizer. Original definition at Ballot.daml:26:5-13.`
- d09, Escrow.daml line 30: `No instance for (IsParties Bool)`
- d10, Escrow.daml line 40: `Parse error in pattern: x . _1`
- d11, Escrow.daml line 18: `Multiple declarations of ‘Payout’`
- d12, Ballot.daml line 49: `Couldn't match expected type ‘Update a0’ with actual type ‘Bool’`
- d13, Ballot.daml line 9: `Couldn't match expected type ‘Map k0 Bool’`
- d14, Escrow.daml line 6: `parse error on input ‘Party’`
- d15, Ballot.daml line 13: `Not in scope: data constructor ‘Decimal’`
- d16, Ballot.daml line 30: `Ambiguous type variable ‘a0’ arising from a use of ‘toParties’`
- d17, AssetProposal.daml line 3: `Failure to process Daml program, this feature is not currently supported.`
- d18, AssetProposal.daml line 18: `Constructor ‘AssetProposal’ does not have field ‘issuer’`
- d19, Iou.daml line 1: `name collision between choice Iou:Iou.Currency and field Iou:Iou.currency`
- d20, Iou.daml line 31: `duplicate field name ‘issuer’ in record construction`
- d21, Ballot.daml line 1: `Ambiguous occurrence ‘Bool’`
- d22, AssetProposal.daml line 25: `` `self' is a prohibited field name, please use something else. ``
- d23, Ballot.daml line 42: `Tried to access nonexistent field ‘consuming’ with type ‘Map`
- d24, Escrow.daml line 40: `Tried to get field ‘deadline’ with type ‘[Time]’ on value of type ‘EscrowTerms’, but that field has type ‘Time’`
- d25, Iou.daml line 32: `Tried to get field ‘owner’ with type ‘Transfer`
- d26, Ballot.daml line 24: `Duplicate type signatures for ‘count_yes’`
- d27, Ballot.daml line 42: `You cannot bind scoped type variable ‘self’`
- d28, AssetProposal.daml line 11: `Expected kind ‘* -> *’, but ‘Reject’ has kind ‘*’`
- d29, Ballot.daml line 10: `The constructor ‘Ballot’ should have 3 arguments, but has been given none`
- d30, Iou.daml line 11: `No instance for (IsParties`
