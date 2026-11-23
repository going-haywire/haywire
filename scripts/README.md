# scripts/

Maintenance scripts run by humans or CI.

| Script                      | Purpose                                                              |
| --------------------------- | -------------------------------------------------------------------- |
| `bump_version.py`           | Bump every Tier 1+2 package to a new lockstep version.               |
| `check_release_versions.py` | Verify every package (and its `haybale.toml`) agrees on one version. |
| `check_deps.py`             | Audit declared vs. imported deps per package (wraps `deptry`).       |
| `generate_marketstall.py`   | CI marketstall generator for the published packages.                 |
| `worktree_setup.py`         | Ready a new git worktree: branch, links, environment, studio port.   |
| `release_sweep.py`          | Report what a release means for the organisation's libraries.        |
| `finish.py`                 | Delete a merged branch's local and remote branch and its worktree.   |
| `tasks.py`                  | List the tasks in flight: worktrees, their PRs and agent sessions.   |

`worktree_setup.py`, `finish.py` and `tasks.py` are links to the copies in `dev/scripts/`, which the org's library
repositories reach through the core clone beside them; edit them there.

`worktree_setup.py` runs with the system Python (`python3 scripts/worktree_setup.py`),
before the worktree has an environment; the [workflow](../docs/collaboration/workflow.md), *Parallel sessions*,
says when.

## bump_version.py

```bash
# Preview what would change.
uv run python scripts/bump_version.py 0.0.2 --dry-run

# Apply (never prompts).
uv run python scripts/bump_version.py 0.0.2
```

Reads `[tool.haywire.release]` in the workspace root `pyproject.toml` for the canonical
package list. To add or remove a publishable package, edit that block — not the script.

`pyproject.toml` is canon for `version`; any package that also carries a `haybale.toml`
(the runtime-read copy `LibraryIdentity` loads) gets that file's `version` line synced
too, so the two never disagree after a release.

## check_release_versions.py

```bash
# Lockstep + haybale.toml sync check against whatever is committed.
uv run python scripts/check_release_versions.py

# Require an exact version (what CI does, using the tag being built).
uv run python scripts/check_release_versions.py --expect 0.0.2
```

The read-back for `bump_version.py`'s write. Asserts that every package in
`[tool.haywire.release]` declares the same `[project] version`, and that every
`haybale.toml` matches its own `pyproject.toml`. Exits 1 and lists each
disagreeing file otherwise — unlike `check_deps.py`, this one *is* a gate.

Both publish workflows run it before building any wheel, with `--expect` set
from the tag. Without it, tagging without having run the bump produces a green
run that publishes nothing: the publish job reads each version from
`pyproject.toml`, finds the previous release already on PyPI, and skips every
package as "already published".

## check_deps.py

```bash
# Audit every package in [tool.haywire.release].
uv run python scripts/check_deps.py

# Audit a single package.
uv run python scripts/check_deps.py haywire-core
```

Wraps `deptry`, running it once per package with a dist→module name map so
inter-package deps aren't mis-flagged. Reports three classes: MISSING (imported but
undeclared — can break a standalone PyPI install), UNUSED (declared but unused), and
NOT INSTALLED (imported but absent). Always exits 0 — it's a report, not a gate. The
`/release` skill runs it at Step 2.5. Known false positives (e.g. `attrs` as a
transitive of `cattrs`) are suppressed via the `KNOWN_OK` map in the script.

## generate_marketstall.py

```bash
# Print the generated marketplace to stdout.
uv run python scripts/generate_marketstall.py

# Write to a file (used by the publish workflow).
uv run python scripts/generate_marketstall.py --out dist/marketplace.toml
```

Reads `[tool.haywire.release].publish_order` and `[tool.haywire.marketstall]` from
the workspace root `pyproject.toml`. For each publishable package, lifts
`label` / `description` / `author` / `tags` from the package's `@library`
decorator and falls back to the pyproject `description` and `[tool.haywire.marketstall]`
defaults when the decorator omits a field.

The output is deployed to GitHub Pages on every release tag by
`.github/workflows/publish.yml`. Subscribers fetch it from
`https://going-haywire.github.io/haywire/marketplace.toml`.

## release_sweep.py

```bash
# Before the bump: Author API names HEAD removes or deprecates against the last tag,
# the haybale-* repositories that import them, and their imports of internal modules.
uv run python scripts/release_sweep.py names

# After the publish: open after-core-release reminders, and whether the tag contains
# the commit on each one's "Waits for:" line.
uv run python scripts/release_sweep.py reminders --ref v0.5.0
```

Both take `--json`. Read-only: it shallow-clones the libraries into a temporary folder
and writes nothing on GitHub. Needs `git` and a logged-in `gh`; exit code 2 means a
command failed and the report could not be made. `/release` runs it in Steps 2.2
and 10; the convention it reads is in
[sharing-libraries §7.1](../docs/guides/sharing-libraries.md#71-release-reminders).

## finish.py

```bash
# After the PR merged: delete the local and remote branch, and the worktree.
uv run python scripts/finish.py fix/edge-drag
uv run python scripts/finish.py fix/old-idea --abandon   # PR closed without a merge (the user's word)

# Leftovers across the clone: list, then clean what is merged.
uv run python scripts/finish.py --sweep
uv run python scripts/finish.py --sweep --yes [--abandon]
```

The only way agents delete branches: the hook blocks the raw local and remote deletions.
It refuses unless the branch's PR is merged (or closed, with `--abandon`) and the local
branch holds nothing the PR's head lacks. Inside the branch's worktree it detaches the
folder at `master`; from another folder it removes a clean worktree. A contributor's
clone reads the PR on `upstream` and deletes on the fork (`origin`). Running it again is
a no-op. Output is `key: value` lines (`--json` for one object); exit 1 means refused or
failed. Needs `git` and a logged-in `gh`.
