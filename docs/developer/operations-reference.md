# goPilot operations reference

Detailed operating contracts moved verbatim from the repository [README](../../README.md) when it was shortened.
The standalone HTML environment, also formerly in the README, is documented in the
[developer and operation guide](cli.mdx#standalone-html-environment); references to it "below" point there.

## Configuration and operation boundaries

Provider configuration comes from `OPENAI_API_KEY` in the runtime environment. The provider-aware `main.py` entry rejects a missing/blank value before context generation or manager construction. The separate context export command below needs no provider configuration. No key value belongs in source, documentation or design artifacts. Removal from the current file does not erase Git history or rotate a credential.

The launchers resolve helpers and default `goHelpers/results` outputs relative to this checkout, preserving paths containing spaces. `bash ezRun.sh --help` and `bash goHelpers/all_run.sh --help` exit successfully without running helpers or creating outputs. Unknown/missing/positional arguments and non-boolean flag values and nonexistent/non-directory context targets fail before those operations. The wrapper always launches the provider-aware helper for valid operational arguments; all boolean flags set to false do **not** make a dry run. `-d` selects context while Go commands retain the caller's current directory; the code runner still expects that project's `localtest/run/run.go`.

`-a true` reaches provider-account file enumeration/deletion, broader than local thread-text cleanup. It requires explicit authorization for that account and exact scope. Normal manager construction and upload can also create/update/delete provider objects; do not execute these for a configuration or documentation audit.

`-x true/false` controls thread-text cleanup and defaults true. Cleanup and external checks happen only after successful helper execution; a helper failure is returned unchanged. Go check failures still reach error parsing, and parser failures return a nonzero status. The error parser reads the selected report first, then supplies its own helper directory to the manager. These launcher fixes establish no current provider/SDK compatibility.

## Standalone Go context export

From the repository root, export analysis context using the Python standard library:

```bash
python3 -B goHelpers/exportContext.py SOURCE NEW_OUTPUT_DIR
```

Quote paths containing spaces, for example `python3 -B goHelpers/exportContext.py '/path/Go project' '/path/exports/fresh context'`. The source and output parent must be existing directories. The output must be a new directory outside the resolved source tree: existing files, directories and symlinks, including dangling links, are rejected. Resolving parent symlinks also prevents choosing an output inside the source through another path. The command creates its destination exclusively with mode 0700 on POSIX and writes no generated files into the source.

The export contains UTF-8 `<package>_go.txt` analysis files, `package_map_context.txt`, `directory_tree.txt`, `directory_tree_updated.txt` and `projectDirectoryTree_context.txt`. The tree header lists the packages actually discovered. Tree entries follow the source hierarchy with deterministic directories-first, then files ordering and branch markers that show ancestor continuation and each last sibling. Directory symlinks are explicitly labeled as leaf entries and are not followed. Display labels escape backslashes and control characters while preserving readable Unicode and spaces.

The package map provides authoritative root-relative source paths and generated package filenames. The suffix-updated tree retains the same hierarchy with terminal `.go` file suffixes displayed as `_go.txt`; it does not imply a separate generated output for every source file. Escaped tree labels do not change source identity in the map. Analysis text is not guaranteed to compile, and the tree is not an atomic snapshot of changing source.

The command needs no provider key, dependency installation or Go executable, and performs no provider operations. `--help` returns 0 without creating output. A complete export returns 0 and prints only its destination path to stdout. Invalid arguments, read/walk failures, publication or later output-write failures, and no eligible packages return 1 with a bounded single-line error on stderr. A failure after creating the fresh directory retains and reports that incomplete directory; it does not replace an older export. Exporting does not provide an atomic snapshot of a changing source tree, preserve source metadata, guarantee crash durability or establish Windows permission behavior.

This is a separate entry from the provider-aware launchers. Their key requirement and existing provider workflow remain unchanged. The [export tests](../../tests/test_export_context.py) exercise the standard-library CLI in isolated temporary projects, deterministic multi-package Unicode output, source and prior-artifact preservation, destination rejection and read/publication failures. Injected walk/later-write failures and a simulated case-folding collision check cover additional failure paths. These tests establish no provider acceptance or native Windows permission behavior.

## Standalone executable and local installation

Build a single-file executable from this checkout using only the Python standard library:

```bash
python3 -B goHelpers/buildContext.py NEW_OUTPUT_FILE
```

Choose a fresh output outside the resolved checkout, with an existing parent directory. Every existing destination entry, including a dangling symlink, is rejected. The builder embeds exactly three unchanged helper modules (`exportContext.py`, `getter.py`, `directoryTree.py`), `__main__.py` as its bootstrap and `manifest.json` as its source-hash manifest. Fixed archive ordering, timestamps, modes and uncompressed entries make identical source bytes produce identical archives. The manifest records source-byte identity; it is not a signature or proof of publisher authenticity.

The archive starts with `#!/usr/bin/env -S python3 -I -B -S`. Its initial target is Linux with CPython 3.10 and GNU `env` supporting `-S`; it still needs a compatible Python interpreter on PATH. It runs without the source checkout, a virtual environment, installed dependencies, provider keys or Go tools. [Python's zipapp documentation](https://docs.python.org/3.10/library/zipapp.html) describes this single-file Python distribution model.

The builder fully writes and closes a private sibling staging file with POSIX mode 0700, publishes through an exclusive hard link without replacing the destination, then removes its owned staging entry. Success returns 0 and prints only the executable path. Build failures return 1 with a bounded one-line error; if publication or staging cleanup has already occurred, diagnostics distinguish the published artifact and any retained staging file. Source files and prior artifacts are not replaced. This publication contract does not guarantee crash durability or platform-independent hard-link behavior.

For a candidate user-local installation, after source/artifact qualification, choose a new owned command name in an existing external directory:

```bash
python3 -B goHelpers/buildContext.py "$HOME/.local/bin/gopilot-context"
"$HOME/.local/bin/gopilot-context" --help
"$HOME/.local/bin/gopilot-context" SOURCE NEW_OUTPUT_DIR
```

An existing command is never overwritten by this builder. Verify the installed archive's hash and executable behavior against the qualified artifact before recording deployment. Any rollback must remove only the owned artifact after confirming its exact bytes. These commands describe the installation workflow; they do not establish that local deployment or executable readback has occurred. The archive preserves the standalone export's fresh-directory, output and failure contracts above; provider migration remains separate.

## Offline verification

Run these checks from the repository root. Shell syntax validation does not execute the wrappers, and the Python suite uses synthetic inputs without contacting a provider:

```bash
bash -n ezRun.sh goHelpers/all_run.sh
python3 -B -m unittest discover -s tests -v
```

The suite combines selected AST checks for runtime configuration/startup ordering with actual offline helper execution: [getter tests](../../tests/test_getter.py) import the context consolidator and [thread-parser tests](../../tests/test_chat_parse.py) import the link parser, using temporary files to check outputs and input preservation. [Launcher tests](../../tests/test_launchers.py) execute copied actual scripts with inert Python/Go/lint command adapters; [error-parser tests](../../tests/test_error_parser.py) execute its actual entry using a fake manager module. These check routing, help/validation, failure ordering and helper/report separation. The suite does not import provider-aware `main.py`, initialize an actual assistant client, run real Go checks or qualify SDK/file-upload integration. Make target execution is explicitly skipped if Make is unavailable; it requires separate qualification in an environment with Make.

In the shared native WSL workspace, coordinate with the existing verification owner and inspect jobs in sibling worktrees before running the suite. Use the shared gate (a local lock wrapper on that workspace's PATH) instead of the direct Python command above:

```bash
agent-heavy-check -- python3 -B -m unittest discover -s tests -v
```

Run the gate in the foreground. Admission exit 75 means the suite did not run; report the contention instead of repeatedly queueing an unchanged check or bypassing the gate. See the [operation guide](cli.mdx) for verification boundaries. The legacy helper Makefile's `install` target installs unpinned provider and other Python dependencies into its selected environment. Use the separate HTML environment below for standalone fetching. `all_run.sh` is maintained source: `create_script` checks its presence and `clean` preserves it; neither regenerates nor deletes the tracked wrapper.

## License and provenance

The repository has no license file identified in this snapshot. Existing source and the original README remain the attribution/provenance reference; this documentation adds no license grant.

## External project links

[Documentation canvas](https://superdesign.dev/teams/daa6c1df-346f-4dc3-81dd-fb4f462aff90/projects/8ddc6d31-cab0-4a6a-b18e-706f0bf43ef2) · [Linear project](https://linear.app/jckail/project/gopilot-25d280e3a6b1)
