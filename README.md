# damlforge-fuzz

A mutation fuzzer for `forge`, the DamlForge compiler that compiles `.vy` contracts to Daml.

damlforge-fuzz takes a few seed contracts and makes small random edits to them.
It compiles each edited copy with `forge`, groups the crashes, shrinks each crashing input to a few lines, and writes a report.
It also checks the loops in the Daml that `forge` writes, and reports the loops that `forge` translated wrongly.
With `--damlc`, it also builds the Daml that `forge` writes, and reports the Daml that the Daml compiler rejects.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Reports](#reports)
- [Change rules](#change-rules)
- [Seeds](#seeds)
- [Development](#development)

## Features

- **Repeatable runs.** One random seed fixes every copy and its changes. The same random seed always gives the same copies in the same order.
- **Text change rules.** Ten rules each change one line: they delete it, copy it, insert a line above it, or replace or delete one word. Six loop rules make the code shapes that break forge's loops, such as a `fetch` inside an expression or a `return` inside a loop.
- **Crash groups.** Crashes with the same exception at the same forge file and line are one group.
- **Shrinking.** The run cuts the first input of each crash group and each loop group down to the lines that cause the crash or the loop bug.
- **Daml checks.** With `--damlc`, the run builds the Daml that `forge` writes with `damlc`, and groups the Daml that `damlc` rejects.
- **Loop check.** For each `OK` input, the run checks the loops in the Daml that `forge` writes for four kinds of wrong translation, and groups the inputs with a loop bug. It does not need `damlc`.
- **Reports** in JSON and Markdown, with one folder for each group. You can compile each saved input again.

## Requirements

| Requirement | Version | Needed for |
| --- | --- | --- |
| Python | 3.11 or newer | All commands |
| DamlForge (`forge`) | Tested with `0.0.7` and `0.0.11` | All commands |
| dpm and the Daml SDK | SDK 3.5.2 | Only `--damlc` and the second [seed check](#check-the-seeds) |

## Install

### Create a virtual environment

```sh
python3 -m venv .venv
. .venv/bin/activate
```

### Install DamlForge

> [!WARNING]
> Do not run `pip install forge`.
> The `forge` package on PyPI is a different project, a Django tool.

The DamlForge repository, `noders-team/damlforge`, is private.
For the release wheel and the git install, you need GitHub access to that repository.
Use one of these three methods:

- Install the release wheel. The latest release is `v0.0.7`.

  ```sh
  gh release download v0.0.7 --repo noders-team/damlforge --pattern '*.whl'
  pip install forge-0.0.7-py3-none-any.whl
  ```

- Install from git:

  ```sh
  pip install "forge @ git+https://github.com/noders-team/damlforge.git@v0.0.7"
  ```

- Install a local DamlForge checkout that you change. Your changes apply without a reinstall.

  ```sh
  pip install -e /path/to/damlforge
  ```

To check the install, run `forge --help`.
The output lists the `daml`, `dar`, `json`, and `stubs` commands.

### Install damlforge-fuzz

Install the fuzzer into the virtual environment that has DamlForge.
Run this command from the root of this repository:

```sh
pip install -e ".[test]"
```

The `test` extra also installs pytest.

### Install dpm and the Daml SDK

This step is optional.
You need dpm and the Daml SDK only for `--damlc` and for the second [seed check](#check-the-seeds).

dpm is the Daml package manager.
It installs the Daml SDK, which has the `damlc` compiler.
Install the SDK version that the seeds' `daml.yaml` files use, 3.5.2:

```sh
curl -sSL https://get.digitalasset.com/install | sh
dpm install 3.5.2
```

If your shell does not find `dpm` after the install, add `~/.dpm/bin` to your `PATH`.
`forge dar` looks for `dpm` on your `PATH` and then in `~/.dpm/bin`.
These commands are the same as in `.devcontainer/post-create.sh` in the DamlForge repository.

## Quick start

> [!NOTE]
> All example output in this README is real output from DamlForge 0.0.11, the commit after the `v0.0.10` tag.
> Another forge version gives other counts and other forge line numbers.

Run these commands from the root of this repository.

1. Compile the seeds. Every seed must be `OK`.

   ```
   $ damlforge-fuzz check contracts
   OK       emit   contracts/asset_proposal/asset_proposal.vy
   OK       emit   contracts/ballot/ballot.vy
   OK       emit   contracts/escrow/escrow.vy
   OK       emit   contracts/iou/iou.vy
   OK       emit   contracts/loop_count/loop_count.vy
   OK       emit   contracts/loop_give/loop_give.vy
   OK       emit   contracts/loop_many/loop_many.vy
   OK       emit   contracts/loop_pure/loop_pure.vy
   OK       emit   contracts/loop_verify/loop_verify.vy
   ```

2. Fuzz the seeds for 60 seconds:

   ```
   $ damlforge-fuzz run --seconds 60
   random seed 813550, 9 seeds, 60 seconds
   random seed 813550: 82103 inputs, 17467 OK, 42691 rejected, 5420 crash, 16525 skipped
   loops: 658 inputs with loop findings, 4 loop groups
   14 crash groups, report in reports/2026-10-20T11-46-49Z
   ```

3. Open `report.md` in the report folder.
   It has one table row for each group, and the shrunk input of each crash group and each loop group.

4. Compile a saved crash input again.
   This example uses the report that is in the repository:

   ```
   $ damlforge-fuzz check reports/2026-10-19T18-45-34Z/groups/g01/iou.vy
   CRASH    lower  reports/2026-10-19T18-45-34Z/groups/g01/iou.vy  CompilerPanic lower_stmt: unsupported statement node Import at forge/ir/lower.py:314
   ```

## Usage

```
damlforge-fuzz check [--damlc] PATH [PATH ...]
damlforge-fuzz run [SEED_FOLDER ...] (--seconds N | --count N) [--random-seed S] [--reports DIR] [--damlc]
damlforge-fuzz shrink [--damlc] FILE
```

| Command | What it does |
| --- | --- |
| `check` | Compiles `.vy` files with `forge` and prints one result for each file. |
| `run` | Makes changed copies of the seeds, compiles each copy with `forge`, and writes a report. |
| `shrink` | Deletes lines of a `.vy` file while it still crashes in the same way, or still has the same loop bug. |

### `damlforge-fuzz check`

`check` compiles each `.vy` file with `forge` and prints one line for each file.

| Argument | Meaning |
| --- | --- |
| `PATH` | A `.vy` file, or a folder. For a folder, `check` uses every `.vy` file under it. |
| `--damlc` | Also build the Daml of the `OK` files with `damlc`. See [Check the Daml with damlc](#check-the-daml-with-damlc). |

For example, `bitand.vy` has these two lines:

```python
def f(count: int) -> int:
    return count & 1
```

```
$ damlforge-fuzz check bitand.vy
CRASH    lower  bitand.vy  KeyError 'BitAnd' at forge/ir/lower.py:289
```

forge has no entry for `&` in its table of operators.
In DamlForge `v0.0.7`, the same crash is at `forge/ir/lower.py:244`.

Each line has the [result](#results), the [stage](#stages), and the file.
A `REJECTED`, `CRASH`, `BAD_DAML`, or `BAD_LOOP` line ends with the error.

### `damlforge-fuzz run`

`run` makes changed copies of the seeds and compiles each copy with `forge`.
Each copy starts from one seed and gets 1 to 4 random changes.
[Change rules](#change-rules) lists the changes.

| Argument | Meaning |
| --- | --- |
| `SEED_FOLDER` | A seed folder or a `.vy` file. Without it, the run uses every seed in `contracts/`. |
| `--seconds N` | Run for N seconds. Give `--seconds` or `--count`, not both. |
| `--count N` | Make N copies. |
| `--random-seed S` | The number that decides every copy and its changes. Without it, the run picks a new number and prints it. |
| `--reports DIR` | The folder for the report folders. The default is `reports`. |
| `--damlc` | Also build the Daml of the `OK` copies with `damlc`. See [Check the Daml with damlc](#check-the-daml-with-damlc). |

```
$ damlforge-fuzz run contracts/iou --count 2000 --random-seed 1
random seed 1, 1 seed, 2000 inputs
random seed 1: 2000 inputs, 419 OK, 1135 rejected, 63 crash, 383 skipped
loops: 11 inputs with loop findings, 2 loop groups
7 crash groups, report in reports/2026-10-20T11-45-50Z
```

The first line prints when the run starts.
The second line prints when the run has made all the copies:

- `inputs`: the number of copies that the run made, including the skipped copies.
- `skipped`: copies whose changes left the text as it was. The run does not compile them.
- `OK`, `rejected`, and `crash`: the same [results](#results) as for `check`.

The third line gives the number of `OK` copies with a loop bug, and the number of loop groups.
[Loop check](#loop-check) tells what a loop bug is.
The last line gives the number of crash groups and the [report](#reports) folder.

A run has these steps:

1. Compile the unchanged seeds, and run the loop check on them. With `--damlc`, also build their Daml.
2. Make the copies, and compile each copy with `forge`.
3. With `--damlc`, build the Daml of the `OK` copies.
4. Shrink the first input of each crash group and each loop group.
5. Write the report.

#### Repeat a run

The same random seed and the same seed folders always give the same copies in the same order.
To repeat a run exactly, give its random seed and its number of inputs.
For example, this command repeats the 60-second run in [Quick start](#quick-start):

```sh
damlforge-fuzz run --count 82103 --random-seed 813550
```

Do not use `--seconds` to repeat a run.
The number of copies in a time limit changes with the speed of the machine.

`report.json` records the seeds of a run in `run.seeds`.
A run without `SEED_FOLDER` uses every seed in `contracts/`, so a new seed in `contracts/` changes the copies of such a run.
To repeat a run from before a seed was added, name the seeds of that run.
A change to the [change rules](#change-rules) also changes the copies.
To repeat a run from before such a change, use a commit from before it.
For example, the report in `reports/2026-10-19T18-45-34Z` comes from a run with the ten rules from before the loop rules, on the four seeds that `contracts/` had before the loop seeds.
At commit `e99695a`, this command makes the same copies:

```sh
damlforge-fuzz run contracts/asset_proposal contracts/ballot contracts/escrow contracts/iou --damlc --count 20000 --random-seed 1
```

### `damlforge-fuzz shrink`

`shrink` deletes lines of a `.vy` file that crashes forge or that is `BAD_LOOP`.
It writes the result to `shrunk/` next to FILE, with the same file name, and prints it.

| Argument | Meaning |
| --- | --- |
| `FILE` | A `.vy` file that crashes forge, or that has a loop bug. |
| `--damlc` | For a `BAD_LOOP` file, also keep the verdict of `damlc` on the Daml. |

For a file that crashes forge, `shrink` keeps a deletion only when the file still crashes with the same exception at the same forge line:

```
$ damlforge-fuzz shrink reports/2026-10-19T18-45-34Z/groups/g02/escrow.vy
shrunk reports/2026-10-19T18-45-34Z/groups/g02/escrow.vy from 42 to 3 lines: reports/2026-10-19T18-45-34Z/groups/g02/shrunk/escrow.vy
@template
class Escrow:
    tuple[int, str]: EscrowTerms
```

For a `BAD_LOOP` file, `shrink` keeps a deletion only when forge still writes Daml and the first check of the [loop check](#loop-check) is the same.
This example uses the loop group `l01` of the run without `--damlc` in [Loop check](#loop-check):

```
$ damlforge-fuzz shrink reports/2026-10-20T12-41-34Z/groups/l01/loop_pure.vy
shrunk reports/2026-10-20T12-41-34Z/groups/l01/loop_pure.vy from 40 to 4 lines: reports/2026-10-20T12-41-34Z/groups/l01/shrunk/loop_pure.vy
def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
            for _k in range(0, 2):
                return True
```

forge loses the `return` in the inner loop, so the first check is `L3`.
`damlc` builds the Daml of the full input, but not the Daml of the shrunk input.
The shrinker deleted the `return False` after the loop, and forge then writes `()` as the result of `has_party`:

```
$ damlforge-fuzz check --damlc reports/2026-10-20T12-41-34Z/groups/l01/shrunk/loop_pure.vy
BAD_LOOP emit   reports/2026-10-20T12-41-34Z/groups/l01/shrunk/loop_pure.vy  L3: the return in a loop of function has_party at Daml line 3 is lost (2 loops with a return, 0 early-return helpers); damlc rejects: Couldn't match expected type ‘Bool’ with actual type ‘()’
```

With `--damlc`, `shrink` first builds the Daml of FILE with `damlc`.
Then it keeps a deletion only when `damlc` also gives the same verdict, `builds` or `rejects`.
So the shrunk input keeps `return False`, and its Daml builds.
This example uses the same group in the report of the `--damlc` run:

```
$ damlforge-fuzz shrink --damlc reports/2026-10-20T12-41-38Z/groups/l01/loop_pure.vy
shrunk reports/2026-10-20T12-41-38Z/groups/l01/loop_pure.vy from 40 to 5 lines: reports/2026-10-20T12-41-38Z/groups/l01/shrunk/loop_pure.vy
def has_party(ps: list[Party], p: Party) -> bool:
    for q in ps:
            for _k in range(0, 2):
                return True
    return False
```

With `--damlc`, `shrink` needs dpm, the Daml SDK, and a `daml.yaml` for FILE.
Each try that keeps the first check needs a `dpm build` of its Daml, about 0.7 seconds, so this command took about 11 seconds.
For a file that crashes forge, `--damlc` changes nothing.

`run` already shrinks the first input of each crash group and each loop group.
Use `shrink` for other files.
[Shrunk inputs](#shrunk-inputs) tells how the shrinker works.

### Check the Daml with damlc

forge says `OK` when it writes Daml, but the Daml can still be wrong.
With `--damlc`, `run` and `check` also build the Daml of the `OK` inputs with `damlc`.
`BAD_DAML` means that forge wrote Daml, but `damlc` rejects that Daml.
That is a bug in forge: its check stage let through a program that it then translated to wrong Daml.

`--damlc` needs dpm and the Daml SDK. [Install dpm and the Daml SDK](#install-dpm-and-the-daml-sdk) shows how to install them.

```
$ damlforge-fuzz run --damlc --count 2000 --random-seed 1
random seed 1, 9 seeds, 2000 inputs
random seed 1: 2000 inputs, 432 OK, 1017 rejected, 133 crash, 418 skipped
damlc: 231 Daml texts, 172 bad, 22 bad Daml groups
loops: 12 inputs with loop findings, 4 loop groups, 1 builds with damlc
9 crash groups, report in reports/2026-10-20T11-45-56Z
```

The `damlc:` line comes before the `loops:` line:

- `Daml texts`: the number of different Daml texts among the `OK` copies. Many copies give the same Daml, so the run builds each text only once.
- `bad`: the texts that `damlc` rejects.
- `bad Daml groups`: the number of groups of bad texts. Texts whose first `damlc` error is the same, after the names in the error are hidden, are one group.
  For example, `Variable not in scope: str : Int -> t` and `Variable not in scope: x : [a0]` are one group.
  So a group is one kind of `damlc` error, and it can hold more than one forge bug.

With `--damlc`, the `loops:` line also gives the number of loop groups whose Daml `damlc` builds.
[Loop check](#loop-check) tells more.

With `check --damlc`, a file whose Daml `damlc` rejects is `BAD_DAML`.
The line ends with the first line of the first `damlc` error:

```
$ damlforge-fuzz check --damlc reports/2026-10-19T18-45-34Z/groups/d02/iou.vy
BAD_DAML emit   reports/2026-10-19T18-45-34Z/groups/d02/iou.vy  Variable not in scope: x : [a0]
```

How a run uses `damlc`:

- Before the first copy, the run builds the Daml of the unchanged seeds.
  If dpm or the SDK is missing, or the Daml of a seed does not build, the run prints one line to stderr and exits with 2.
- After the last copy, the run puts up to 500 Daml texts into one temporary Daml project, and runs one `dpm build` for them.
  A build of 500 texts takes about 5 seconds, so a 60-second run takes about 40 seconds more.
  The temporary projects are in your system's temporary folder, and the run deletes them.
- The run does not shrink the bad Daml inputs, because each try needs its own `dpm build`, which takes about 0.7 seconds.
- The run shrinks the loop groups so that each shrunk input keeps the verdict of `damlc`.
  This needs a `dpm build` for each new Daml text of a try, so each loop group takes about 3 to 10 seconds. [Shrunk inputs](#shrunk-inputs) tells more.

### Loop check

forge writes a `for` loop in one of four ways.
A loop with no ledger action becomes `foldl`, and a loop with a ledger action, such as `create` or `fetch`, becomes `foldlA`.
A loop with only an `assert` becomes `all`, and a loop with an early `return` becomes a recursive helper function, `_damlforge_loopN`.
The loop check reads the Daml that forge writes and the `.vy` text, and finds four kinds of wrong loops.
It runs on each `OK` input of `check` and `run`, and it does not need `damlc`.

| Check | What it finds |
| --- | --- |
| `L1` | forge writes `foldlA`, the fold for a loop with a ledger action, but does not import it from `DA.Action`. damlc rejects the Daml. |
| `L2` | forge writes the pure fold `foldl` for a loop whose body has a ledger action, such as `fetch` or `create`. A ledger action needs `foldlA` in an `Update`. |
| `L3` | A `return` in a loop of the .vy code has no early-return helper (`_damlforge_loopN`) in the Daml, so the return is lost: the loop goes on, or the function returns another value. damlc can build this Daml. |
| `L4` | A ledger action, in a loop or not, is used as a value: it is not bound with `<-` and is not a statement of a `do` block, so the code gets an `Update`, not its result. |

An input that fails a check is `BAD_LOOP`.
`check` prints every check that the file fails, and the first bug.
The six programs in [`bugs/loops/`](bugs/loops/) each show a forge loop bug:

```
$ damlforge-fuzz check bugs/loops
BAD_LOOP emit   bugs/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   bugs/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   bugs/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20
BAD_LOOP emit   bugs/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7
BAD_LOOP emit   bugs/loops/b21_return_in_create_loop.vy  L3: the return in a loop of choice GiveUntil at Daml line 14 is lost (1 loop with a return, 0 early-return helpers)
BAD_LOOP emit   bugs/loops/b22_return_in_inner_loop.vy  L3: the return in a loop of function first_positive at Daml line 3 is lost (2 loops with a return, 0 early-return helpers)
```

With `--damlc`, each `BAD_LOOP` line ends with the verdict of `damlc`.
A file with a loop bug is `BAD_LOOP`, not `BAD_DAML`, because the loop bug tells the cause.
The `damlc` error is usually a result of that cause, such as `Variable not in scope: foldlA` for `L1`.
`damlc builds` is the most serious case: forge wrote wrong Daml that compiles.

```
$ damlforge-fuzz check --damlc bugs/loops
BAD_LOOP emit   bugs/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action; damlc rejects: Variable not in scope: foldlA
BAD_LOOP emit   bugs/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action; damlc rejects: Variable not in scope: foldlA
BAD_LOOP emit   bugs/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20; damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_LOOP emit   bugs/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7; damlc rejects: Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update
BAD_LOOP emit   bugs/loops/b21_return_in_create_loop.vy  L3: the return in a loop of choice GiveUntil at Daml line 14 is lost (1 loop with a return, 0 early-return helpers); damlc builds
BAD_LOOP emit   bugs/loops/b22_return_in_inner_loop.vy  L3: the return in a loop of function first_positive at Daml line 3 is lost (2 loops with a return, 0 early-return helpers); damlc builds
```

How a run uses the loop check:

- Before the first copy, the run compiles the unchanged seeds and runs the loop check on them.
  A seed with a loop bug stops the run with exit code 2, because almost every copy would have the same bug:

  ```
  $ damlforge-fuzz run bugs/loops/b17_create_append.vy --count 10
  damlforge-fuzz run: the loop check finds a bug in seed bugs/loops/b17_create_append.vy: L1: foldlA at Daml line 20 with no import DA.Action
  ```

- After the last copy, the run groups the `OK` copies with a loop bug.
  A copy goes to the group of its first check, so a run without `--damlc` has at most four loop groups.
  The `loops:` line comes before the last line:

  ```
  $ damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1
  random seed 1, 5 seeds, 5000 inputs
  random seed 1: 5000 inputs, 972 OK, 2582 rejected, 413 crash, 1033 skipped
  loops: 49 inputs with loop findings, 4 loop groups
  10 crash groups, report in reports/2026-10-20T12-41-34Z
  ```

- With `--damlc`, the run also splits the loop groups by the verdict of `damlc`.
  So a group whose Daml builds does not hide behind an earlier input whose Daml `damlc` rejects.
  The `loops:` line also gives the number of groups that build:

  ```
  $ damlforge-fuzz run contracts/loop_* --damlc --count 5000 --random-seed 1
  random seed 1, 5 seeds, 5000 inputs
  random seed 1: 5000 inputs, 972 OK, 2582 rejected, 413 crash, 1033 skipped
  damlc: 405 Daml texts, 315 bad, 22 bad Daml groups
  loops: 49 inputs with loop findings, 5 loop groups, 1 builds with damlc
  10 crash groups, report in reports/2026-10-20T12-41-38Z
  ```

  Here the `L3` inputs make two groups: `l01`, whose Daml `damlc` builds, and `l05`, whose Daml `damlc` rejects.

- After the crash groups, the run shrinks the first input of each loop group.
  [Shrunk inputs](#shrunk-inputs) tells how.

The loop check has these limits:

- It reads the Daml in the layout that forge writes: one statement on each line, and `do` at the end of the line that opens a block.
  If forge changes its layout, the check can give wrong results.
  The tests in `tests/test_loopcheck.py` compare the Daml that forge writes with saved Daml, so they show such a change first.
- `L3` does not know whether the lost `return` changes the result. A lost `return` before code that does nothing is harmless.

### Results

The first column of a `check` line is the result:

| Result | Meaning |
| --- | --- |
| `OK` | forge wrote Daml. |
| `REJECTED` | forge reported an error in the input, such as `DF1213`. |
| `CRASH` | forge failed with an error that is not its own. This is a bug in forge. The line ends with the exception and the forge file and line where it failed. |
| `BAD_DAML` | Only with `--damlc`. forge wrote Daml, but `damlc` rejects it. This is also a bug in forge. |
| `BAD_LOOP` | forge wrote Daml, but the [loop check](#loop-check) finds a wrong loop in it. This is also a bug in forge. With `--damlc`, the line ends with the verdict of `damlc`. |

### Stages

The second column is the forge step that was running, the stage.
forge runs four stages, in this order:

| Stage | What forge does |
| --- | --- |
| `parse` | forge reads the `.vy` text and makes a syntax tree (`forge.ast.parse_to_ast`). A crash here means forge failed while it read the code. |
| `check` | forge checks names, types, imports, and the rules for templates and choices (`forge.semantics.analyze_module`). Wrong code must stop here with a DF error. |
| `lower` | forge changes the checked program into its internal form, IR (`forge.ir.lower_module`). A crash here usually means that check let through code that forge cannot translate. |
| `emit` | forge writes the Daml code from the IR (`forge.codegen.generate_daml`). |

The stage is the step that was running, not the folder of the forge file.
So a crash can have stage `check` and a line in `forge/ir/lower.py`.

### Exit codes

| Code | `check` | `run` | `shrink` |
| --- | --- | --- | --- |
| `0` | Every file is `OK`. | No copy crashed, no Daml text is bad, and the report has no loop group. | The command wrote the shrunk file. |
| `1` | A file is `REJECTED`, `CRASH`, `BAD_DAML`, or `BAD_LOOP`. | A copy crashed, a Daml text is bad, or the report has a loop group. | FILE does not crash forge and has no loop bug. The command writes nothing. |
| `2` | Usage error. | Usage error. | Usage error. |
| `130` | — | You pressed Ctrl-C. See [Stop a run with Ctrl-C](#stop-a-run-with-ctrl-c). | You pressed Ctrl-C. The command writes nothing. |

A usage error prints one line to stderr.
These are the usage errors:

- For all commands: a missing path, a folder with no `.vy` file, a file that cannot be read, or DamlForge is not installed.
- With `--damlc`: a file with no `daml.yaml`, dpm or its SDK is missing, or dpm fails.
- For `run`: a `--reports` folder that cannot be made, a report that cannot be written, or a seed with a loop bug.
- For `shrink`: a FILE that is a folder, or a FILE that is already in a `shrunk/` folder.

## Reports

Every run writes a report folder in `reports/`.
The folder name is the UTC time when the run started, such as `reports/2026-10-20T07-52-29Z`.
If a folder with that name exists, the run adds `-2`, `-3`, and so on.
To put the report folders in a different folder, give `--reports DIR`.

Git does not ignore `reports/`.
Commit the reports that you want to keep, and delete the others.
The reports in git are in [`reports/`](reports/).

### Report files

A report folder has these files.
The example is the report in the repository.
Its `analysis.md` file and its `analysis/` folder are not part of the report: they were written by hand.

```
reports/2026-10-19T18-45-34Z/
├── report.json
├── report.md
└── groups/
    ├── g01/               crash group 1
    │   ├── iou.vy         the first input that crashed
    │   ├── daml.yaml      a copy of the seed's daml.yaml
    │   └── shrunk/
    │       └── iou.vy     the shrunk input
    ├── ...
    ├── d01/               bad Daml group 1 (only with --damlc)
    │   ├── ballot.vy      the first input with this damlc error
    │   ├── daml.yaml      a copy of the seed's daml.yaml
    │   └── Ballot.daml    the Daml that forge wrote for the input
    └── ...
```

- `report.json` is the full report. It has the run settings, the counts, the counts after each second of the run, and one entry for each group.
  A crash group entry has the exception, the forge file and line, the stage, the number of crashes, the first input that crashed, and the full text of that input.
  It also has the shrunk text in `"shrunk"` and the shrunk file in `"shrunk_file"`.
  The `damlc` entry has the counts and the time that `damlc` took. Without `--damlc`, `damlc` is `null`.
  A loop group entry has the first check of the group (`check`), every check of its first input (`checks`), the first bug (`message` and `daml_line`), the number of inputs, the first input, and the Daml that forge wrote for it.
  With `--damlc`, `damlc` is `builds` or `rejects`, and `damlc_error` is the first `damlc` error when `damlc` rejects the Daml. Without `--damlc`, both are `null`.
  A loop group entry also has the shrunk text in `"shrunk"` and its file in `"shrunk_file"`, and the Daml that forge wrote for the shrunk text in `"shrunk_daml"` and `"shrunk_daml_file"`.
- `report.md` is a short summary of `report.json`.
  It has one table row for each group, with a `Shrunk` column, such as `3 of 42 lines`, and a code block with each shrunk input.
  It also tells what the stages of the groups mean.
  With `--damlc`, it has a `Bad Daml` section with a table of the groups and the first error line of each group.
  It has a `Loop check` section, with the checks of the loop groups, a table of the groups with a `Shrunk` column, the first bug of each group, and a code block with each shrunk input and its Daml.
- `groups/g01/`, `groups/g02/`, and so on are the crash groups, in the order that the run found them.
- `groups/d01/`, `groups/d02/`, and so on are the bad Daml groups, in the order that the run found them.
- `groups/l01/`, `groups/l02/`, and so on are the loop groups, in the order that the run found them.

The report in the repository is from before the loop check, so it has no loop group.
A loop group folder has the first input, a copy of the seed's `daml.yaml` when the seed has one, and the Daml that forge wrote for the input.
Its `shrunk/` folder has the shrunk input and the Daml that forge wrote for it.
For example, `damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1` writes this folder:

```
groups/l01/
├── loop_pure.vy       the first input whose first check is L3
├── daml.yaml          a copy of the seed's daml.yaml
├── LoopPure.daml      the Daml that forge wrote for the input
└── shrunk/
    ├── loop_pure.vy   the shrunk input
    └── LoopPure.daml  the Daml that forge wrote for the shrunk input
```

### See a group again

To see a crash again, run `check` on the input in the group folder.
A folder argument also checks the shrunk input:

```
$ damlforge-fuzz check reports/2026-10-19T18-45-34Z/groups/g02
CRASH    check  reports/2026-10-19T18-45-34Z/groups/g02/escrow.vy  AttributeError 'Subscript' object has no attribute 'id' at forge/semantics/analysis/types.py:644
CRASH    check  reports/2026-10-19T18-45-34Z/groups/g02/shrunk/escrow.vy  AttributeError 'Subscript' object has no attribute 'id' at forge/semantics/analysis/types.py:644
```

To see a `damlc` error again without the fuzzer, run `dpm build` in the bad Daml group folder.

To see a loop bug again, run `check` on the input in the loop group folder.
With `--damlc`, the line also gives the verdict of `damlc`.
A folder argument also checks the shrunk input.
This example uses the report of the `--damlc` run in [Loop check](#loop-check):

```
$ damlforge-fuzz check --damlc reports/2026-10-20T12-41-38Z/groups/l01
BAD_LOOP emit   reports/2026-10-20T12-41-38Z/groups/l01/loop_pure.vy  L3: the return in a loop of function has_party at Daml line 37 is lost (2 loops with a return, 0 early-return helpers); damlc builds
BAD_LOOP emit   reports/2026-10-20T12-41-38Z/groups/l01/shrunk/loop_pure.vy  L3: the return in a loop of function has_party at Daml line 3 is lost (2 loops with a return, 0 early-return helpers); damlc builds
```

### Shrunk inputs

The seeds have 18 to 41 lines, and a crashing input has about as many as its seed.
Usually only a few of these lines cause the crash.
After the last copy, the run shrinks the first input of each crash group:

1. The shrinker deletes lines, first in large blocks, then one line or one indented block at a time.
2. It keeps a deletion only when the text still crashes with the same exception at the same forge line.
3. It stops when it cannot delete one more line.

The shrunk input has only lines of the full input, in the same order, and no line is changed.
For the 9 crash groups of the 2000-copy run in [Check the Daml with damlc](#check-the-daml-with-damlc), shrinking took about 0.06 seconds.
The inputs of these groups have 19 to 42 lines, and the shrunk inputs have 1 to 8 lines.

Then the run shrinks the first input of each loop group in the same way.
It keeps a deletion only when forge still writes Daml and the first check of the [loop check](#loop-check) is the same.
With `--damlc`, it also keeps a deletion only when `damlc` gives the same verdict on the Daml, `builds` or `rejects`.
Without that, a group whose Daml builds can get a shrunk input whose Daml `damlc` rejects.
[`damlforge-fuzz shrink`](#damlforge-fuzz-shrink) shows an example.

For `damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1`, with and without `--damlc`:

| Run | Loop groups | Lines of the inputs | Lines of the shrunk inputs | Time to shrink the loop groups |
| --- | --- | --- | --- | --- |
| Without `--damlc` | 4 | 19 to 40 | 4 to 10 | 0.13 seconds |
| With `--damlc` | 5 | 19 to 43 | 5 to 13 | 30 seconds |

With `--damlc`, each try that keeps the first check needs a `dpm build` of its Daml, about 0.7 seconds, unless an earlier try had the same Daml.
The 5 loop groups needed 43 builds, 5 to 13 for each group.
So this run took 37 seconds, and 30 of them were for the loop groups.

For a group whose Daml `damlc` rejects, the shrunk input keeps the verdict, but not the error.
`damlc` can reject the shrunk Daml for another reason.
For example, in the `L4` group `l02` of that run, `damlc` rejects the Daml of the full input with `Tried to access nonexistent field ‘amount’ with type ‘Decimal’ on value of type ‘Update`.
It rejects the Daml of the shrunk input with `Variable not in scope: issuer`, because the shrinker deleted the field `issuer`.

The shrunk input is in `shrunk/` in the group folder, with the same file name as the full input.
The same file name keeps the Daml module name.
The shrunk file uses the `daml.yaml` of the group folder.
The `shrunk/` folder of a loop group also has the Daml that forge wrote for the shrunk input.

### Stop a run with Ctrl-C

When you press Ctrl-C, the run stops the step that is running and continues with the next steps.
In each of these cases, the run writes the report and exits with 130:

| When you press Ctrl-C | What the run does |
| --- | --- |
| While it makes copies | Stops the copies. With `--damlc`, it still builds the Daml. It still shrinks. `report.json` has `"interrupted": true`. |
| While `damlc` builds | Keeps the texts that it built, and stops the `damlc` step. It still shrinks. The `damlc` entry in `report.json` has `"interrupted": true`. A loop group whose Daml `damlc` did not build has `"damlc": null`, and `report.md` shows `not built`. |
| While it shrinks | Stops the shrinking. The groups that are not shrunk yet have `"shrunk": null`, and `report.md` shows `not shrunk`. A loop group that is not shrunk yet also has `"shrunk_daml": null`. |

## Change rules

For each change, the run picks one line and one of these rules, each with the same chance.
A word is a name, a number, or an operator.
A rule that does not fit its line, such as `operator` on a line with no operator, leaves the line as it was.
The first ten examples are real changes to `contracts/iou/iou.vy`, and the last six are real changes to the loop seeds.

| Rule | What it does | Example |
| --- | --- | --- |
| `delete_line` | Deletes the line. | `        return create(` is deleted |
| `copy_line` | Inserts a copy of the line above it. | the `from forge.models import ...` line is there two times |
| `donor_line` | Inserts a line from one of the run's seeds above it. The line keeps its own indent. | `        now = datetime.now()` is inserted |
| `insert_statement` | Inserts a statement at the line's indent, above it. | `    x += 1` is inserted |
| `literal` | Replaces one word with a literal. | `amount > Decimal(0)` becomes `amount False Decimal(0)` |
| `operator` | Replaces one operator with another operator. | `split_amount > Decimal(0)` becomes `split_amount + Decimal(0)` |
| `type` | Replaces one name with a type. | `issuer: Party` becomes `Optional[int]: Party` |
| `expression` | Replaces one name with an expression. | `> Decimal(0)` becomes `> len(x)(0)` |
| `name` | Replaces one name with another name from the same text. | `owner=self.owner` becomes `str=self.owner` |
| `delete_word` | Deletes one word. | `self, new_owner: Party` becomes `self, : Party` |
| `inline_local` | Replaces one use of a local name with the value that an assignment in the text gives it. The value gets parentheses unless it is a name or a call. | `if i.amount > Decimal(1):` becomes `if fetch(c).amount > Decimal(1):` |
| `toggle_ledger_effect` | Deletes a line `@ledger_effect`, or inserts one above a `def` at column 0. | the `@ledger_effect` line above `def verify` is deleted |
| `early_return` | In a loop body, inserts `if v == v:` and the `return` line that follows the loop, above the line. `v` is the loop's name. It looks out through `if` and `else` blocks and inner loops for the nearest loop that a `return` follows. | `if c == c:` and `return n` are inserted above `n = n + 1` |
| `wrap_in_loop` | Puts a statement that has an indent into `for _k in range(0, 2):`. | `return cids` becomes `for _k in range(0, 2):` and `    return cids` |
| `dedent_line` | Moves a line with an indent of 8 or more 4 spaces to the left. | `cid = create(...)` moves out of the `if` |
| `inline_var` | On `v = value`, puts the value in place of each use of `v` below it in the same block, and deletes the line. It does not fit when `v` gets a new value in that block. | `cid = create(Iou(...))` is deleted, and `cids.append(cid)` becomes `cids.append(create(Iou(...)))` |

The rules take their new words from five lists in `src/damlforge_fuzz/mutate.py`: `_OPERATORS`, `_LITERALS`, `_TYPES`, `_EXPRESSIONS`, and `_STATEMENTS`.
Most rules change only their own line.
`inline_local` and `early_return` read the whole text, and `inline_var` also changes the lines below its line.
The six loop rules never take a string or a comment for code.

### Add a word or a rule

> [!IMPORTANT]
> Every change to the rules or the word lists changes some copies of every random seed.
> So a result from before the change and a result from after it do not use the same copies.
> Record the change in `docs/progress.md`.

To add a word, add it at the end of its list in `mutate.py`.

A rule is one of two kinds:

- A line rule changes only its own line. Most rules are line rules.
- A text rule gets the whole text and returns the whole new text. Use it when the rule must change other lines, such as `inline_var`, or must know where its line is, such as `inline_local` and `early_return`.

To add a rule:

1. In `mutate.py`, write the function of the rule.
   - A line rule takes `(rng, line, ctx)` and returns the lines that replace `line`:
     - Return `[]` to delete the line.
     - Return `[new_line]` to change the line.
     - Return `[inserted_line, line]` to insert a line above it.
     - Return `None` when the rule does not fit the line.
   - A text rule takes `(rng, i, ctx)` and returns every line of the new text. `ctx.lines[i]` is the line that the run picked. Return `None` when the rule does not fit there.

   Use `rng` for every random choice, and never the order of a set.
   `ctx.lines` is the whole text before the change, and `ctx.donor_lines` holds the lines of all the run's seeds.
   To find code and not a string or a comment, search the lines that `_code(ctx.lines)` returns. They have the same positions.
2. Add a row at the end of `_RULES`:
   - for a line rule, `_Rule("your_rule", _line_rule(your_function))`
   - for a text rule, `_Rule("your_rule", your_function)`

   Do not put it first or in the middle.
   In a test, a rule added last kept 1608 of the first 2000 copies the same, and the same rule added first kept 86.
   The six loop rules, added last together, kept 25 of the first 2000 copies of random seed 1 on the nine seeds the same.
3. Add a row for the rule at the end of the table in [Change rules](#change-rules).
   A test checks that the table and `_RULES` list the same rules in the same order.
4. In `tests/test_mutate.py`, add a test that applies the rule to a short text and compares the result with the exact text that it must give.
   Change the expected input in `test_input_1_of_random_seed_1_on_a_two_line_text` to the new input 1.
5. Run `pytest`.
6. Compare the rules with and without the new rule:

   ```sh
   python scripts/compare_rules.py contracts/loop_* --count 5000 --random-seed 1 2 3 --leave-out your_rule
   ```

   For each set of rules, the script counts the `OK` inputs and the loop findings by first check.
   Leaving out a rule also changes the rules that the run picks for the other changes, so a small difference can be chance.

## Seeds

The seeds are in `contracts/`.
Each seed folder is its own Daml project, with one `.vy` file and a `daml.yaml` with `source: .`.
Separate projects let the fuzzer run on the seeds that you choose.

| Seed | Templates | Choices |
| --- | --- | --- |
| `contracts/asset_proposal/` | `Asset`, `AssetProposal` | `Give`, `Accept`, `Reject` |
| `contracts/ballot/` | `Ballot` | `CastVote`, `Close` |
| `contracts/escrow/` | `Payout`, `Escrow` | `Release`, `Refund` |
| `contracts/iou/` | `Iou` | `Transfer`, `Split` |
| `contracts/loop_count/` | `Iou` | `Count` |
| `contracts/loop_give/` | `Iou` | `GiveAll` |
| `contracts/loop_many/` | `Iou` | `Many` |
| `contracts/loop_pure/` | `Iou` | `Check` |
| `contracts/loop_verify/` | `Iou` | `Sum` |

### Loop seeds

The `contracts/loop_*` seeds hold `for` loops.
forge writes a loop with a ledger action, such as `create` or `fetch`, as `foldlA`.
`loop_many`, `loop_give`, and `loop_count` each have one such loop in a choice, and `loop_verify` has one in a `@ledger_effect` function.
`loop_pure` has loops without a ledger action, and forge writes them in three other ways.
It writes the sum with an `if` as `foldl`, the two nested loops as two `foldl`, the loop with an early `return` as a recursive helper function, and the loop with only an `assert` as `all`.

Each loop seed has at most one loop with a ledger action.
forge adds `import DA.Action (foldlA)` once, for the whole Daml module.
Some forge bugs write `foldlA` for a loop but do not add the import.
When a seed has a second `foldlA` loop, that loop adds the import anyway.
Then `damlc` builds the Daml, and the fuzzer does not see the bug.

To fuzz only the loop seeds, name their folders:

```sh
damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1
```

damlforge-fuzz has no option such as `--loops`.
To fuzz one area of forge, name the seed folders for that area.

### Check the seeds

Every seed must pass two checks.
Run both checks from the root of this repository.
Each command runs the check on every seed folder, and stops at the first seed that fails.

1. Compile the seeds to Daml with `forge`:

   ```sh
   for p in contracts/*/; do forge daml --no-i "$p" -o "build/daml/$(basename "$p")" || break; done
   ```

   For each seed, this command writes a `.daml` file to `build/daml/<seed>/`, such as `build/daml/iou/Iou.daml`.
   Keep `--no-i`. Without it, `forge daml` logs an error for a broken seed, but still exits with code 0.

2. Build the seeds with `damlc`:

   ```sh
   for p in contracts/*/; do forge dar "$p" -o "build/$(basename "$p").dar" || break; done
   ```

   For each seed, `forge dar` compiles the seed again, writes the `.daml` file next to it, such as `contracts/iou/Iou.daml`, and runs `dpm build`.
   It writes one `.dar` file for each seed to `build/`, such as `build/iou.dar`.
   Git ignores the generated files.

To check one seed, run the command in the loop yourself, for example `forge dar contracts/iou -o build/iou.dar`.

### Add a seed

1. Make a folder for the seed in `contracts/`, for example `contracts/vault/`.
2. Copy `contracts/iou/daml.yaml` into the new folder, and change its `name` line to `damlforge-fuzz-vault`.
3. Put the `.vy` file in the new folder.
4. Run both checks in [Check the seeds](#check-the-seeds).

A seed that fails a check is a bug in the seed.
Fix the seed before you use it, so that every crash that the fuzzer finds comes from an edit and not from the seed.

A seed with a `for` loop has two more rules:

- At most one loop in the file has a ledger action, such as `create` or `fetch`. [Loop seeds](#loop-seeds) tells why.
- No loop uses the code of a known forge loop bug in `bugs/loops/`. Some of these bugs, such as a `return` in a loop that creates a contract, give Daml that `damlc` builds, so the two checks do not find them. The [loop check](#loop-check) finds them: `damlforge-fuzz check` prints `BAD_LOOP` for such a seed, and `damlforge-fuzz run` stops before the first copy.

## Development

### Project layout

```
damlforge-fuzz/
├── src/damlforge_fuzz/
│   ├── cli.py            the damlforge-fuzz command
│   ├── compiler.py       compiles one .vy text with forge and sorts the result
│   ├── mutate.py         the change rules, and the sequence of inputs of a random seed
│   ├── runner.py         the fuzz loop
│   ├── report.py         crash groups, report.json, report.md, and the group folders
│   ├── shrinker.py       the shrinker
│   ├── damlc.py          builds the Daml with damlc, through dpm build
│   └── loopcheck.py      the loop check: finds wrong loops in forge's Daml
├── tests/                pytest tests, and in tests/loops/ the saved .vy and Daml pairs of the loop check
├── scripts/
│   ├── show_inputs.py    prints each copy of a run, its changes, and its result
│   ├── compare_rules.py  compares sets of change rules by what the loop check finds
│   └── update_loop_fixtures.py  writes the Daml in tests/loops/ again with the installed forge
├── contracts/            the seeds, one Daml project for each seed
├── reports/              the reports that are kept in git
├── bugs/                 hand-written programs that prove forge bugs, with their write-ups
├── docs/                 design notes and the progress log
└── pyproject.toml
```

`compiler.py` is the only module that imports forge.
`mutate.py`, `damlc.py`, and `loopcheck.py` do not import forge.

If you change the text of a stage in [Stages](#stages), also change `STAGE_TEXT` in `src/damlforge_fuzz/compiler.py`.
`report.md` uses the texts in `STAGE_TEXT`.
The table in [Loop check](#loop-check) has the texts of `LOOP_CHECK_TEXT` in `src/damlforge_fuzz/loopcheck.py`, which `report.md` also uses. A test checks that the two are the same.

### Run the tests

```sh
pytest
```

The tests that need dpm skip when dpm or the Daml SDK is missing.
The Daml in `tests/loops/` is from DamlForge 0.0.11.
The tests that compare it with the Daml that forge writes now skip on an older forge, such as `0.0.7`.
On a newer forge that writes other Daml, they fail.
Then run `python scripts/update_loop_fixtures.py`.
It writes the Daml of each fixture again with the installed forge, puts the forge version in `tests/loops/EXPECTED.tsv`, and prints each fixture whose Daml or loop findings changed.
Read each printed fixture. When its new loop findings are right, change its expected checks in `EXPECTED.tsv`.

### Show the inputs of a run

To see each copy, its changes, and its result, run `scripts/show_inputs.py`:

```sh
python scripts/show_inputs.py contracts/iou --count 5 --random-seed 1
```

The script makes the same copies as `damlforge-fuzz run` with the same seed folders and random seed.
