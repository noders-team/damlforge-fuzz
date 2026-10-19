# damlforge-fuzz

damlforge-fuzz is a fuzzer for the DamlForge compiler, `forge`, which compiles `.vy` files to Daml.
The fuzzer takes a few seed contracts, makes small random edits to them, runs `forge` on each edited copy, and reports crashes.

**Status.** This is unit 2. The `damlforge-fuzz check` command compiles `.vy` files and sorts each result. The random edits come next.

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
$ damlforge-fuzz check floordiv.vy
CRASH    lower  floordiv.vy  KeyError 'FloorDiv' at forge/ir/lower.py:244
```

The first column is the result:

- `OK`: forge wrote Daml.
- `REJECTED`: forge reported an error in the input, such as `DF1213`.
- `CRASH`: forge failed with an error that is not its own. This is a bug in forge, and the line ends with the forge file and line where it failed.

The second column is the forge step that was running: `parse`, `check`, `lower`, or `emit`.
The command exits with 0 when every file is `OK`, 1 when any file is `REJECTED` or `CRASH`, and 2 for a usage error, such as a missing path.

To run the tests, run `pytest`.

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
