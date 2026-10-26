# damlforge-fuzz

A mutation fuzzer for `forge`, the DamlForge compiler that compiles `.vy` contracts to Daml.

damlforge-fuzz takes a few seed contracts and makes small random edits to them.
It compiles each edited copy with `forge`, groups the crashes, shrinks each crashing input to a few lines, and writes a report.
It also checks the loops in the Daml that `forge` writes, and reports the loops that `forge` translated wrongly.
With `--damlc`, it also builds the Daml that `forge` writes, and reports the Daml that the Daml compiler rejects.
With `--compare`, it also runs the `.vy` code and the Daml that `forge` writes on the same data, and reports the Daml that does not do what the `.vy` code does.

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
- **Text change rules.** Ten rules each change one line: they delete it, copy it, insert a line above it, or replace or delete one word. Five loop rules make the code shapes that break forge's loops, such as a `fetch` inside an expression or a `return` inside a loop.
- **Crash groups.** Crashes with the same exception at the same forge file and line are one group.
- **Shrinking.** The run cuts the first input of each crash group and each loop group down to the lines that cause the crash or the loop bug.
- **Daml checks.** With `--damlc`, the run builds the Daml that `forge` writes with `damlc`, and groups the Daml that `damlc` rejects.
- **Loop check.** For each `OK` input, the run checks the loops in the Daml that `forge` writes for four kinds of wrong translation, and groups the inputs with a loop bug. It does not need `damlc`.
- **Run and compare.** With `--compare`, the run calls the functions and choices of each `OK` input in Python and with Daml Script, on the same data, and groups the inputs whose Daml gives another result or creates other contracts.
- **Reports** in JSON and Markdown, with one folder for each group. You can compile each saved input again.

## Requirements

| Requirement | Version | Needed for |
| --- | --- | --- |
| Python | 3.11 or newer | All commands |
| DamlForge (`forge`) | Tested with `0.0.7` and `0.0.11` | All commands |
| dpm and the Daml SDK | SDK 3.5.2 | Only `--damlc`, `--compare`, and the second [seed check](#check-the-seeds) |

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
You need dpm and the Daml SDK only for `--damlc`, `--compare`, and the second [seed check](#check-the-seeds).

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
   OK       emit   contracts/import_qualified/import_qualified.vy
   OK       emit   contracts/import_qualified/models.vy
   OK       emit   contracts/import_sibling/import_sibling.vy
   OK       emit   contracts/import_sibling/models.vy
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
   random seed 999297, 13 seeds, 60 seconds
   random seed 999297: 84327 inputs, 15483 OK, 45515 rejected, 153 crash, 23176 skipped
   loops: 86 inputs with loop findings, 6 loop groups
   4 crash groups, report in reports/2026-10-22T11-13-00Z
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
damlforge-fuzz check [--damlc] [--compare] PATH [PATH ...]
damlforge-fuzz run [SEED_FOLDER ...] (--seconds N | --count N) [--random-seed S] [--reports DIR] [--damlc] [--compare]
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
| `--compare` | Also run each `OK` file that has a calls file in Python and with Daml Script, and compare. See [Run and compare](#run-and-compare). |

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
A `REJECTED`, `CRASH`, `BAD_DAML`, `BAD_LOOP`, or `BAD_RUN` line ends with the error.

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
| `--compare` | Also run the `OK` copies of the seeds that have a calls file in Python and with Daml Script, and compare. See [Run and compare](#run-and-compare). |

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

1. Compile the unchanged seeds, and run the loop check on them. With `--damlc`, also build their Daml. With `--compare`, also run the calls of each seed that has a calls file.
2. Make the copies, and compile each copy with `forge`.
3. With `--damlc`, build the Daml of the `OK` copies.
4. With `--compare`, run the `OK` copies of the seeds with a calls file in Python and with Daml Script, and compare.
5. Shrink the first input of each crash group and each loop group.
6. Write the report.

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
random seed 1, 13 seeds, 2000 inputs
random seed 1: 2000 inputs, 357 OK, 1077 rejected, 4 crash, 562 skipped
damlc: 205 Daml texts, 108 bad, 20 bad Daml groups
loops: 2 inputs with loop findings, 1 loop group, 0 build with damlc
3 crash groups, report in reports/2026-10-22T11-34-07Z
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
| `I1` | The Daml uses a qualified name, such as `Map.insert`, `M.Note`, or a type used as a value, `Party.amount`, but no import line binds its qualifier. A lower-case qualifier, such as `models.double`, counts only when the `.vy` text binds that name to a module, as `import models` does. damlc rejects the Daml. |
| `I2` | An import line of the Daml has an alias that is not a Daml module name, such as `import qualified Models as m`. damlc rejects the Daml. |
| `I3` | The Daml selects an upper-case name, such as an enum value or a choice, from an expression: `(M.Kind).CASH`. Daml has no such syntax, so damlc rejects the Daml. |
| `I4` | The .vy code imports a name from a sibling module or a stub, but the Daml has no import of that module, or its import does not list the name. |

An input that fails a check `L1` to `L4` is `BAD_LOOP`.
The checks `I1` to `I4` are the import check, in `src/damlforge_fuzz/importcheck.py`. They read the import lines of forge's Daml and the `.vy` text, and an input that fails one is `BAD_IMP`. Their groups are `i01`, `i02`, ..., next to the loop groups `l01`, `l02`, ..., and the `loops:` line counts both.
`check` prints every check that the file fails, and the first bug.
The seven programs in [`bugs/loops/`](bugs/loops/) each show a forge loop bug:

```
$ damlforge-fuzz check bugs/loops
BAD_LOOP emit   bugs/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   bugs/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   bugs/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20
BAD_LOOP emit   bugs/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7
BAD_LOOP emit   bugs/loops/b21_return_in_create_loop.vy  L3: the return in a loop of choice GiveUntil at Daml line 14 is lost (1 loop with a return, 0 early-return helpers)
BAD_LOOP emit   bugs/loops/b22_return_in_inner_loop.vy  L3: the return in a loop of function first_positive at Daml line 3 is lost (2 loops with a return, 0 early-return helpers)
OK       emit   bugs/loops/b23_pass_in_loop.vy
```

No loop check finds b23, so its line is `OK`. [Run and compare](#run-and-compare) shows how `--compare` finds it.
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
OK       emit   bugs/loops/b23_pass_in_loop.vy
```

How a run uses the loop check:

- Before the first copy, the run compiles the unchanged seeds and runs the loop check on them.
  A seed with a loop bug stops the run with exit code 2, because almost every copy would have the same bug:

  ```
  $ damlforge-fuzz run bugs/loops/b17_create_append.vy --count 10
  damlforge-fuzz run: the loop check finds a bug in seed bugs/loops/b17_create_append.vy: L1: foldlA at Daml line 20 with no import DA.Action
  ```

- After the last copy, the run groups the `OK` copies with a loop bug.
  A copy goes to the group of its first check, so a run without `--damlc` has at most eight groups: four loop groups and four import groups.
  The `loops:` line comes before the last line:

  ```
  $ damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1
  random seed 1, 5 seeds, 5000 inputs
  random seed 1: 5000 inputs, 852 OK, 2828 rejected, 4 crash, 1316 skipped
  loops: 2 inputs with loop findings, 1 loop group
  1 crash group, report in reports/2026-10-22T11-12-56Z
  ```

- With `--damlc`, the run also splits the loop groups by the verdict of `damlc`.
  So a group whose Daml builds does not hide behind an earlier input whose Daml `damlc` rejects.
  The `loops:` line also gives the number of groups that build:

  ```
  $ damlforge-fuzz run contracts/loop_* --damlc --count 5000 --random-seed 1
  random seed 1, 5 seeds, 5000 inputs
  random seed 1: 5000 inputs, 852 OK, 2828 rejected, 4 crash, 1316 skipped
  damlc: 353 Daml texts, 238 bad, 17 bad Daml groups
  loops: 2 inputs with loop findings, 1 loop group, 0 build with damlc
  1 crash group, report in reports/2026-10-22T11-34-07Z
  ```

  Here the one group, `i01` (`I1`), is Daml that `damlc` rejects.
  On DamlForge 0.0.11, the same command gave five loop groups, and the `L3` inputs made two of them: `l01`, whose Daml `damlc` builds, and `l05`, whose Daml `damlc` rejects.

- After the crash groups, the run shrinks the first input of each loop group.
  [Shrunk inputs](#shrunk-inputs) tells how.

The loop check has these limits:

- It reads the Daml in the layout that forge writes: one statement on each line, and `do` at the end of the line that opens a block.
  If forge changes its layout, the check can give wrong results.
  The tests in `tests/test_loopcheck.py` compare the Daml that forge writes with saved Daml, so they show such a change first.
- `L3` does not know whether the lost `return` changes the result. A lost `return` before code that does nothing is harmless.

### Run and compare

The loop check knows only the known shapes of wrong loops, and `damlc` only tells whether the Daml builds.
Neither one runs the code.
With `--compare`, `run` and `check` run it.
They call the functions and choices of each `OK` input twice, with the same data: in Python, on the `.vy` code, and with Daml Script, on the Daml that forge writes.
Then they compare the results and the contracts that each call creates.
`BAD_RUN` means that the Daml does not do what the `.vy` code does.

`--compare` needs dpm and the Daml SDK. [Install dpm and the Daml SDK](#install-dpm-and-the-daml-sdk) shows how to install them.
Only the seeds that have a [calls file](#calls-files) are compared, so you choose the area with the seed folders, as for every run:

```
$ damlforge-fuzz run contracts/loop_* --compare --count 5000 --random-seed 1
random seed 1, 5 seeds, 5000 inputs
random seed 1: 5000 inputs, 852 OK, 2828 rejected, 4 crash, 1316 skipped
loops: 2 inputs with loop findings, 1 loop group
compare: 389 inputs compared, 0 differ, 0 run groups
1 crash group, report in reports/2026-10-22T11-34-13Z
```

The `compare:` line comes after the `loops:` line:

- `inputs compared`: the `OK` copies of the seeds with a calls file whose calls ran in Python and in Daml. Many copies have the same text, so the run compares each text once.
- `differ`: the compared copies whose Daml does not do what the `.vy` code does in a call.
- `run groups`: the number of groups of these copies. Copies with the same kind of difference and the same first loop check are one group.

On DamlForge 0.0.12 this run finds no difference: forge 0.0.12 writes these loops right.
On DamlForge 0.0.11, the same command found two run groups.
Group `r01` was a lost `return` in `has_party`, which the loop check also finds (`L3`).
Group `r02` was a copy with a `pass` above the `if` in the loop of `GiveAll`.
forge dropped the `create` after the `pass`, the Daml built, and no loop check failed.
That is bug b23. [b23 in `bugs/loops/`](bugs/loops/README.md#b23-pass-drops-the-rest-of-its-block) tells its cause.

#### Why `--compare` is an option

- **It finds bugs that the other checks miss.** The loop check finds only the shapes of wrong loops that are known: `L1` to `L4`. `damlc` only tells whether the Daml builds. For b23, forge drops an `assert`, the Daml builds, and no loop check fails. Only a run of both programs on the same data shows that the Daml accepts a negative number that the `.vy` code rejects.
- **It is slow, and it needs dpm.** Without `--compare`, the run above took 3.3 seconds on DamlForge 0.0.11, and it does not need dpm. With `--compare`, it took 61 seconds. The compare step takes 51 seconds, and the check of the seeds before the first copy takes about 6.5 seconds. A plain run must stay fast and must work without the Daml SDK.
- **It is not part of `--damlc`.** `damlc` builds the Daml, and `--compare` runs it. They cost different amounts and answer different questions, so a run can use one of them or both. With both, the compare step uses the verdicts of `damlc` and does not build the Daml of the copies again.

#### Calls files

A calls file is next to its seed, with the same name and the extension `.calls.yaml`.
For example, the calls file of `contracts/loop_give/loop_give.vy` is `contracts/loop_give/loop_give.calls.yaml`:

```yaml
# With `stop` in the list, a lost return or a lost create changes the contracts.
- choice: Iou.GiveAll
  contract: {issuer: alice, owner: alice, amount: "1.0"}
  args: {owners: [alice, stop, bob], stop: stop}
- choice: Iou.GiveAll
  contract: {issuer: alice, owner: bob, amount: "2.5"}
  args: {owners: [bob, alice], stop: stop}
```

Each call names a `function` or a `choice` (`Template.Choice`), and gives its arguments in `args`.
A choice also gives the fields of the contract that it runs on, in `contract`.
Each value has the type of its annotation in the seed:

| Type | Value in the calls file |
| --- | --- |
| `Party` | A name, such as `alice`. Each name is one party. Each script allocates every party of the file. |
| `Decimal` | A string or a number, such as `"-2.0"`, with at most 10 decimal places. |
| `int` | A whole number. |
| `bool` | `true` or `false`. |
| `list[T]` | A list of values of type `T`. |
| `ContractId[T]` | `{create: T, with: {...}}`: a contract with these fields that the script creates before the call. |

A call cannot name a function that forge makes a Daml `Update` function, because Daml Script cannot call it. forge does this for a function that calls `fetch`, `create`, `exercise`, `archive`, `lookup`, or `datetime.now()`, or that calls such a function. Call a choice that calls it, as `contracts/loop_verify/loop_verify.calls.yaml` does.

The five loop seeds have a calls file.
Each calls file reaches every loop of its seed, with data where a lost `return`, a lost `assert`, or a lost `create` changes the result.
For example, `owners: [alice, stop, bob]` makes the loop of `GiveAll` pass `stop`, and the second call of `Check` in `loop_pure.calls.yaml` gives a negative number.

`run` and `check` check a calls file against its seed when they load it.
An unknown function, choice, field, or parameter, or a value that does not fit its type, is a usage error.
The error names the file and the call.
Before the first copy, `run` also runs the calls of each seed with the seed itself.
When the seed's Daml does not do what its `.vy` code does, the run prints one line to stderr and exits with 2, because the calls file or the seed is wrong.

#### How a copy is compared

1. Python runs each call on the `.vy` code of the copy, with stand-ins for the names that forge gives meaning to.
2. `damlc` builds the Daml that forge wrote for the copy. With `--damlc`, the step uses the verdict that `damlc` already gave.
3. Daml Script runs each call that Python ran, with one script for each call. The run puts up to 100 copies into one temporary Daml project, with a test module for each copy, and runs `dpm build` and `dpm test` in it.
4. For each copy with a failed script, the run writes one script for each question and runs them again, so that the kind of the difference comes from which scripts fail.

The first call, in calls file order, whose scripts fail is the difference of the copy:

| Difference | Script that fails | Meaning |
| --- | --- | --- |
| `daml_fails` | `c1_runs` | Python runs the call, and Daml fails. |
| `result` | `c1_result` | Both run, and the results differ. |
| `contracts` | `c1_contracts` | Both run, and the results are the same, but the contracts that the call creates differ. |
| `daml_passes` | `c1_fails` | Python fails the call on an `assert`, and Daml runs it. |

The number in the script name is the place of the call in the calls file.
The run compares a contract ID in a result by its contract.

These are the stand-ins on the Python side:

- A template class is a Python dataclass with the fields of the template. The run drops every decorator and every `from forge` import.
- `create` adds a contract to a ledger of the call and returns its ID. `fetch` reads it.
- In a choice, `create` and `fetch` follow the authorization rules of Daml: the controllers of the choice and the signatories of its contract authorize them. Without this rule, a copy with `signatory: list[Party] = [owner]` failed in Daml but ran in Python.
- `is` and `is not` mean `==` and `!=`, as forge writes them.
- A call can run at most 100000 lines of Python. A loop such as `while True: pass` stops there, and the call is skipped.

The run does not compare these copies and calls:

- A copy with a statement at module level or in a class body that is not a definition, a field, an import, or a docstring. Python runs a module-level `assert False`, but forge does not.
- A call whose function or choice, or whose template with its fields, is not the same as in the seed.
- A call that raises a Python error other than an `AssertionError`, or that returns a value that does not fit the types of the seed, such as a `Decimal` with more than 10 decimal places.
- A call of a plain function that fails in Python. In Daml, the `assert` of a plain function is an `error`, which Daml Script cannot catch.
- A copy whose Daml or test module `damlc` rejects. The run counts it as dropped.

In the run above, the compare step compared 367 of the 972 `OK` copies, and 4 of them differ.
Python could run no call of 419 copies, and `damlc` rejected the Daml or the test module of 186 copies.

With `check --compare`, each `OK` file that has a calls file next to it runs in the same way.
A file whose Daml does not do what its `.vy` code does is `BAD_RUN`.
The line gives the kind of the difference, the call, and what the `.vy` code does in Python.
`BAD_RUN` comes before `BAD_LOOP`: a file with both prints `BAD_RUN`, and the line ends with its first loop check.
b21, b22, and b23 in `bugs/loops/` have a calls file:

```
$ damlforge-fuzz check --compare bugs/loops
BAD_LOOP emit   bugs/loops/b17_create_append.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   bugs/loops/b18_fetch_in_sum.vy  L1: foldlA at Daml line 20 with no import DA.Action
BAD_LOOP emit   bugs/loops/b19_fetch_in_if_test.vy  L2 L4: fetch at Daml line 22 in the pure foldl of line 20
BAD_LOOP emit   bugs/loops/b20_fetch_in_plain_function.vy  L2 L4: fetch at Daml line 9 in the pure foldl of line 7
BAD_RUN  emit   bugs/loops/b21_return_in_create_loop.vy  contracts in Iou.GiveUntil #1: returns None, makes 1 contract: Iou(issuer=issuer, owner=alice, amount=1.0); loop check L3
BAD_RUN  emit   bugs/loops/b22_return_in_inner_loop.vy  result in first_positive #1: returns 3; loop check L3
BAD_RUN  emit   bugs/loops/b23_pass_in_loop.vy  daml_passes in Iou.Check #2: fails: positive
```

`--compare` has these limits:

- The run does not shrink the run groups, because each try needs its own `dpm test`, about 4 seconds.
- The stand-ins do not cover every difference between Python and Daml. For example, Python computes a `Decimal` with 28 digits and an `int` with no limit. Daml rounds a `Decimal` to 10 decimal places, and fails on an `Int` that does not fit in 64 bits, also in the middle of a call. The run skips only a result that does not fit.
- A difference shows only when the data of a call makes it show. The `early_return` [change rule](#change-rules) inserts `if v == v:`, which is always true, so a lost `return` above a `create` changes nothing that a call can see. In the runs of `contracts/loop_*` with `--count 5000` and the random seeds 1, 2, and 3, no copy showed b21. With `--random-seed 4`, the run found b21 by the comparison: a `contracts` group whose first loop check is `L3`.

### Results

The first column of a `check` line is the result:

| Result | Meaning |
| --- | --- |
| `OK` | forge wrote Daml. |
| `REJECTED` | forge reported an error in the input, such as `DF1213`. |
| `CRASH` | forge failed with an error that is not its own. This is a bug in forge. The line ends with the exception and the forge file and line where it failed. |
| `BAD_DAML` | Only with `--damlc`. forge wrote Daml, but `damlc` rejects it. This is also a bug in forge. |
| `BAD_LOOP` | forge wrote Daml, but the [loop check](#loop-check) finds a wrong loop in it. This is also a bug in forge. With `--damlc`, the line ends with the verdict of `damlc`. |
| `BAD_RUN` | Only with `--compare`. forge wrote Daml that `damlc` builds, but the Daml does not do what the `.vy` code does when the [calls file](#calls-files) runs. This is also a bug in forge. |

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
| `0` | Every file is `OK`. | No copy crashed, no Daml text is bad, and the report has no loop group and no run group. | The command wrote the shrunk file. |
| `1` | A file is `REJECTED`, `CRASH`, `BAD_DAML`, `BAD_LOOP`, or `BAD_RUN`. | A copy crashed, a Daml text is bad, or the report has a loop group or a run group. | FILE does not crash forge and has no loop bug. The command writes nothing. |
| `2` | Usage error. | Usage error. | Usage error. |
| `130` | — | You pressed Ctrl-C. See [Stop a run with Ctrl-C](#stop-a-run-with-ctrl-c). | You pressed Ctrl-C. The command writes nothing. |

A usage error prints one line to stderr.
These are the usage errors:

- For all commands: a missing path, a folder with no `.vy` file, a file that cannot be read, or DamlForge is not installed.
- With `--damlc`: a file with no `daml.yaml`, dpm or its SDK is missing, or dpm fails.
- With `--compare`: a calls file that does not fit its `.vy` file, a file with a calls file and no `daml.yaml`, dpm or its SDK is missing, or dpm fails. For `run`, also no seed with a calls file, or a seed whose Daml does not do what its `.vy` code does.
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
  The `compare` entry has the counts of the compare step (`compared`, `skipped`, `dropped`, `differ`, and `skipped_calls`, the calls of the compared copies that were not compared) and its time. Without `--compare`, `compare` is `null`.
  A run group entry has the kind of the difference (`difference`), the call (`call`, such as `Iou.GiveAll #1`), the first loop check of its first input or `null` (`loop_check`), what Python does in the call (`python`), the number of inputs, the first input, the Daml that forge wrote for it, and its test module (`test`).
- `report.md` is a short summary of `report.json`.
  It has one table row for each group, with a `Shrunk` column, such as `3 of 42 lines`, and a code block with each shrunk input.
  It also tells what the stages of the groups mean.
  With `--damlc`, it has a `Bad Daml` section with a table of the groups and the first error line of each group.
  It has a `Loop check` section, with the checks of the loop groups, a table of the groups with a `Shrunk` column, the first bug of each group, and a code block with each shrunk input and its Daml.
  With `--compare`, it has a `Run and compare` section, with the counts of the compare step, a table of the run groups, and what Python does in the call of each group.
- `groups/g01/`, `groups/g02/`, and so on are the crash groups, in the order that the run found them.
- `groups/d01/`, `groups/d02/`, and so on are the bad Daml groups, in the order that the run found them.
- `groups/l01/`, `groups/l02/`, and so on are the loop groups, in the order that the run found them.
- `groups/i01/`, `groups/i02/`, and so on are the import groups (checks `I1` to `I4`), in the order that the run found them. Their folders are like loop group folders.
- `groups/r01/`, `groups/r02/`, and so on are the run groups, in the order that the run found them.

The report in the repository is from before the loop check, so it has no loop group.
A loop group or import group folder has the first input, a copy of the seed's `daml.yaml` when the seed has one, and the Daml that forge wrote for the input.
Its `shrunk/` folder has the shrunk input and the Daml that forge wrote for it.
For example, `damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1` writes this folder:

```
groups/i01/
├── loop_count.vy      the first input whose first check is I1
├── daml.yaml          a copy of the seed's daml.yaml
├── LoopCount.daml     the Daml that forge wrote for the input
└── shrunk/
    ├── loop_count.vy  the shrunk input
    └── LoopCount.daml the Daml that forge wrote for the shrunk input
```

A group of an import seed also has the seed's sibling `.vy` files, such as `models.vy`, in the group folder and in `shrunk/`, so `check` on the saved input finds the modules it imports.
A folder with Daml also has forge's Daml of each sibling module that the input's Daml imports, such as `Models.daml`, so `dpm build` there builds what `damlc` built in the run.
With `--damlc`, `damlc` builds each Daml text together with forge's Daml of the sibling modules that the text imports, directly or through another sibling.

A run group folder is a Daml project.
For example, `damlforge-fuzz run contracts/loop_* --compare --count 5000 --random-seed 1` writes this folder:

```
groups/r02/
├── loop_give.vy           the first input of the group
├── loop_give.calls.yaml   a copy of the seed's calls file
├── daml.yaml              the seed's daml.yaml, with daml-script and source: daml
└── daml/
    ├── LoopGive.daml      the Daml that forge wrote for the input
    └── Test.daml          the scripts of the input's calls, one for each question
```

The run does not shrink the run groups.

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

To see a run difference again, run `check --compare` on the input in the run group folder.
This example uses the report of the run in [Run and compare](#run-and-compare):

```
$ damlforge-fuzz check --compare reports/2026-10-20T15-55-09Z/groups/r02/loop_give.vy
BAD_RUN  emit   reports/2026-10-20T15-55-09Z/groups/r02/loop_give.vy  contracts in Iou.GiveAll #1: returns None, makes 2 contracts: Iou(issuer=alice, owner=alice, amount=1.0), Iou(issuer=alice, owner=bob, amount=1.0)
```

To see what the Daml does, without the fuzzer, run `dpm test` in the run group folder.
The scripts that fail show the difference.
`dpm test` exits with 1, and its test summary has these lines:

```
daml/Test.daml:c1_contracts: failed
daml/Test.daml:c1_result: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c1_runs: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c2_contracts: failed
daml/Test.daml:c2_result: ok, 1 active contracts, 2 transactions.
daml/Test.daml:c2_runs: ok, 1 active contracts, 2 transactions.
```

The failure message of `c1_contracts` is `expected [] == [Iou {issuer = 'alice-d4d95138', owner = 'alice-d4d95138', amount = 1.0},Iou {issuer = 'alice-d4d95138', owner = 'bob-4f1df03a', amount = 1.0}]`.
The left list has the contracts that the Daml of `GiveAll` created. The right list has the contracts that the `.vy` code creates.

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
| While it makes copies | Stops the copies. With `--damlc`, it still builds the Daml. With `--compare`, it still compares. It still shrinks. `report.json` has `"interrupted": true`. |
| While `damlc` builds | Keeps the texts that it built, and stops the `damlc` step. It still shrinks. The `damlc` entry in `report.json` has `"interrupted": true`. A loop group whose Daml `damlc` did not build has `"damlc": null`, and `report.md` shows `not built`. |
| While it compares | Keeps the batches of 100 copies that it compared, and stops the compare step. It still shrinks. The `compare` entry in `report.json` has `"interrupted": true`. |
| While it shrinks | Stops the shrinking. The groups that are not shrunk yet have `"shrunk": null`, and `report.md` shows `not shrunk`. A loop group that is not shrunk yet also has `"shrunk_daml": null`. |

## Change rules

For each change, the run picks one line and one of these rules, each with the same chance.
A word is a name, a number, or an operator.
A rule that does not fit its line, such as `operator` on a line with no operator, leaves the line as it was.
The first ten examples are real changes to `contracts/iou/iou.vy`, and the next five are real changes to the loop seeds.

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
| `early_return` | In a loop body, inserts `if v == v:` and the `return` line that follows the loop, above the line. `v` is the loop's name. It looks out through `if` and `else` blocks and inner loops for the nearest loop that a `return` follows. | `if c == c:` and `return n` are inserted above `n = n + 1` |
| `wrap_in_loop` | Puts a statement that has an indent into `for _k in range(0, 2):`. | `return cids` becomes `for _k in range(0, 2):` and `    return cids` |
| `dedent_line` | Moves a line with an indent of 8 or more 4 spaces to the left. | `cid = create(...)` moves out of the `if` |
| `inline_var` | On `v = value`, puts the value in place of each use of `v` below it in the same block, and deletes the line. It does not fit when `v` gets a new value in that block. | `cid = create(Iou(...))` is deleted, and `cids.append(cid)` becomes `cids.append(create(Iou(...)))` |
| `import_name` | In `from m import a, b` at column 0, deletes one name, or adds a name from any seed. | `from models import Kind, Lot, Note, double` becomes `from models import Kind, Lot, Note` |
| `import_module` | Changes the module of an import line at column 0: `.m`, `..m`, `pkg.m`, `forge.m`, or `ms`. | `import math as m` becomes `import forge.math as m` |
| `import_form` | Changes `from m import a, b` to `import m as A`, and each use `a` to `A.a`, or back. `A` is `M`, `m`, `Lib`, or none (`import m` and `m.a`). | `from models import Note` becomes `import models as M`, and `ContractId[Note]` becomes `ContractId[M.Note]` |

The rules take their new words from five lists in `src/damlforge_fuzz/mutate.py`: `_OPERATORS`, `_LITERALS`, `_TYPES`, `_EXPRESSIONS`, and `_STATEMENTS`.
Most rules change only their own line.
`inline_local` and `early_return` read the whole text, and `inline_var` and `import_form` also change other lines.
The five loop rules never take a string or a comment for code.

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
Each seed folder is its own Daml project, with a `daml.yaml` with `source: .`. Most have one `.vy` file. The two import seeds also have a sibling module, `models.vy`, which is a seed too.
The five loop seeds also have a [calls file](#calls-files) for `--compare`.
Separate projects let the fuzzer run on the seeds that you choose.

| Seed | Templates | Choices |
| --- | --- | --- |
| `contracts/asset_proposal/` | `Asset`, `AssetProposal` | `Give`, `Accept`, `Reject` |
| `contracts/ballot/` | `Ballot` | `CastVote`, `Close` |
| `contracts/escrow/` | `Payout`, `Escrow` | `Release`, `Refund` |
| `contracts/import_qualified/` | `Desk`; `Note` in `models.vy` | `Issue`, `Size` |
| `contracts/import_sibling/` | `Desk`; `Note` in `models.vy` | `Issue`, `Size` |
| `contracts/iou/` | `Iou` | `Transfer`, `Split` |
| `contracts/loop_count/` | `Iou` | `Count` |
| `contracts/loop_give/` | `Iou` | `GiveAll` |
| `contracts/loop_many/` | `Iou` | `Many` |
| `contracts/loop_pure/` | `Iou` | `Check` |
| `contracts/loop_verify/` | `Iou` | `Sum` |

### Import seeds

The `contracts/import_*` seeds test forge's imports between `.vy` files.
In each folder, the main file imports a template, a struct, an enum, and a function from `models.vy`, the file next to it:
`import_sibling.vy` with `from models import Kind, Lot, Note, double`, and `import_qualified.vy` with `import models as M` and `M.Note`.
forge reads the sibling file from the disk, so a change to the main file is compiled against the unchanged `models.vy`.
The import seeds use no qualified enum value, such as `M.Kind.CASH`, because forge rejects it (b31 in `bugs/imports/`).

### Loop seeds

The `contracts/loop_*` seeds hold `for` loops.
forge writes a loop with a ledger action, such as `create` or `fetch`, as `foldlA`.
`loop_many`, `loop_give`, and `loop_count` each have one such loop in a choice, and `loop_verify` has one in a top-level function, which forge makes a Daml `Update` function because it calls `fetch`.
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
5. Optional: to compare the copies of the seed with `--compare`, write its [calls file](#calls-files), such as `contracts/vault/vault.calls.yaml`. `damlforge-fuzz run contracts/vault --compare --count 1` checks the calls file and runs it with the seed.

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
│   ├── loopcheck.py      the loop check: finds wrong loops in forge's Daml
│   └── compare.py        runs an input in Python and with Daml Script, and compares
├── tests/                pytest tests, and in tests/loops/ the saved .vy and Daml pairs of the loop check
├── scripts/
│   ├── show_inputs.py    prints each copy of a run, its changes, and its result
│   ├── compare_rules.py  compares sets of change rules by what the loop check finds
│   └── update_loop_fixtures.py  writes the Daml in tests/loops/ again with the installed forge
├── contracts/            the seeds, one Daml project for each seed, and the calls files
├── reports/              the reports that are kept in git
├── bugs/                 hand-written programs that prove forge bugs, with their write-ups
├── docs/                 design notes and the progress log
└── pyproject.toml
```

`compiler.py` is the only module that imports forge.
`mutate.py`, `damlc.py`, `loopcheck.py`, and `compare.py` do not import forge.

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
