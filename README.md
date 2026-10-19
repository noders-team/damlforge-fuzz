# damlforge-fuzz

damlforge-fuzz is a fuzzer for the DamlForge compiler, `forge`, which compiles `.vy` files to Daml.
The fuzzer takes a few seed contracts, makes small random edits to them, runs `forge` on each edited copy, and reports crashes.

**Status.** This is unit 3. The `damlforge-fuzz check` command compiles `.vy` files and sorts each result. The `damlforge-fuzz run` command makes random edits to the seeds and counts the results. Crash reports come next.

For a step-by-step guide with real command output, open [`docs/guide.html`](docs/guide.html) in a browser.
The plan for units 2 to 6 is in [`docs/plan.html`](docs/plan.html).
[`docs/progress.md`](docs/progress.md) records where the work stands and what comes next.

## Layout

```
damlforge-fuzz/
├── README.md
├── .gitignore
├── pyproject.toml
├── src/damlforge_fuzz/     the Python package and the damlforge-fuzz command
├── tests/                  pytest tests
└── contracts/              one folder per seed, each its own Daml project
    ├── asset_proposal/
    │   ├── asset_proposal.vy
    │   └── daml.yaml       Daml SDK 3.5.2, package damlforge-fuzz-asset-proposal
    ├── ballot/
    ├── escrow/
    └── iou/
```

Every seed folder has one `.vy` file and a `daml.yaml` with `source: .`.
Separate projects let the fuzzer run on the seeds you choose.

## Install DamlForge

DamlForge needs Python 3.11 or newer.
Install it into a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
```

Do not run `pip install forge`.
The `forge` package on PyPI is a different project, a Django tool.

The DamlForge repository, `noders-team/damlforge`, is private.
To use the release wheel or the git install, you need GitHub access to that repository.
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

  While this folder is inside the DamlForge repository, the checkout is the parent folder, so run `pip install -e ..`.

To check the install, run `forge --help`.
The output lists the `daml`, `dar`, `json`, and `stubs` commands.

## Install dpm and the Daml SDK

dpm is the Daml package manager.
It installs the Daml SDK, which has the `damlc` compiler.
Only the second check in [Check the seeds](#check-the-seeds) needs dpm.

```sh
curl -sSL https://get.digitalasset.com/install | sh
dpm install 3.5.2
```

If your shell does not find `dpm` after the install, add `~/.dpm/bin` to your `PATH`.
`forge dar` looks for `dpm` on your `PATH` and then in `~/.dpm/bin`.
These commands are the same as in `.devcontainer/post-create.sh` in the DamlForge repository.

## Use

Install the fuzzer into the virtual environment that has DamlForge.
Run the commands from this folder.

```sh
pip install -e ".[test]"
```

`damlforge-fuzz check` compiles each `.vy` file with `forge` and prints one line per file.
A folder argument means every `.vy` file under it.

```
$ damlforge-fuzz check contracts
OK       emit   contracts/asset_proposal/asset_proposal.vy
OK       emit   contracts/ballot/ballot.vy
OK       emit   contracts/escrow/escrow.vy
OK       emit   contracts/iou/iou.vy
$ damlforge-fuzz check bitand.vy
CRASH    lower  bitand.vy  KeyError 'BitAnd' at forge/ir/lower.py:289
```

`bitand.vy` has two lines, `def f(count: int) -> int:` and `    return count & 1`.
forge has no entry for `&` in its table of operators.
The forge line depends on the forge version: it is `forge/ir/lower.py:244` in DamlForge `v0.0.7` and `forge/ir/lower.py:289` in `v0.0.10`.

The first column is the result:

- `OK`: forge wrote Daml.
- `REJECTED`: forge reported an error in the input, such as `DF1213`.
- `CRASH`: forge failed with an error that is not its own. This is a bug in forge, and the line ends with the forge file and line where it failed.

The second column is the forge step that was running: `parse`, `check`, `lower`, or `emit`.
The command exits with 0 when every file is `OK`, 1 when any file is `REJECTED` or `CRASH`, and 2 for a usage error, such as a missing path.

`damlforge-fuzz run` makes changed copies of the seeds and compiles each copy with `forge`.
Each copy starts from one seed and gets 1 to 4 random changes.
Give a time limit with `--seconds` or a number of copies with `--count`.
Without a folder argument, the run uses every seed in `contracts/`.

```
$ damlforge-fuzz run --seconds 60
random seed 202216, 4 seeds, 60 seconds
random seed 202216: 68222 inputs, 12625 OK, 46725 rejected, 3902 crash, 4970 skipped
$ damlforge-fuzz run contracts/iou --count 2000 --random-seed 1
random seed 1, 1 seed, 2000 inputs
random seed 1: 2000 inputs, 338 OK, 1388 rejected, 111 crash, 163 skipped
```

This output is from DamlForge `v0.0.7`. Another forge version gives other counts.
The first line prints when the run starts. The second line prints when it ends.

- `inputs`: the number of copies the run made, including the skipped copies.
- `skipped`: copies whose changes left the text as it was. The run does not compile them.
- `OK`, `rejected`, and `crash` mean the same as for `check`.

The random seed decides every copy and its changes.
Without `--random-seed`, the run picks a new one and prints it.
The same random seed and the same seed folders always give the same copies in the same order.
To repeat a run exactly, pass its random seed and its number of inputs, for example `--count 68222 --random-seed 202216`.
A second `--seconds` run can make a different number of copies, because the speed of the machine changes.

The command exits with 0 when no copy crashed, 1 when any copy crashed, 2 for a usage error, and 130 when you press Ctrl-C.

To see each copy, its changes, and its result, run `python scripts/show_inputs.py contracts/iou --count 5 --random-seed 1`.
It makes the same copies as `damlforge-fuzz run` with the same folders and random seed.

To run the tests, run `pytest`.

## Change rules

For each change, the run picks one line and one of these rules, each with the same chance.
A word is a name, a number, or an operator.
A rule that does not fit its line, such as `operator` on a line with no operator, leaves the line as it was.
The examples are real changes to `contracts/iou/iou.vy`.

| Rule | What it does to the line | Example |
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

The rules take their new words from five lists in `src/damlforge_fuzz/mutate.py`: `_OPERATORS`, `_LITERALS`, `_TYPES`, `_EXPRESSIONS`, and `_STATEMENTS`.

### Add a word or a rule

Every change to the rules or the word lists changes some copies of every random seed.
So a result from before the change and a result after it do not use the same copies.
Write the change in `docs/progress.md`.

To add a word, add it at the end of its list in `mutate.py`.

To add a rule:

1. In `mutate.py`, write a function that takes `(rng, line, ctx)` and returns the lines that replace `line`.
   Return `[]` to delete the line, `[new_line]` to change it, or `[inserted_line, line]` to insert a line above it.
   Return `None` when the rule does not fit the line.
   Use `rng` for every random choice. `ctx.lines` is the whole text, and `ctx.donor_lines` holds the lines of all the run's seeds.
2. Add a row `_Rule("your_rule", your_function)` at the end of `_RULES`.
   Do not put it first or in the middle.
   In a test, a rule added last kept 1608 of the first 2000 copies the same, and the same rule added first kept 86.
3. Add a row for the rule to the table above. A test checks that the table and `_RULES` list the same rules in the same order.
4. Run `pytest`.

A rule can change only its own line. It cannot, for example, swap two lines.

## Check the seeds

Every seed must pass two checks.
Run both from this folder.
Each command below runs the check on every seed folder and stops at the first seed that fails.

1. Compile the seeds to Daml with `forge`:

   ```sh
   for p in contracts/*/; do forge daml --no-i "$p" -o "build/daml/$(basename "$p")" || break; done
   ```

   For each seed, this writes a `.daml` file to `build/daml/<seed>/`, such as `build/daml/iou/Iou.daml`.
   Keep `--no-i`. Without it, `forge daml` logs an error for a broken seed but still exits with code 0.

2. Build the seeds with `damlc`:

   ```sh
   for p in contracts/*/; do forge dar "$p" -o "build/$(basename "$p").dar" || break; done
   ```

   For each seed, `forge dar` compiles the seed again, writes the `.daml` file next to it, such as `contracts/iou/Iou.daml`, and runs `dpm build`.
   It writes one `.dar` file for each seed to `build/`, such as `build/iou.dar`.
   Git ignores the generated files.

To check one seed, run the command inside a loop by hand, for example `forge dar contracts/iou -o build/iou.dar`.

## Add a seed

1. Make a folder for the seed in `contracts/`, for example `contracts/vault/`.
2. Copy `contracts/iou/daml.yaml` into the new folder and change its `name` line to `damlforge-fuzz-vault`.
3. Put the `.vy` file in the new folder.
4. Run both checks in [Check the seeds](#check-the-seeds).

A seed that fails a check is a bug in the seed.
Fix the seed before you use it, so that every crash the fuzzer finds comes from an edit and not from the seed.

## Move this folder to its own repository

From the root of the DamlForge repository, copy this folder and its history to a new branch:

```sh
git subtree split --prefix=damlforge-fuzz -b damlforge-fuzz
```

The `damlforge-fuzz` branch has only the files of this folder, at its root.
Push that branch to the new repository:

```sh
git push <new-repository-url> damlforge-fuzz:main
```

After the move, `pip install -e ..` no longer finds DamlForge.
Use the path to your DamlForge checkout instead.
