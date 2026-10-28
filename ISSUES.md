# Found issues

The work on damlforge-fuzz found 35 numbered issues in DamlForge, b01 to b35.
Most of them came from fuzz runs and the analysis of their reports.
Some were found by hand, for example while the seeds were written.
An issue is a result of forge that looks wrong. The DamlForge team decides whether it is a bug.
Each numbered issue has a write-up and a proof of concept (PoC).
The PoC is a short program, written by hand, that shows the issue in code that a user can write.
The write-ups are in the analyses of the reports in [`reports/`](reports/).
The write-ups of b28 to b30 are in commit `205b074`, because DamlForge fixed these issues before the last analysis.

The analyses also contain issues with no number.
Most of them are fuzzer groups of wrong code that a user seldom writes, such as `for row for rows:`.
For such code, forge crashes (kind D), or forge accepts the code and damlc then rejects the Daml (kind E).
Nobody wrote a PoC for these groups, so they have no number.
Each group has the fuzzer input that shows the issue, in the `groups/` folder of its report.
A crash group also has a shrunk input, and a bad Daml group also has forge's Daml.
The other issues with no number are short notes in an analysis, for example a field default value that forge drops.
This file does not list the issues with no number, and gives no status for them.
These sections of the analyses list them:

- [The 2026-10-19 analysis](reports/2026-10-19T18-45-34Z/analysis.md#category-d-wrong-code-forge-crashes-instead-of-a-df-error), the groups of kinds D and E
- [The 2026-10-20 analysis](reports/2026-10-20T16-34-28Z/analysis.md#every-group-one-line-each), every group
- [The 2026-10-26 analysis](reports/2026-10-26T07-07-10Z/analysis.md#the-21-bad-daml-groups), the bad Daml groups

The status is from the DamlForge 0.0.12 and 0.0.13 releases, checked on 2026-10-28.
On that day, 0.0.13 was the latest release.
The open issues and the changed issues also gave the same results on the DamlForge `main` branch of that day.
On these releases, 23 issues are fixed, 9 are open, and 3 changed but are still wrong.
To check an issue on your own DamlForge, run `check` on its program, as [Check an issue on your DamlForge](#check-an-issue-on-your-damlforge) shows.

| Issue | Code | What forge did | Kind | Status |
| --- | --- | --- | --- | --- |
| [b01](reports/2026-10-19T18-45-34Z/analysis.md#b01-list-assignment-does-nothing) | `xs[0] = 0` on a list | The assignment does nothing. | A | Fixed in 0.0.12 |
| [b02](reports/2026-10-19T18-45-34Z/analysis.md#b02-map-assignment-does-nothing) | `votes[voter] = True` on a `GenMap` | The assignment does nothing. | A | Open |
| [b03](reports/2026-10-19T18-45-34Z/analysis.md#b03-empty-observer-list) | `observer: list[Party] = []` | damlc: ambiguous type. | B | Changed in 0.0.13 |
| [b04](reports/2026-10-19T18-45-34Z/analysis.md#b04-module-level-constant) | `limit = 10` at the top of the file | forge drops the line. damlc: `limit` is not in scope. | B | Changed in 0.0.13 |
| [b05](reports/2026-10-19T18-45-34Z/analysis.md#b05-upper-case-local-name) | An upper-case name, such as `FEE = 10` | damlc reads the name as a constructor. | B | Open |
| [b06](reports/2026-10-19T18-45-34Z/analysis.md#b06-to-b08-genmap-operations) | `voter in votes` on a `GenMap` | damlc: type error. | B | Open |
| [b07](reports/2026-10-19T18-45-34Z/analysis.md#b06-to-b08-genmap-operations) | `voter not in votes` on a `GenMap` | damlc: type error. | B | Open |
| [b08](reports/2026-10-19T18-45-34Z/analysis.md#b06-to-b08-genmap-operations) | `votes.values()` on a `GenMap` | damlc: no field `values`. | B | Fixed in 0.0.12 |
| [b09](reports/2026-10-19T18-45-34Z/analysis.md#b09-and-b10-bitwise-operators) | `a >> 1`, and also `<<`, `&`, `\|`, `^` | forge crashes with `KeyError`. | C | Fixed in 0.0.12 |
| [b10](reports/2026-10-19T18-45-34Z/analysis.md#b09-and-b10-bitwise-operators) | `~a` | forge crashes with `KeyError`. | C | Fixed in 0.0.13 |
| [b11](reports/2026-10-19T18-45-34Z/analysis.md#b11-loop-with-a-total-and-an-early-return) | A loop that adds to a total and can `return` early | forge crashes with `CompilerPanic`. | C | Fixed in 0.0.12 |
| [b12](reports/2026-10-19T18-45-34Z/analysis.md#b12-local-declaration-without-a-value) | `b: int` in a function | forge crashes with `CompilerPanic`. | C | Fixed in 0.0.12 |
| [b13](reports/2026-10-19T18-45-34Z/analysis.md#b13-import-inside-a-function) | `import math` in a function | forge crashes with `CompilerPanic`. | C | Fixed in 0.0.12 |
| [b14](reports/2026-10-19T18-45-34Z/analysis.md#b14-typo-in-the-forge-import) | `from forge.modles import ...` | forge crashes with `ModuleNotFoundError`, not a DF error. | D | Fixed in 0.0.12 |
| [b15](reports/2026-10-19T18-45-34Z/analysis.md#b15-wrong-indent-level) | A line that goes back to a wrong indent level | forge crashes with `IndentationError`, not a DF error. | D | Fixed in 0.0.12 |
| [b16](reports/2026-10-19T18-45-34Z/analysis.md#b16-unknown-name) | `return b` with no `b` | No DF error. damlc: `b` is not in scope. | E | Fixed in 0.0.13 |
| [b17](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b17-create-inside-append-loses-the-import) | `cids.append(create(...))` in a loop in a choice | forge writes `foldlA` with no import. | B | Fixed in 0.0.12 |
| [b18](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b18-fetch-inside-a-sum-loses-the-import) | `total = total + fetch(c).amount` in a loop in a choice | forge writes `foldlA` with no import. | B | Fixed in 0.0.12 |
| [b19](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b19-fetch-in-an-if-test-stays-in-a-pure-foldl) | `if fetch(c).amount > ...:` in a loop in a choice | `fetch` stays in a pure `foldl`. damlc: type error. | B | Fixed in 0.0.12 |
| [b20](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b20-a-top-level-function-gets-no-df1205-check) | `fetch(c)` in a top-level function without `@ledger_effect` | No DF1205 error. damlc: type error. | E | Fixed in 0.0.12 |
| [b21](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b21-return-in-the-loop-works-as-continue) | `return` in a loop of a choice with a ledger action or an `assert` | The `return` works as `continue`. | A | Fixed in 0.0.12 |
| [b22](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b22-return-in-an-inner-loop-removes-both-loops) | `return` in an inner loop of a function | forge writes no code for the loops. | A | Fixed in 0.0.12 |
| [b23](reports/2026-10-20T16-34-28Z/analysis/loops/README.md#b23-pass-drops-the-rest-of-its-block) | `pass` in a block | forge drops the statements after the `pass`. | A | Fixed in 0.0.12 |
| [b24](reports/2026-10-20T16-34-28Z/analysis.md#b24-a-loop-in-a-plain-function-loses-its-asserts) | A loop in a plain function whose body is not one `assert` | forge writes no code for the loop, so its asserts are lost. | A | Fixed in 0.0.12 |
| [b25](reports/2026-10-20T16-34-28Z/analysis.md#b25-a-second-signatory-observer-or-ensure-line-is-lost) | Two `signatory`, `observer`, or `ensure` lines in a template | forge keeps the first line and drops the second. | F | Fixed in 0.0.12 |
| [b26](reports/2026-10-20T16-34-28Z/analysis.md#b26-a-template-method-that-is-not-a-choice-is-lost) | A method without `@choice` in a template | forge drops the method with no error. | B, F | Changed in 0.0.12 |
| [b27](reports/2026-10-20T16-34-28Z/analysis.md#b27-an-int-literal-next-to-a-decimal) | `amount > 0` with a `Decimal` `amount` | forge writes `0`, an `Int` in Daml. damlc: type error. | B | Fixed in 0.0.12 |
| [b28](https://github.com/noders-team/damlforge-fuzz/blob/205b074/bugs/imports/README.md#b28-a-relative-import-crashes) | `from . import models` | forge crashes with `AttributeError`. | C | Fixed in 0.0.13 |
| [b29](https://github.com/noders-team/damlforge-fuzz/blob/205b074/bugs/imports/README.md#b29-an-aliased-import-of-a-missing-forge-module-crashes) | `import forge.math as m`, and an enum | forge crashes with `ModuleNotFoundError`. | C | Fixed in 0.0.13 |
| [b30](https://github.com/noders-team/damlforge-fuzz/blob/205b074/bugs/imports/README.md#b30-a-lower-case-module-alias-gives-bad-daml) | `import models as m`, then `m.double(x)` | forge writes `import qualified Models as m`. damlc: parse error. | B | Fixed in 0.0.13 |
| [b31](reports/2026-10-26T07-07-10Z/analysis.md#b31-a-qualified-enum-value-is-rejected) | `import models as M`, then `M.Kind.CASH` | forge rejects valid code with DF1213. | B | Open |
| [b32](reports/2026-10-26T07-07-10Z/analysis.md#b32-a-plain-module-import-cannot-name-a-type) | `import models`, then `models.Note` as a type | forge rejects valid code with DF1213. | B | Open |
| [b33](reports/2026-10-26T07-07-10Z/analysis.md#b33-a-plain-module-import-gives-bad-daml-for-a-call) | `import models`, then `models.double(x)` | forge writes `models.double x`. damlc: `models` is not in scope. | B | Open |
| [b34](reports/2026-10-26T07-07-10Z/analysis.md#b34-a-value-set-in-a-loop-and-used-after-it) | `note = fetch(cid)` in a loop, then `note.lot.amount` after it | forge writes `fromSome x.lot`. damlc: no such field. | B | Open |
| [b35](reports/2026-10-26T07-07-10Z/analysis.md#b35-a-template-with-the-name-of-an-enum-value) | `class Kind(Enum): CASH`, and `@template class CASH` | damlc: two declarations of `CASH`. | B | Open |

The three changed issues:

- b03: forge now rejects the valid empty observer list, with DF1201.
- b04: forge now gives DF1219, which says that `limit` is not defined. But the top of the file defines `limit`.
- b26: forge now rejects a template method that is not a choice, with DF1233. For a helper method, DamlForge must decide whether that is a fix.

The kinds of issues:

- **A.** Valid code. forge writes Daml that builds, but gives a wrong result. This is the most serious kind.
- **B.** Valid code. forge writes Daml that damlc rejects, or forge rejects the code.
- **C.** Valid code. forge crashes.
- **D.** Wrong code. forge crashes, and gives no DF error.
- **E.** Wrong code that forge accepts. damlc then rejects the Daml.
- **F.** Wrong code with one name declared two times. forge keeps one declaration and gives no error.

## Check an issue on your DamlForge

To see if an issue is in your DamlForge, run `check` on its program.
Install damlforge-fuzz first, as [the README](README.md#install) shows.
For example, this is the result for b33 when the issue is there:

```
$ damlforge-fuzz check reports/2026-10-26T07-07-10Z/analysis/imports/b33_plain_module_import_call.vy
BAD_IMP  emit   reports/2026-10-26T07-07-10Z/analysis/imports/b33_plain_module_import_call.vy  I1: models. at Daml line 7 with no import that binds models
```

When the issue is there, the line starts with `BAD_IMP`.
Another result means that forge changed.
The write-up of the issue tells what the right result is.
Some issues show only with `--damlc` or `--compare`, as their write-ups say.
