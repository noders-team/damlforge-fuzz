# damlforge-fuzz run 2026-10-26T07:07:10Z

- Random seed: 1
- Limit: 20000 inputs
- Seeds: `contracts/import_qualified/import_qualified.vy`, `contracts/import_qualified/models.vy`, `contracts/import_sibling/import_sibling.vy`, `contracts/import_sibling/models.vy`
- DamlForge: 0.0.13

## Totals

20000 inputs: 3176 OK, 10783 rejected, 0 crash, 6041 skipped.

## 0 crash groups

## Bad Daml

BAD_DAML means that forge said OK and wrote Daml, but damlc, the Daml compiler, rejects that Daml. That is a bug in forge: its check stage let through a program that it then translated to wrong Daml. Each group folder has the input, its daml.yaml, and forge's Daml, so `dpm build` in the folder shows the error again.

damlc built 570 distinct Daml texts of the OK inputs in 10.52 s. It rejected 390, which 595 OK inputs have.

## 21 bad Daml groups

| Group | Count | damlc error | damlc stage | Seed | First seen | Input | Daml |
| --- | --- | --- | --- | --- | --- | --- | --- |
| d01 | 159 | Variable not in scope: … | typecheck | contracts/import_sibling/models.vy | input 153, 0.1 s | [models.vy](groups/d01/models.vy) | [Models.daml](groups/d01/Models.daml) |
| d02 | 115 | parse error on input ‘…’ | parser | contracts/import_sibling/models.vy | input 161, 0.1 s | [models.vy](groups/d02/models.vy) | [Models.daml](groups/d02/Models.daml) |
| d03 | 33 | Couldn't match expected type ‘…’ | typecheck | contracts/import_qualified/models.vy | input 178, 0.12 s | [models.vy](groups/d03/models.vy) | [Models.daml](groups/d03/Models.daml) |
| d04 | 45 | Data constructor not in scope: … | typecheck | contracts/import_qualified/import_qualified.vy | input 217, 0.14 s | [import_qualified.vy](groups/d04/import_qualified.vy) | [ImportQualified.daml](groups/d04/ImportQualified.daml) |
| d05 | 28 | Ambiguous type variable ‘…’ arising from a use of ‘…’ | typecheck | contracts/import_sibling/import_sibling.vy | input 224, 0.15 s | [import_sibling.vy](groups/d05/import_sibling.vy) | [ImportSibling.daml](groups/d05/ImportSibling.daml) |
| d06 | 76 | Tried to access nonexistent field ‘…’ with type ‘…’ on value of type ‘…’ | typecheck | contracts/import_sibling/import_sibling.vy | input 320, 0.22 s | [import_sibling.vy](groups/d06/import_sibling.vy) | [ImportSibling.daml](groups/d06/ImportSibling.daml) |
| d07 | 18 | No instance for (IsParties …) | typecheck | contracts/import_sibling/import_sibling.vy | input 492, 0.32 s | [import_sibling.vy](groups/d07/import_sibling.vy) | [ImportSibling.daml](groups/d07/ImportSibling.daml) |
| d08 | 6 | Invalid type signature: … | parser | contracts/import_sibling/models.vy | input 684, 0.44 s | [models.vy](groups/d08/models.vy) | [Models.daml](groups/d08/Models.daml) |
| d09 | 2 | No instance for (HasFetch …) | typecheck | contracts/import_sibling/import_sibling.vy | input 807, 0.51 s | [import_sibling.vy](groups/d09/import_sibling.vy) | [ImportSibling.daml](groups/d09/ImportSibling.daml) |
| d10 | 7 | Tried to access nonexistent field ‘…’ with type ‘…’ | typecheck | contracts/import_sibling/import_sibling.vy | input 896, 0.58 s | [import_sibling.vy](groups/d10/import_sibling.vy) | [ImportSibling.daml](groups/d10/ImportSibling.daml) |
| d11 | 22 | Ambiguous occurrence ‘…’ | typecheck | contracts/import_sibling/import_sibling.vy | input 992, 0.64 s | [import_sibling.vy](groups/d11/import_sibling.vy) | [ImportSibling.daml](groups/d11/ImportSibling.daml) |
| d12 | 37 | Couldn't match type ‘…’ with ‘…’ | typecheck | contracts/import_qualified/import_qualified.vy | input 1089, 0.71 s | [import_qualified.vy](groups/d12/import_qualified.vy) | [ImportQualified.daml](groups/d12/ImportQualified.daml) |
| d13 | 11 | Not in scope: ‘…’ | typecheck | contracts/import_qualified/import_qualified.vy | input 1674, 1.05 s | [import_qualified.vy](groups/d13/import_qualified.vy) | [ImportQualified.daml](groups/d13/ImportQualified.daml) |
| d14 | 2 | Multiple declarations of ‘…’ | typecheck | contracts/import_qualified/models.vy | input 1758, 1.11 s | [models.vy](groups/d14/models.vy) | [Models.daml](groups/d14/Models.daml) |
| d15 | 10 | Not in scope: data constructor ‘…’ | typecheck | contracts/import_qualified/import_qualified.vy | input 2045, 1.29 s | [import_qualified.vy](groups/d15/import_qualified.vy) | [ImportQualified.daml](groups/d15/ImportQualified.daml) |
| d16 | 15 | Constructor ‘…’ does not have the required strict field(s): … | typecheck | contracts/import_qualified/models.vy | input 2478, 1.57 s | [models.vy](groups/d16/models.vy) | [Models.daml](groups/d16/Models.daml) |
| d17 | 2 | Tried to get field ‘…’ with type ‘…’ on value of type ‘…’, but that field has type ‘…’ | typecheck | contracts/import_sibling/import_sibling.vy | input 5812, 3.91 s | [import_sibling.vy](groups/d17/import_sibling.vy) | [ImportSibling.daml](groups/d17/ImportSibling.daml) |
| d18 | 4 | Couldn't match expected type ‘…’ with actual type ‘…’ | typecheck | contracts/import_qualified/models.vy | input 7979, 5.36 s | [models.vy](groups/d18/models.vy) | [Models.daml](groups/d18/Models.daml) |
| d19 | 1 | Tried to get field ‘…’ with type ‘…’ | typecheck | contracts/import_sibling/import_sibling.vy | input 8983, 6.01 s | [import_sibling.vy](groups/d19/import_sibling.vy) | [ImportSibling.daml](groups/d19/ImportSibling.daml) |
| d20 | 1 | No instance for (HasCreate …) | typecheck | contracts/import_sibling/import_sibling.vy | input 11663, 7.76 s | [import_sibling.vy](groups/d20/import_sibling.vy) | [ImportSibling.daml](groups/d20/ImportSibling.daml) |
| d21 | 1 | Constructor ‘…’ does not have field ‘…’ | typecheck | contracts/import_qualified/models.vy | input 14374, 9.52 s | [models.vy](groups/d21/models.vy) | [Models.daml](groups/d21/Models.daml) |

### First error lines

- d01, Models.daml line 14: `Variable not in scope: int : Decimal`
- d02, Models.daml line 6: `parse error on input ‘Party’`
- d03, Models.daml line 14: `Couldn't match expected type ‘(Text -> a0) -> Text -> Decimal’`
- d04, ImportQualified.daml line 20: `Data constructor not in scope: Decimal : M.Lot`
- d05, ImportSibling.daml line 11: `Ambiguous type variable ‘a0’ arising from a use of ‘toParties’`
- d06, ImportSibling.daml line 38: `Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘r0’`
- d07, ImportSibling.daml line 16: `No instance for (IsParties Int) arising from a use of ‘toParties’`
- d08, Models.daml line 12: `Invalid type signature: Int :: ...`
- d09, ImportSibling.daml line 30: `No instance for (HasFetch (TextMap Text))`
- d10, ImportSibling.daml line 29: `Tried to access nonexistent field ‘range’ with type ‘Int`
- d11, ImportSibling.daml line 1: `Ambiguous occurrence ‘ContractId’`
- d12, ImportQualified.daml line 19: `Couldn't match type ‘ContractId Int’ with ‘Numeric 10’`
- d13, ImportQualified.daml line 20: `Not in scope: ‘str’`
- d14, Models.daml line 20: `Multiple declarations of ‘CASH’`
- d15, ImportQualified.daml line 24: `Not in scope: data constructor ‘M.Party’`
- d16, Models.daml line 19: `Constructor ‘Lot’ does not have the required strict field(s): lot`
- d17, ImportSibling.daml line 29: `Tried to get field ‘amount’ with type ‘Party’ on value of type ‘Lot’, but that field has type ‘Decimal’`
- d18, Models.daml line 18: `Couldn't match expected type ‘Lot’ with actual type ‘()’`
- d19, ImportSibling.daml line 36: `Tried to get field ‘amount’ with type ‘ContractId`
- d20, ImportSibling.daml line 28: `No instance for (HasCreate (ContractId Note))`
- d21, Models.daml line 18: `Constructor ‘[]’ does not have field ‘amount’`

## Loop check

BAD_LOOP means that forge said OK and wrote Daml, but the loop check finds a loop bug, L1 to L4, in that Daml. The check reads forge's Daml and the .vy text, with no damlc. An input goes to the group of its first check. With --damlc, the groups are also split by whether damlc builds the Daml. A group that builds is the most serious case: damlc accepts the wrong code. Each group folder has the input, its daml.yaml when the seed has one, forge's Daml, and in shrunk/ the shrunk input and its Daml.

0 OK inputs have loop bugs.

## 0 loop groups
