# damlforge-fuzz

damlforge-fuzz is a fuzzer for `forge`, the compiler of [DamlForge](https://github.com/noders-team/damlforge).
forge compiles `.vy` contracts to Daml. A `.vy` contract uses Python syntax.

The fuzzer makes small random changes to seed contracts, and compiles each changed copy with `forge`.
It finds four kinds of forge bugs:

- forge crashes with a Python error.
- forge writes a wrong loop or a wrong import in the Daml. The fuzzer finds these bugs in the Daml text, without a Daml compiler.
- forge writes Daml that the Daml compiler, `damlc`, rejects. To find these bugs, use the option `--damlc`.
- forge writes Daml that does not do what the `.vy` code does. To find these bugs, use the option `--compare`. It runs the `.vy` code in Python and the Daml with Daml Script, on the same data.

The fuzzer puts the bugs into groups and writes a report.
For a crash, a wrong loop, or a wrong import, it also cuts the input down to a few lines.

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Found issues](#found-issues)
- [Guides](#guides)
  - [Fuzz one area of forge](#fuzz-one-area-of-forge)
  - [Fuzz your own DamlForge checkout](#fuzz-your-own-damlforge-checkout)
  - [Find Daml that damlc rejects](#find-daml-that-damlc-rejects)
  - [Compare the Daml with the .vy code](#compare-the-daml-with-the-vy-code)
  - [Write a calls file](#write-a-calls-file)
  - [See a group again](#see-a-group-again)
  - [Shrink a file](#shrink-a-file)
  - [Repeat a run](#repeat-a-run)
- [Reference](#reference)
  - [Commands](#commands)
  - [Output of run](#output-of-run)
  - [Results](#results)
  - [Stages](#stages)
  - [Loop check](#loop-check)
  - [Differences](#differences)
  - [Calls files](#calls-files)
  - [Exit codes](#exit-codes)
  - [Stop a run with Ctrl-C](#stop-a-run-with-ctrl-c)
  - [Report files](#report-files)
  - [Seeds](#seeds)
- [Change rules](#change-rules)
- [How it works](#how-it-works)
- [Development](#development)
- [License](#license)

## Install

You need Python 3.11 or newer.
Run these commands:

```sh
git clone https://github.com/noders-team/damlforge-fuzz.git
cd damlforge-fuzz
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
```

The last command also installs the latest release of DamlForge from PyPI, the `damlforge` package.
DamlForge has the `forge` command and the `forge` Python package.
The `test` extra also installs pytest.
If DamlForge is already installed, `pip install -U damlforge` gets the latest release.

To check the install, run `damlforge-fuzz --help` and `forge --version`.

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

## Quick start

Run these commands from the root of this repository.

1. Compile the seeds:

   ```
   $ damlforge-fuzz check contracts
   OK       emit   contracts/asset_proposal/asset_proposal.vy
   OK       emit   contracts/ballot/ballot.vy
   OK       emit   contracts/escrow/escrow.vy
   OK       emit   contracts/import_call/import_call.vy
   OK       emit   contracts/import_call/models.vy
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

   Every line must start with `OK`.
   If a line does not start with `OK`, the seed does not fit your DamlForge version.
   Report it in the GitHub issues of this repository.

2. Fuzz the seeds for 60 seconds:

   ```
   $ damlforge-fuzz run --seconds 60
   random seed 535031, 15 seeds, 60 seconds
   random seed 535031: 81396 inputs, 12870 OK, 47624 rejected, 0 crash, 20902 skipped
   loops: 78 inputs with loop findings, 2 loop groups
   0 crash groups, report in reports/2026-10-28T10-31-07Z
   ```

   Your numbers are different.
   They depend on the random seed, the speed of your computer, and your DamlForge version.
   [Output of run](#output-of-run) tells what each line means.

3. Open `report.md` in the report folder.
   It has one table row for each group, and the shrunk input of each crash group, loop group, and import group.
   If the run found no group, the report has only the counts.

4. Check the input of a group again:

   ```sh
   damlforge-fuzz check reports/<run>/groups/<group>
   ```

   `<run>` is the name of the report folder that the run printed.
   `<group>` is a group folder in its `groups/` folder, such as `i01`.
   Each line gives the same result as `report.md`.
   The command also checks the shrunk input in `shrunk/`.

5. Repeat the run.
   Use the random seed from the first line of step 2, and the number of inputs from the second line:

   ```sh
   damlforge-fuzz run --count 81396 --random-seed 535031
   ```

   The run makes the same inputs in the same order.
   With the same DamlForge, it also prints the same counts.
   [Repeat a run](#repeat-a-run) tells more.

## Found issues

The work on damlforge-fuzz found issues in DamlForge.
[ISSUES.md](ISSUES.md) lists them, with their status and how to check them on your own DamlForge.

## Guides

Each guide shows how to do one task.
Run the commands from the root of the repository.

### Fuzz one area of forge

To fuzz one area of forge, name the seed folders for that area.
damlforge-fuzz has no option such as `--loops`.
For example, this command fuzzes only the loop seeds:

```sh
damlforge-fuzz run contracts/loop_* --count 5000 --random-seed 1
```

[Seeds](#seeds) lists the seed folders.

### Fuzz your own DamlForge checkout

To fuzz a DamlForge checkout that you change, install it in the virtual environment of damlforge-fuzz:

```sh
git clone https://github.com/noders-team/damlforge.git
pip install -e ./damlforge
```

The checkout replaces the release from PyPI.
Your changes to the checkout apply without a reinstall.

### Find Daml that damlc rejects

forge says `OK` when it writes Daml, but the Daml can still be wrong.
With `--damlc`, `run` and `check` also build the Daml of the `OK` inputs with `damlc`.
`BAD_DAML` means that forge wrote Daml, but `damlc` rejects that Daml.
That is a bug in forge.
Its check stage let through a program that it then translated to wrong Daml.

`--damlc` needs dpm and the Daml SDK. [Install dpm and the Daml SDK](#install-dpm-and-the-daml-sdk) shows how to install them.

To find bad Daml in a run, add `--damlc`:

```sh
damlforge-fuzz run --damlc --seconds 60
```

The run prints a `damlc:` line.
The report has one folder for each group of bad Daml, such as `groups/d01/`.

To check one file, use `check --damlc`.
A file whose Daml `damlc` rejects is `BAD_DAML`.
The line ends with the first line of the first `damlc` error.
For example, this is the result for the program of b35 when the bug is there:

```
$ damlforge-fuzz check --damlc reports/2026-10-26T07-07-10Z/analysis/b35_template_named_like_enum_value.vy
BAD_DAML emit   reports/2026-10-26T07-07-10Z/analysis/b35_template_named_like_enum_value.vy  Multiple declarations of ‘CASH’
```

### Compare the Daml with the .vy code

The loop check knows only the known shapes of wrong loops, and `damlc` only tells whether the Daml builds.
Neither one runs the code.
With `--compare`, `run` and `check` run it.
They call the functions and choices of each `OK` input twice, with the same data: in Python, on the `.vy` code, and with Daml Script, on the Daml that forge writes.
Then they compare the results and the contracts that each call creates.
`BAD_RUN` means that the Daml does not do what the `.vy` code does.

`--compare` needs dpm and the Daml SDK. [Install dpm and the Daml SDK](#install-dpm-and-the-daml-sdk) shows how to install them.

Only the seeds that have a [calls file](#calls-files) are compared, so you choose the area with the seed folders, as for every run.
The five loop seeds have a calls file:

```sh
damlforge-fuzz run contracts/loop_* --compare --count 5000
```

The run prints a `compare:` line.
The report has one folder for each run group, such as `groups/r01/`.

To compare one file, use `check --compare`.
The file needs a calls file next to it.
A file whose Daml does not do what its `.vy` code does is `BAD_RUN`.
The line gives the kind of the difference, the call, and what the `.vy` code does in Python.
`BAD_RUN` comes before `BAD_LOOP`.
A file with both prints `BAD_RUN`, and the line ends with its first loop check.

When `check --compare` compares nothing, the `OK` line ends with `not compared:` and the reason.
This happens when Python skipped every call of the file, or when `damlc` rejects the Daml or the test module.
For example, a call of a function that forge makes a Daml `Update` function gives `not compared: damlc rejects: Couldn't match expected type ‘Update Decimal’`.
Only an `OK` line without `not compared` means that the calls ran in Python and in Daml and gave the same results.

### Write a calls file

A calls file tells `--compare` which functions and choices to call, and with which data.
[Calls files](#calls-files) gives the format.

1. Make the file next to the `.vy` file of the seed, with the same name and the extension `.calls.yaml`.
2. Add a call for each function or choice that you want to compare.
3. Give data where a lost `return`, a lost `assert`, or a lost `create` changes the result.
   For example, `owners: [alice, stop, bob]` in `contracts/loop_give/loop_give.calls.yaml` makes the loop of `GiveAll` pass `stop`.
4. Check the calls file with the seed:

   ```sh
   damlforge-fuzz run contracts/<seed> --compare --count 1
   ```

   `<seed>` is the folder of the seed.
   The run checks the calls file against the seed, and runs the calls on the seed itself.
   If the calls file does not fit the seed, or the Daml of the seed does not do what its `.vy` code does, the run prints one line to stderr and exits with 2.

### See a group again

Each group folder of a report has the first input of the group.
To see the group again, run `check` on the folder:

```sh
damlforge-fuzz check reports/<run>/groups/<group>
```

`<run>` is the name of the report folder, and `<group>` is the name of the group folder, such as `g01` or `l01`.
A folder argument also checks the shrunk input, and the copied sibling files of an import seed, such as `models.vy`.

- For a crash group (`g01`, `g02`, and so on), a loop group (`l01`), or an import group (`i01`), use `check`. With `--damlc`, the line also gives the verdict of `damlc`.
- For a bad Daml group (`d01`), use `check --damlc`. To see the `damlc` error without the fuzzer, run `dpm build` in the group folder.
- For a run group (`r01`), use `check --compare`.

To see what the Daml does, without the fuzzer, run `dpm test` in the run group folder.
The scripts that fail show the difference.
`dpm test` exits with 1, and its test summary has lines such as these:

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

### Shrink a file

`run` already shrinks the first input of each crash group, loop group, and import group.
Use `shrink` for another file that crashes forge, or that is `BAD_LOOP` or `BAD_IMP`, such as a file that you changed by hand:

```sh
damlforge-fuzz shrink my_input.vy
```

`shrink` writes the shrunk file to `shrunk/my_input.vy`, and prints it.
For any other file, `shrink` exits with 1 and writes nothing.
[How the shrinker works](#how-the-shrinker-works) tells how the shrinker works.

### Repeat a run

The same random seed and the same seed folders always give the same copies in the same order.
To repeat a run exactly, give its random seed and its number of inputs.
For example, this command repeats the 60-second run in [Quick start](#quick-start):

```sh
damlforge-fuzz run --count 81396 --random-seed 535031
```

Do not use `--seconds` to repeat a run.
The number of copies in a time limit changes with the speed of the machine.

`report.json` records the seeds of a run in `run.seeds`.
A run without `SEED_FOLDER` uses every seed in `contracts/`, so a new seed in `contracts/` changes the copies of such a run.
To repeat a run from before a seed was added, name the seeds of that run.
A change to the [change rules](#change-rules) also changes the copies.
To repeat a run from before such a change, use a commit from before it.

## Reference

The reference gives the commands, their output, and the files that they read and write.

### Commands

```
damlforge-fuzz check [--damlc] [--compare] PATH [PATH ...]
damlforge-fuzz run [SEED_FOLDER ...] (--seconds N | --count N) [--random-seed S] [--reports DIR] [--damlc] [--compare]
damlforge-fuzz shrink [--damlc] FILE
```

| Command | What it does |
| --- | --- |
| `check` | Compiles `.vy` files with `forge` and prints one result for each file. |
| `run` | Makes changed copies of the seeds, compiles each copy with `forge`, and writes a report. |
| `shrink` | Deletes lines of a `.vy` file while it still crashes in the same way, or still has the same loop bug or import bug. |

#### `damlforge-fuzz check`

`check` compiles each `.vy` file with `forge` and prints one line for each file.

| Argument | Meaning |
| --- | --- |
| `PATH` | A `.vy` file, or a folder. For a folder, `check` uses every `.vy` file under it. |
| `--damlc` | Also build the Daml of the `OK` files with `damlc`. See [Find Daml that damlc rejects](#find-daml-that-damlc-rejects). |
| `--compare` | Also run each `OK` file that has a calls file in Python and with Daml Script, and compare. See [Compare the Daml with the .vy code](#compare-the-daml-with-the-vy-code). |

Each line has the [result](#results), the [stage](#stages), and the file.
A `REJECTED`, `CRASH`, `BAD_DAML`, `BAD_LOOP`, `BAD_IMP`, or `BAD_RUN` line ends with the error.

#### `damlforge-fuzz run`

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
| `--damlc` | Also build the Daml of the `OK` copies with `damlc`. See [Find Daml that damlc rejects](#find-daml-that-damlc-rejects). |
| `--compare` | Also run the `OK` copies of the seeds that have a calls file in Python and with Daml Script, and compare. See [Compare the Daml with the .vy code](#compare-the-daml-with-the-vy-code). |

#### `damlforge-fuzz shrink`

`shrink` deletes lines of a `.vy` file that crashes forge or that is `BAD_LOOP` or `BAD_IMP`.
It writes the result to `shrunk/` next to FILE, with the same file name, and prints it.

| Argument | Meaning |
| --- | --- |
| `FILE` | A `.vy` file that crashes forge, or that has a loop bug or an import bug. |
| `--damlc` | For a `BAD_LOOP` or `BAD_IMP` file, also keep the verdict of `damlc` on the Daml. |

For a file that crashes forge, `shrink` keeps a deletion only when the file still crashes with the same exception at the same forge line.

For a `BAD_LOOP` or `BAD_IMP` file, `shrink` keeps a deletion only when forge still writes Daml and the first check of the [loop check](#loop-check) is the same.

With `--damlc`, `shrink` first builds the Daml of FILE with `damlc`.
Then it keeps a deletion only when `damlc` also gives the same verdict, `builds` or `rejects`.
With `--damlc`, `shrink` needs dpm, the Daml SDK, and a `daml.yaml` for FILE.
Each try that keeps the first check needs a `dpm build` of its Daml, about 0.7 seconds.
For a file that crashes forge, `--damlc` changes nothing.

### Output of run

This is the output of a run with `--damlc` and `--compare`:

```
$ damlforge-fuzz run contracts/loop_* --damlc --compare --count 2000 --random-seed 1
random seed 1, 5 seeds, 2000 inputs
random seed 1: 2000 inputs, 290 OK, 1207 rejected, 0 crash, 503 skipped
damlc: 141 Daml texts, 83 bad, 16 bad Daml groups
loops: 3 inputs with loop findings, 1 loop group, 0 build with damlc
compare: 145 inputs compared, 0 differ, 0 run groups
0 crash groups, report in reports/2026-10-28T11-07-26Z
```

The numbers depend on your DamlForge version.
Without `--damlc`, the run prints no `damlc:` line.
Without `--compare`, it prints no `compare:` line.

The first line prints when the run starts.
The second line prints when the run has made all the copies:

- `inputs`: the number of copies that the run made, including the skipped copies.
- `skipped`: copies whose changes left the text as it was. The run does not compile them.
- `OK`, `rejected`, and `crash`: the same [results](#results) as for `check`.

The `loops:` line gives the number of `OK` copies with a loop bug or an import bug, and the number of their groups.
[Loop check](#loop-check) tells what a loop bug is.
The last line gives the number of crash groups and the [report](#report-files) folder.

The `damlc:` line comes before the `loops:` line:

- `Daml texts`: the number of different Daml texts among the `OK` copies. Many copies give the same Daml, so the run builds each text only once.
- `bad`: the texts that `damlc` rejects.
- `bad Daml groups`: the number of groups of bad texts. Texts whose first `damlc` error is the same, after the names in the error are hidden, are one group.
  For example, `Variable not in scope: str : Int -> t` and `Variable not in scope: x : [a0]` are one group.
  So a group is one kind of `damlc` error, and it can hold more than one forge bug.

With `--damlc`, the `loops:` line also gives the number of loop groups whose Daml `damlc` builds.
[Loop check](#loop-check) tells more.

The `compare:` line comes after the `loops:` line:

- `inputs compared`: the `OK` copies of the seeds with a calls file whose calls ran in Python and in Daml. Many copies have the same text, so the run compares each text once.
- `differ`: the compared copies whose Daml does not do what the `.vy` code does in a call.
- `run groups`: the number of groups of these copies. Copies with the same kind of difference and the same first loop check are one group.

### Results

The first column of a `check` line is the result:

| Result | Meaning |
| --- | --- |
| `OK` | forge wrote Daml. |
| `REJECTED` | forge reported an error in the input, such as `DF1213`. |
| `CRASH` | forge failed with an error that is not its own. This is a bug in forge. The line ends with the exception and the forge file and line where it failed. |
| `BAD_DAML` | Only with `--damlc`. forge wrote Daml, but `damlc` rejects it. This is also a bug in forge. |
| `BAD_LOOP` | forge wrote Daml, but the [loop check](#loop-check) finds a wrong loop in it. This is also a bug in forge. With `--damlc`, the line ends with the verdict of `damlc`. |
| `BAD_IMP` | forge wrote Daml, but the import check, `I1` to `I4` in [Loop check](#loop-check), finds a wrong import in it. This is also a bug in forge. With `--damlc`, the line ends with the verdict of `damlc`. |
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
With `--damlc`, each `BAD_LOOP` or `BAD_IMP` line ends with the verdict of `damlc`.
A file with a loop bug is `BAD_LOOP`, not `BAD_DAML`, because the loop bug tells the cause.
The `damlc` error is usually a result of that cause, such as `Variable not in scope: foldlA` for `L1`.
`damlc builds` is the most serious case: forge wrote wrong Daml that compiles.

### Differences

The first call, in calls file order, whose scripts fail is the difference of the copy:

| Difference | Script that fails | Meaning |
| --- | --- | --- |
| `daml_fails` | `c1_runs` | Python runs the call, and Daml fails. |
| `result` | `c1_result` | Both run, and the results differ. |
| `contracts` | `c1_contracts` | Both run, and the results are the same, but the contracts that the call creates differ. |
| `daml_passes` | `c1_fails` | Python fails the call on an `assert`, and Daml runs it. |

The number in the script name is the place of the call in the calls file.
The run compares a contract ID in a result by its contract.

### Calls files

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

### Exit codes

| Code | `check` | `run` | `shrink` |
| --- | --- | --- | --- |
| `0` | Every file is `OK`. | No copy crashed, no Daml text is bad, and the report has no loop group, no import group, and no run group. | The command wrote the shrunk file. |
| `1` | A file is `REJECTED`, `CRASH`, `BAD_DAML`, `BAD_LOOP`, `BAD_IMP`, or `BAD_RUN`. | A copy crashed, a Daml text is bad, or the report has a loop group, an import group, or a run group. | FILE does not crash forge and has no loop bug or import bug. The command writes nothing. |
| `2` | Usage error. | Usage error. | Usage error. |
| `130` | — | You pressed Ctrl-C. See [Stop a run with Ctrl-C](#stop-a-run-with-ctrl-c). | You pressed Ctrl-C. The command writes nothing. |

A usage error prints one line to stderr.
These are the usage errors:

- For all commands: a missing path, a folder with no `.vy` file, a file that cannot be read, or DamlForge is not installed.
- With `--damlc`: a file with no `daml.yaml`, dpm or its SDK is missing, or dpm fails.
- With `--compare`: a calls file that does not fit its `.vy` file, a file with a calls file and no `daml.yaml`, dpm or its SDK is missing, or dpm fails. For `run`, also no seed with a calls file, or a seed whose Daml does not do what its `.vy` code does.
- For `run`: a `--reports` folder that cannot be made, a report that cannot be written, or a seed with a loop bug.
- For `shrink`: a FILE that is a folder, or a FILE that is already in a `shrunk/` folder.

### Stop a run with Ctrl-C

When you press Ctrl-C, the run stops the step that is running and continues with the next steps.
In each of these cases, the run writes the report and exits with 130:

| When you press Ctrl-C | What the run does |
| --- | --- |
| While it makes copies | Stops the copies. With `--damlc`, it still builds the Daml. With `--compare`, it still compares. It still shrinks. `report.json` has `"interrupted": true`. |
| While `damlc` builds | Keeps the texts that it built, and stops the `damlc` step. It still shrinks. The `damlc` entry in `report.json` has `"interrupted": true`. A loop group whose Daml `damlc` did not build has `"damlc": null`, and `report.md` shows `not built`. |
| While it compares | Keeps the batches of 100 copies that it compared, and stops the compare step. It still shrinks. The `compare` entry in `report.json` has `"interrupted": true`. |
| While it shrinks | Stops the shrinking. The groups that are not shrunk yet have `"shrunk": null`, and `report.md` shows `not shrunk`. A loop group that is not shrunk yet also has `"shrunk_daml": null`. |

### Report files

Every run writes a report folder in `reports/`.
The folder name is the UTC time when the run started, such as `reports/2026-10-20T07-52-29Z`.
If a folder with that name exists, the run adds `-2`, `-3`, and so on.
To put the report folders in a different folder, give `--reports DIR`.

Git does not ignore `reports/`.
Delete the report folders that you do not keep, or give `--reports DIR`.
The reports in git are in [`reports/`](reports/), with the analyses of the bugs that they found.

A report folder has these files.
The example is the report `reports/2026-10-19T18-45-34Z`.
Its `analysis.md` file and its `analysis/` folder are not part of the report. They were written by hand.

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

- `report.json` is the full report. It has the run settings, the DamlForge version in `run.forge_version`, the counts, the counts after each second of the run, and one entry for each group.
  A crash group entry has the exception, the forge file and line, the stage, the number of crashes, the first input that crashed, and the full text of that input.
  It also has the shrunk text in `"shrunk"` and the shrunk file in `"shrunk_file"`.
  The `damlc` entry has the counts and the time that `damlc` took. Without `--damlc`, `damlc` is `null`.
  A loop group entry has the first check of the group (`check`), every check of its first input (`checks`), the first bug (`message` and `daml_line`), the number of inputs, the first input, and the Daml that forge wrote for it.
  With `--damlc`, `damlc` is `builds` or `rejects`, and `damlc_error` is the first `damlc` error when `damlc` rejects the Daml. Without `--damlc`, both are `null`.
  A loop group entry also has the shrunk text in `"shrunk"` and its file in `"shrunk_file"`, and the Daml that forge wrote for the shrunk text in `"shrunk_daml"` and `"shrunk_daml_file"`.
  The `compare` entry has the counts of the compare step (`compared`, `skipped`, `dropped`, `differ`, and `skipped_calls`, the calls of the compared copies that were not compared) and its time. Without `--compare`, `compare` is `null`.
  A run group entry has the kind of the difference (`difference`), the call (`call`, such as `Iou.GiveAll #1`), the first loop check of its first input or `null` (`loop_check`), what Python does in the call (`python`), the number of inputs, the first input, the Daml that forge wrote for it, and its test module (`test`).
- `report.md` is a short summary of `report.json`.
  Its first lines give the random seed, the limit, the seeds, and the DamlForge version.
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

The report `reports/2026-10-19T18-45-34Z` is from before the loop check, so it has no loop group.
A loop group or import group folder has the first input, a copy of the seed's `daml.yaml` when the seed has one, and the Daml that forge wrote for the input.
Its `shrunk/` folder has the shrunk input and the Daml that forge wrote for it.
For example, this is the folder of an import group:

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
For example, this is the folder of a run group:

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

### Seeds

The seeds are in `contracts/`.
Each seed folder is its own Daml project, with a `daml.yaml` with `source: .`. Most have one `.vy` file. The three import seeds also have a sibling module, `models.vy`, which is a seed too.
The five loop seeds also have a [calls file](#calls-files) for `--compare`.
Separate projects let the fuzzer run on the seeds that you choose.

| Seed | Templates | Choices |
| --- | --- | --- |
| `contracts/asset_proposal/` | `Asset`, `AssetProposal` | `Give`, `Accept`, `Reject` |
| `contracts/ballot/` | `Ballot` | `CastVote`, `Close` |
| `contracts/escrow/` | `Payout`, `Escrow` | `Release`, `Refund` |
| `contracts/import_call/` | `Pot` | `Paid`, `Net` |
| `contracts/import_qualified/` | `Desk`; `Note` in `models.vy` | `Issue`, `Size` |
| `contracts/import_sibling/` | `Desk`; `Note` in `models.vy` | `Issue`, `Size` |
| `contracts/iou/` | `Iou` | `Transfer`, `Split` |
| `contracts/loop_count/` | `Iou` | `Count` |
| `contracts/loop_give/` | `Iou` | `GiveAll` |
| `contracts/loop_many/` | `Iou` | `Many` |
| `contracts/loop_pure/` | `Iou` | `Check` |
| `contracts/loop_verify/` | `Iou` | `Sum` |

## Change rules

For each change, the run picks one line and one of these rules, each with the same chance.
A word is a name, a number, or an operator.
A rule that does not fit its line, such as `operator` on a line with no operator, leaves the line as it was.
The first ten examples are real changes to `contracts/iou/iou.vy`, the next five are real changes to the loop seeds, and the last three are real changes to the import seeds.

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
| `import_module` | Changes the module of an import line at column 0: `.m`, `..m`, `pkg.m`, `forge.m`, or `ms`. | `import models as M` becomes `import forge.models as M` |
| `import_form` | Changes `from m import a, b` to `import m as A`, and each use `a` to `A.a`, or back. `A` is `M`, `m`, `Lib`, or none (`import m` and `m.a`). | `from models import Kind, Lot, Note, double` becomes `import models as M`, and `ContractId[Note]` becomes `ContractId[M.Note]` |

The rules take their new words from five lists in `src/damlforge_fuzz/mutate.py`: `_OPERATORS`, `_LITERALS`, `_TYPES`, `_EXPRESSIONS`, and `_STATEMENTS`.
Most rules change only their own line.
`inline_local` and `early_return` read the whole text, and `inline_var` and `import_form` also change other lines.
The five loop rules never take a string or a comment for code.

## How it works

This part tells how the fuzzer does its work, and what it cannot find.

### What a run does

A run has these steps:

1. Compile the unchanged seeds, and run the loop check on them. With `--damlc`, also build their Daml. With `--compare`, also run the calls of each seed that has a calls file.
2. Make the copies, and compile each copy with `forge`.
3. With `--damlc`, build the Daml of the `OK` copies.
4. With `--compare`, run the `OK` copies of the seeds with a calls file in Python and with Daml Script, and compare.
5. Shrink the first input of each crash group and each loop group.
6. Write the report.

How a run uses `damlc`:

- Before the first copy, the run builds the Daml of the unchanged seeds.
  If dpm or the SDK is missing, or the Daml of a seed does not build, the run prints one line to stderr and exits with 2.
- After the last copy, the run puts up to 500 Daml texts into one temporary Daml project, and runs one `dpm build` for them.
  A build of 500 texts takes about 5 seconds, so a 60-second run takes about 40 seconds more.
  The temporary projects are in your system's temporary folder, and the run deletes them.
- The run does not shrink the bad Daml inputs, because each try needs its own `dpm build`, which takes about 0.7 seconds.
- The run shrinks the loop groups so that each shrunk input keeps the verdict of `damlc`.
  This needs a `dpm build` for each new Daml text of a try, so each loop group takes about 3 to 10 seconds. [How the shrinker works](#how-the-shrinker-works) tells more.

How a run uses the loop check:

- Before the first copy, the run compiles the unchanged seeds and runs the loop check on them.
  A seed with a loop bug stops the run with exit code 2, because almost every copy would have the same bug.

- After the last copy, the run groups the `OK` copies with a loop bug.
  A copy goes to the group of its first check, so a run without `--damlc` has at most eight groups: four loop groups and four import groups.
  The `loops:` line comes before the last line.

- With `--damlc`, the run also splits the loop groups by the verdict of `damlc`.
  So a group whose Daml builds does not hide behind an earlier input whose Daml `damlc` rejects.
  The `loops:` line also gives the number of groups that build.

- After the crash groups, the run shrinks the first input of each loop group.
  [How the shrinker works](#how-the-shrinker-works) tells how.

### Limits of the loop check

The loop check has these limits:

- It reads the Daml in the layout that forge writes: one statement on each line, and `do` at the end of the line that opens a block.
  If forge changes its layout, the check can give wrong results.
- `L3` does not know whether the lost `return` changes the result. A lost `return` before code that does nothing is harmless.

### Why `--compare` is an option

- **It finds bugs that the other checks miss.** The loop check finds only the shapes of wrong loops that are known: `L1` to `L4`. `damlc` only tells whether the Daml builds. For b23, forge drops an `assert`, the Daml builds, and no loop check fails. Only a run of both programs on the same data shows that the Daml accepts a negative number that the `.vy` code rejects.
- **It is slow, and it needs dpm.** The compare step builds and tests the Daml with dpm, in batches of 100 copies. In one run of 5000 inputs on the loop seeds, the run took 3.3 seconds without `--compare` and 61 seconds with it. A plain run must stay fast and must work without the Daml SDK.
- **It is not part of `--damlc`.** `damlc` builds the Daml, and `--compare` runs it. They cost different amounts and answer different questions, so a run can use one of them or both. With both, the compare step uses the verdicts of `damlc` and does not build the Daml of the copies again.

### How a copy is compared

1. Python runs each call on the `.vy` code of the copy, with stand-ins for the names that forge gives meaning to.
2. `damlc` builds the Daml that forge wrote for the copy. With `--damlc`, the step uses the verdict that `damlc` already gave.
3. Daml Script runs each call that Python ran, with one script for each call. The run puts up to 100 copies into one temporary Daml project, with a test module for each copy, and runs `dpm build` and `dpm test` in it.
4. For each copy with a failed script, the run writes one script for each question and runs them again, so that the kind of the difference comes from which scripts fail.

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

`--compare` has these limits:

- The run does not shrink the run groups, because each try needs its own `dpm test`, about 4 seconds.
- The stand-ins do not cover every difference between Python and Daml. For example, Python computes a `Decimal` with 28 digits and an `int` with no limit. Daml rounds a `Decimal` to 10 decimal places, and fails on an `Int` that does not fit in 64 bits, also in the middle of a call. The run skips only a result that does not fit.
- A difference shows only when the data of a call makes it show. The `early_return` [change rule](#change-rules) inserts `if v == v:`, which is always true, so a lost `return` above a `create` changes nothing that a call can see.

### How the shrinker works

The seeds have 9 to 42 lines, and a crashing input has about as many as its seed.
Usually only a few of these lines cause the crash.
After the last copy, the run shrinks the first input of each crash group:

1. The shrinker deletes lines, first in large blocks, then one line or one indented block at a time.
2. It keeps a deletion only when the text still crashes with the same exception at the same forge line.
3. It stops when it cannot delete one more line.

The shrunk input has only lines of the full input, in the same order, and no line is changed.

Then the run shrinks the first input of each loop group in the same way.
It keeps a deletion only when forge still writes Daml and the first check of the [loop check](#loop-check) is the same.
With `--damlc`, it also keeps a deletion only when `damlc` gives the same verdict on the Daml, `builds` or `rejects`.
Without that, a group whose Daml builds can get a shrunk input whose Daml `damlc` rejects.

With `--damlc`, each try that keeps the first check needs a `dpm build` of its Daml, about 0.7 seconds, unless an earlier try had the same Daml.

For a group whose Daml `damlc` rejects, the shrunk input keeps the verdict, but not the error.
`damlc` can reject the shrunk Daml for another reason.

The shrunk input is in `shrunk/` in the group folder, with the same file name as the full input.
The same file name keeps the Daml module name.
The shrunk file uses the `daml.yaml` of the group folder.
The `shrunk/` folder of a loop group also has the Daml that forge wrote for the shrunk input.

### Why the seeds look as they do

Two kinds of seeds have a special form.
These are the import seeds and the loop seeds.

#### Import seeds

The `contracts/import_*` seeds test forge's imports between `.vy` files.
In each folder, the main file imports from `models.vy`, the file next to it.
`import_sibling.vy` and `import_qualified.vy` import a template, a struct, an enum, and a function: `import_sibling.vy` with `from models import Kind, Lot, Note, double`, and `import_qualified.vy` with `import models as M` and `M.Note`.
`import_call.vy` imports only two functions, with `from models import double, fee`, and uses no type from `models.vy`.
When the `import_form` rule changes its import to `import models`, each call becomes `models.double(...)`, which shows b33.
In the other two seeds, the same change also makes a type such as `models.Note`, and forge rejects it (b32) before it gets to a call.
forge reads the sibling file from the disk, so a change to the main file is compiled against the unchanged `models.vy`.
The import seeds use no qualified enum value, such as `M.Kind.CASH`, because forge rejects it (b31 in `reports/2026-10-26T07-07-10Z/analysis/imports/`).

#### Loop seeds

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

## Development

This part is for contributors.
Install damlforge-fuzz as [Install](#install) shows. The `test` extra installs pytest.

### Run the tests

```sh
pytest
```

The tests that need dpm skip when dpm or the Daml SDK is missing.

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
5. Optional: to compare the copies of the seed with `--compare`, [write a calls file](#write-a-calls-file) for it.

A seed that fails a check is a bug in the seed.
Fix the seed before you use it, so that every crash that the fuzzer finds comes from an edit and not from the seed.

A seed with a `for` loop has two more rules:

- At most one loop in the file has a ledger action, such as `create` or `fetch`. [Loop seeds](#loop-seeds) tells why.
- No loop uses the code of a known forge loop bug in `reports/2026-10-20T16-34-28Z/analysis/loops/`. Some of these bugs, such as a `return` in a loop that creates a contract, give Daml that `damlc` builds, so the two checks do not find them. On a DamlForge that has such a bug, the [loop check](#loop-check) finds it. Then `damlforge-fuzz check` prints `BAD_LOOP` for the seed, and `damlforge-fuzz run` stops before the first copy.

### Add a word or a rule

> [!IMPORTANT]
> Every change to the rules or the word lists changes some copies of every random seed.
> So a result from before the change and a result from after it do not use the same copies.
> Say so in the commit message.

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
   A rule in the first place or in the middle changes many more copies of every random seed than a rule in the last place.
3. Add a row for the rule at the end of the table in [Change rules](#change-rules).
   A test checks that the table and `_RULES` list the same rules in the same order.
4. In `tests/test_mutate.py`, add a test that applies the rule to a short text and compares the result with the exact text that it must give.
5. Run `pytest`.
6. Compare the rules with and without the new rule:

   ```sh
   python scripts/compare_rules.py contracts/loop_* --count 5000 --random-seed 1 2 3 --leave-out your_rule
   ```

   For each set of rules, the script counts the `OK` inputs and the loop findings by first check.
   Leaving out a rule also changes the rules that the run picks for the other changes, so a small difference can be chance.

### Show the inputs of a run

To see each copy, its changes, and its result, run `scripts/show_inputs.py`:

```sh
python scripts/show_inputs.py contracts/iou --count 5 --random-seed 1
```

The script makes the same copies as `damlforge-fuzz run` with the same seed folders and random seed.

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
│   ├── importcheck.py    the import check: finds wrong imports in forge's Daml
│   └── compare.py        runs an input in Python and with Daml Script, and compares
├── tests/                pytest tests, and in tests/loops/ the saved .vy and Daml pairs of the loop check
├── scripts/
│   ├── show_inputs.py    prints each copy of a run, its changes, and its result
│   └── compare_rules.py  compares sets of change rules by what the loop check finds
├── contracts/            the seeds, one Daml project for each seed, and the calls files
├── reports/              the reports that are kept in git, with the analyses of the bugs that they found
├── ISSUES.md            the DamlForge issues that the work found, with their status
└── pyproject.toml
```

`compiler.py` is the only module that imports forge.
`mutate.py`, `damlc.py`, `loopcheck.py`, `importcheck.py`, and `compare.py` do not import forge.

If you change the text of a stage in [Stages](#stages), also change `STAGE_TEXT` in `src/damlforge_fuzz/compiler.py`.
`report.md` uses the texts in `STAGE_TEXT`.
The table in [Loop check](#loop-check) has the texts of `LOOP_CHECK_TEXT` in `src/damlforge_fuzz/loopcheck.py`, which `report.md` also uses. A test checks that the two are the same.

## License

damlforge-fuzz is licensed under the [Apache License, Version 2.0](LICENSE).

Copyright 2026 Noders Team. Author: Ruslan Glaznyov <ruslan.glaznyov@gmail.com>.
