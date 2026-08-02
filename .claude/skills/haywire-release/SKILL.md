---
name: haywire-release
description: >
  Walk the author through cutting a release of the haywire monorepo. Runs the
  gate tests, bumps every Tier 1+2 package to a new lockstep version (via
  scripts/bump_version.py), shows a unified diff of every change, then on
  confirmation commits with `chore: release vX.Y.Z`, tags `vX.Y.Z`, then hands the
  user the `git push` command to run themselves (a local hook blocks the skill from
  pushing) so the publish CI workflow takes over. Supports `--dry-run` to
  preview the flow without committing. Use this skill whenever the user wants
  to cut, ship, publish, release, or version-bump the monorepo. Trigger
  phrases: "/haywire-release", "cut a release", "ship a release", "release
  haywire", "bump versions and tag".
---

# `/haywire-release`

Operator's playbook for cutting a release of the haywire monorepo's Tier 1+2 packages.
Composes the existing tools (`scripts/bump_version.py`, `scripts/check_deps.py`,
`git`, `gh`) into the release flow documented in
[`docs/reference/publish_releases.md`](../../../docs/reference/publish_releases.md).

## When to use

- The user says "let's cut a release", "release v0.0.2", "bump versions", or invokes
  `/haywire-release` directly.
- The user has finished merging changes for the next release and the working tree on
  `main` is clean.

Do **not** run if the working tree has uncommitted changes — the release flow needs to
commit only its own version bump. If there are pending changes, ask the user to stash
or commit them first.

## Inputs

- **Target version** (required, e.g. `0.0.2`) — the new lockstep version. Asked
  interactively if not supplied on the invocation line.
- **`--dry-run`** (optional) — perform every step *except* commit/tag/push. The bump
  is applied to the working tree so the user can `git diff` to inspect, then roll
  back with `git checkout .` if abandoning.

## Procedure

The procedure runs in the steps below (mirroring spec § release flow § local), with
a non-blocking dependency audit at Step 2.5. Each step includes the exact command to
run, what to expect, and what to do on failure.

### Step 0 — show the current release version

Read the version from `packages/haywire-core/pyproject.toml` (foundation package; always
at the lockstep version):

```bash
grep -E '^version = ' packages/haywire-core/pyproject.toml | head -1
```

Expected output line: `version = "X.Y.Z"`.

Tell the user:

> Current release version: **X.Y.Z**

If the file is missing or the line isn't found, the workspace layout has changed.
Stop and ask the user.

### Step 1 — get the new release version

If the user supplied a version on the invocation line (e.g. `/haywire-release 0.0.2`),
use it. Otherwise ask via `AskUserQuestion`:

> "New release version? Current is X.Y.Z. Use semver (patch / minor / major)."

Validate the input against the regex `^\d+\.\d+\.\d+(?:[a-z0-9.+!*-]*)?$` (PEP 440-ish:
`X.Y.Z` with optional pre/post/dev suffix). Reject and re-prompt on malformed input.

Also reject if the new version equals the current version — the bump script would
report "Nothing to do" and the release would be a no-op.

- **At `0.1.0`: revisit every published framework floor.** `~=0.0.X` specifiers
  in the wild exclude `0.1.0` by construction. Every haybale published with a
  compatible-release requirement will stop being installable on the new
  framework unless its author republishes with a widened specifier. Announce it
  and sweep the in-repo barns before tagging.

### Step 2 — run the gate tests

```bash
uv run pytest -m "not integration" -q
```

Expected: all tests pass (current baseline: 1156 passed). If anything fails, STOP. Show
the failures to the user and do not proceed — releases must not ship on a red gate.

Then run the ruff gate — **both** the linter and the formatter check. The release
commit (`chore: release vX.Y.Z`) is pushed to `master`, where the separate
`ruff.yml` workflow runs `ruff check .` AND `ruff format --check .`. If either fails,
the release commit lands red on `master`. Catch it here, before committing:

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: `All checks passed!` and `N files already formatted`. If `ruff format --check`
reports `Would reformat: <file>`, STOP. Tell the user formatting has drifted and offer
to fix it with `uv run ruff format .` followed by a separate commit — do **not** fold
the reformat into the release commit, which must contain only the version bump.
(`ruff format` rewrites files silently with no `--check`, which is exactly how this
drift reaches `master` undetected; this is the most common release-only CI failure.)

Also check the working tree is clean:

```bash
git status --short
```

Expected: empty output (or only untracked files unrelated to packages/barn). If there
are modified or staged files, STOP and ask the user to commit or stash them first —
the release commit should contain only the version bump.

### Step 2.5 — dependency audit (non-blocking report)

Run the dependency checker to surface any package whose declared dependencies have
drifted from what it actually imports (unused cruft, or imported-but-undeclared
third-party deps that would break a fresh install from PyPI):

```bash
uv run python scripts/check_deps.py
```

This wraps `deptry` per package (using a module-name map so inter-package deps
aren't mis-flagged) and prints `clean` or a per-package list of findings:

- **MISSING (DEP003)** — imported but not declared. The most important class: a
  package that imports e.g. `nicegui` without declaring it works in the dev
  workspace (transitively present) but can break when installed standalone from
  PyPI.
- **UNUSED (DEP002)** — declared but never imported. Cosmetic; bloats install size.
- **NOT INSTALLED (DEP001)** — imported but not available at all. A real bug.

**This is a REPORT, not a gate.** The script always exits 0. Show the output to the
user. If there are findings, summarize them and ask whether to fix now (edit the
relevant `pyproject.toml`s, re-sync, re-run) or proceed with the release as-is.
Do NOT auto-edit dependencies or block the release — `deptry` has known false
positives (e.g. deliberate version pins like `attrs` that are transitive of
`cattrs`, or extras like `visiongraph[all]`), so the operator decides. The
`KNOWN_OK` map in the script already suppresses the documented ones; if a new
false positive appears, add it there rather than removing a needed dep.

### Step 3 — pre-flight check for a clean ancestor

Make sure we're on `main` (or whichever branch CI publishes from) and there are no
unpushed commits the user has forgotten about:

```bash
git branch --show-current
git log --oneline @{u}..HEAD 2>/dev/null
```

If the branch isn't `main`, ask the user to confirm — releasing from a feature branch
is unusual but not forbidden. If `git log @{u}..HEAD` shows unpushed commits, list them
to the user and ask whether to push them first (`git push <remote> HEAD`) before
proceeding.

### Step 4 — bump and preview the diff

Run the bump script in dry-run mode. This NEVER writes; it only prints the unified
diff of what would change.

```bash
uv run python scripts/bump_version.py <NEW_VERSION> --dry-run
```

Expected: the script either prints `Nothing to do: all packages already at version
X.Y.Z.` (shouldn't happen — step 1 already rejected no-op bumps) or prints a unified
diff covering 10 files (`packages/*/pyproject.toml` ×2, `barn/*/pyproject.toml` ×8)
followed by `10 file(s) will change. Target version: X.Y.Z.`.

Present the diff verbatim in the chat. Make sure the user can scroll the whole thing
before the next step.

### Step 5 — confirm

**On `--dry-run`**: apply the bump (so the user can `git diff` the real files), then
STOP. Do NOT ask for confirmation, do NOT commit, do NOT tag, do NOT push:

```bash
uv run python scripts/bump_version.py <NEW_VERSION> --yes
```

Tell the user:

> **Dry-run: stopping here.** Bump applied; working tree now has 10 modified files.
> Run `git diff` to inspect, then `git checkout packages barn uv.lock` to roll back.
> To actually cut the release, re-invoke `/haywire-release <NEW_VERSION>` without
> `--dry-run`.

**Otherwise (normal invocation)**: ask via `AskUserQuestion`:

> "Apply the bump, commit as `chore: release v<NEW_VERSION>`, and tag `v<NEW_VERSION>`?
> (You'll run the final `git push` yourself — I'll give you the exact command.)"

Offer three options:

- **Yes, do it.** Proceeds to steps 6–9 (including the Step 6.5 wheel smoke).
- **No, abort.** The working tree is still clean; just stop.
- **Apply the bump but don't commit/tag/push yet.** Runs
  `scripts/bump_version.py <NEW_VERSION> --yes`, then stops. The user can inspect
  the files, then re-invoke `/haywire-release <NEW_VERSION>` to finish (Step 6 is
  idempotent), or `git checkout packages barn uv.lock` to roll back.

### Step 6 — apply the bump and commit

```bash
uv run python scripts/bump_version.py <NEW_VERSION> --yes
```

(Idempotent if already applied in step 5's middle option.)

Then regenerate the lockfile. `bump_version.py` rewrites only the `pyproject.toml`
manifests — it does NOT touch `uv.lock`. Every workspace package carries its own
`version = "X.Y.Z"` line in the lockfile, so without this step `uv.lock` is committed
still pinning the OLD versions, leaving it stale on `master` after every release:

```bash
uv lock
```

Expected: `uv.lock` is rewritten with the new versions for all bumped packages.
(`haybale-visiongraph` lives in its own repo and is excluded from the workspace in
`[tool.uv.workspace].exclude`, so it never appears in the lock or the bump.)

Then bake the docs. `scripts/bake_docs.py` regenerates the gitignored
`packages/haywire-core/src/haywire/_baked_docs/` tree that the haywire-core wheel
force-includes as `haywire/docs`. The bake rewrites source-file links to
versioned GitHub blob URLs (`.../blob/v<NEW_VERSION>/...`), so it **MUST run after
the bump** — otherwise the URLs embed the previous release's tag:

```bash
uv run python scripts/bake_docs.py --version v<NEW_VERSION>
```

Expected: `Baked 70 docs → …/_baked_docs (version v<NEW_VERSION>)`. A few `WARN`
lines for prose that looks link-shaped (e.g. `setting[str](...)`) are normal.
The output dir is gitignored, so it does **not** appear in the commit — it's
consumed at wheel-build time (Step 6.5 and CI). If the script raises
`SnippetMissingError`, a snippet source in `docs/` moved; STOP and fix the
`--8<--` path before releasing.

Then stage the bumped files plus the freshly-locked file and commit:

```bash
git add -u
git commit -m "chore: release v<NEW_VERSION>"
```

Use `git add -u` (stage **all tracked modifications**), NOT a `barn/*/pyproject.toml`
glob. A glob expands to every `barn/*` entry on disk — and if `barn/haybale-visiongraph`
is present as a local symlink (it's a gitignored, out-of-tree package; see
[`docs/guides/sharing-libraries.md`](../../../docs/guides/sharing-libraries.md) and the
workspace `exclude`), git aborts the whole `git add` with
`pathspec '…' is beyond a symbolic link` and **nothing gets staged** — the commit then
silently fails with "no changes added." `git add -u` sidesteps this entirely: it only
touches files git already tracks, and the visiongraph symlink is untracked, so it's
never considered. This is safe because Step 2 guaranteed a clean tree, so the only
tracked modifications are this release's 10 `pyproject.toml`s + `uv.lock`.

Single-line subject, no body. The commit subject is exactly that — `chore: release v`
prefix followed by the version. The CI workflow doesn't care about the message, but
following the convention keeps `git log --oneline` searchable for past releases.

After `uv lock`, `uv.lock` will always have changed (the version lines moved), so it's
part of the staged set — confirm it's in the commit with `git diff --cached --name-only`
(expect exactly 11 paths: 10 `pyproject.toml` + `uv.lock`). The baked docs are
gitignored, so they are correctly absent from this set.

### Step 6.5 — wheel-build smoke (before tag)

Build the haywire-core wheel locally to prove it builds from the baked docs
*before* tagging. `uv build` builds the wheel from an extracted sdist; a broken
docs force-include (the v0.0.26 failure) or a missing bake surfaces here as a
build error instead of blowing up in CI after the tag is already public:

```bash
uv build --package haywire-core
```

Expected: `Successfully built dist/haywire_core-<NEW_VERSION>-py3-none-any.whl`.
Then confirm the baked docs actually landed in the wheel:

```bash
unzip -l dist/haywire_core-<NEW_VERSION>-py3-none-any.whl | grep -c 'haywire/docs/'
```

Expected: a non-zero count (currently 70 — one per `docs/*.md`). If the build
fails or the count is 0, STOP: the bake didn't run or the force-include is
misconfigured. Do NOT tag. Clean up the smoke artifacts afterward:

```bash
rm -f dist/haywire_core-<NEW_VERSION>-py3-none-any.whl dist/haywire_core-<NEW_VERSION>.tar.gz
```

(These are gitignored under `dist/`, but removing them keeps the tree tidy.)

### Step 7 — create the tag

```bash
git tag v<NEW_VERSION>
```

This creates a *lightweight* tag (no message, no signature). For a release that
deserves a release-notes page, use an annotated tag instead:

```bash
git tag -a v<NEW_VERSION> -m "Release v<NEW_VERSION>"
```

Default to **lightweight**. The annotated form is offered as a second `AskUserQuestion`
only if the user explicitly asked for a release-notes page:

> "Create an annotated tag with a release-notes message? (Default: no, lightweight tag.)"

### Step 8 — hand the push command to the user (do NOT run it)

**Do NOT run `git push` yourself.** A local `block-dangerous-git.sh` hook intercepts
`git push` and blocks it; if the skill attempts the push it will fail silently mid-flow
and the tag never reaches GitHub — which means the CI publish workflow never fires and
nothing gets published to PyPI (the exact failure this step exists to prevent).

Instead, detect the remote and then **print the exact command for the user to copy-paste
and run in their own terminal**, where the hook doesn't apply.

Detect the remote first:

```bash
git remote
```

Expected: a single remote name. If there's exactly one, use it. If there are multiple,
ask the user which one to use via `AskUserQuestion`:

> "Push to which remote? (options: each name from `git remote`)"

If there are zero remotes, STOP and tell the user — the release can't reach CI without
a remote.

Then present the push command to the user as a copy-paste block (substituting the real
`<REMOTE>` and `<NEW_VERSION>`):

> **Final step — run this in your terminal to ship the release:**
>
> ```bash
> git push <REMOTE> HEAD v<NEW_VERSION>
> ```
>
> This pushes the branch ref AND the new tag in a single round-trip. The tag triggers
> the CI publish workflow (`.github/workflows/publish.yml`) on GitHub. Once it's
> pushed, watch progress with `gh run watch`.

Do not proceed to Step 9's "tag pushed" wording as if the push already happened — the
user runs it. Frame Step 9 as "once you've pushed, CI will…".

### Step 9 — CI handoff

Tell the user (note: the push is theirs to run from Step 8 — phrase this as what
happens *once they push*, not as something that already occurred):

> Once you push tag `v<NEW_VERSION>` to `<REMOTE>` (Step 8), CI will:
>
> 1. Run the fast test suite (Job 1 — gate).
> 2. Build all 7 wheels (Job 2 — build).
> 3. Publish each wheel to PyPI in dependency order, with idempotent skip if a version
>    already exists (Job 3 — publish, OIDC via Trusted Publisher).
> 4. Generate the marketplace and deploy to GitHub Pages (Job 4 — deploy-marketstall).
>
> Watch progress: `gh run watch` (or visit the Actions tab on GitHub).
>
> If a job fails, see
> [`docs/reference/publish_releases.md`](../../../docs/reference/publish_releases.md)
> for recovery procedures. The most common cases:
>
> - **Gate failure**: fix tests on main, retag the same version with `git tag -d
>   v<NEW_VERSION> && git push <REMOTE> :refs/tags/v<NEW_VERSION>`, then re-tag and
>   re-push.
> - **Build/publish failure**: re-run the workflow on the same tag with
>   `gh workflow run publish.yml --ref v<NEW_VERSION>`. The idempotent skip means
>   already-published packages won't be re-published.

If `gh` is available, offer to open the workflow run live:

```bash
gh run watch
```

(This blocks until the workflow finishes. Useful for quick releases; skip for
fire-and-forget.)

## Dry-run mode

If the user invoked `/haywire-release --dry-run <VERSION>`:

- Steps 0–4 run identically (show current, get target, gate, preflight, preview diff).
- Step 5 applies the bump (`scripts/bump_version.py <VERSION> --yes`) so the working
  tree contains the actual changes that would ship, then STOPS without asking for
  confirmation. The user sees:

  > **Dry-run: stopping here.** Bump applied; working tree now has 10 modified files.
  > Run `git diff` to inspect, then `git checkout packages barn uv.lock` to roll back.
  > To actually cut the release, re-invoke `/haywire-release <VERSION>` without
  > `--dry-run`.

- Steps 6–9 (commit, tag, push, CI handoff) are skipped entirely.

This gives the operator a realistic preview — the same files modified the same way as
a real release — without any persistent or shared-state action. Rollback is a single
`git checkout` away.

## What this skill does NOT do

- Bump versions outside `[tool.haywire.release]` (lockstep_unpublished is in scope —
  the bump script handles it; CI doesn't publish those packages, but they still get
  versioned together).
- Edit any file other than via the bump script.
- Run `git push` itself. A local `block-dangerous-git.sh` hook blocks the skill from
  pushing, so Step 8 hands the user a copy-paste command to run in their own terminal.
- Force-push tags or branches. If a tag exists at the target version, the push fails
  loudly — the user must delete the old tag deliberately (per the recovery procedure
  above).
- Authenticate to PyPI. That's CI's job via OIDC Trusted Publisher.
- Watch the workflow run by default. The user can opt in via `gh run watch`.

## Related skills and tools

- [`scripts/bump_version.py`](../../../scripts/bump_version.py) — the version-rewriting
  CLI this skill calls. Documented in [`scripts/README.md`](../../../scripts/README.md).
- [`scripts/check_deps.py`](../../../scripts/check_deps.py) — the dependency auditor
  this skill runs at Step 2.5. Wraps `deptry` per package; reports unused/missing
  deps without blocking or editing.
- [`scripts/generate_marketstall.py`](../../../scripts/generate_marketstall.py) — the
  marketplace generator that CI's deploy job runs. Not invoked by this skill (CI
  runs it after publish succeeds).
- [`.github/workflows/publish.yml`](../../../.github/workflows/publish.yml) — the CI
  publish workflow this skill triggers via the tag push.
- [`docs/reference/publish_releases.md`](../../../docs/reference/publish_releases.md) —
  operational guide with prerequisites (Trusted Publisher setup, GitHub Pages config),
  recovery procedures, and tier-transition recipes.
