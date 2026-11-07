---
name: haywire-release
description: >
  Walk the author through cutting a release of the haywire monorepo. Checks that
  CI passed on master, bumps every Tier 1+2 package to a new lockstep version (via
  scripts/bump_version.py), shows a unified diff of every change, then on
  confirmation commits `chore: release vX.Y.Z` on a release branch, merges it
  through a PR once its checks pass, tags the merged commit, and hands the user the
  tag push (a local hook blocks tag pushes) so the publish CI workflow takes over. Supports `--dry-run` to
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
  `master` is clean.

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

The procedure runs in the steps below, with a non-blocking dependency audit at Step
2.5. `master` only receives changes through PRs whose checks passed (CLAUDE.md, *Git
and pull requests*), so the release does not run the test suite locally: it checks CI's
result for the commit it releases, and the version bump goes through a PR like any
change. Each step includes the exact command to
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

- **At `0.1.0`: revisit every published framework floor.** In-repo packages use
  `>=` floors, so they are unaffected. But `~=0.0.X` specifiers published in the
  wild exclude `0.1.0` by construction: any third-party haybale carrying a
  compatible-release requirement will stop being installable on the new
  framework unless its author republishes with a widened specifier. Announce it
  before tagging.

### Step 2 — check that CI passed on master

The release is cut from the latest `master`. Bring it up to date and make sure the
working tree is clean:

```bash
git switch master
git pull --ff-only
git status --short
```

Expected: no output from `git status --short` (untracked files unrelated to
packages/barn are fine). If there are modified or staged files, STOP and ask the user
to commit or stash them first — the release commit must contain only the version bump.

Then check the CI result for the commit about to be released:

```bash
gh run list --branch master --workflow CI --limit 1 \
  --json headSha,status,conclusion --jq '.[0]'
git rev-parse HEAD
```

Expected: `headSha` equals `HEAD`, `status` is `completed` and `conclusion` is
`success`. Otherwise STOP:

- **Still running:** wait (`gh run watch <id>`), then check again.
- **Failed:** show the failing jobs (`gh run view <id> --log-failed`) — releases must
  not ship on a red `master`. The fix goes through a PR first.
- **No run for `HEAD`:** the commit reached `master` without CI (an admin bypass).
  Start one with `gh workflow run CI --ref master`, wait for it, then continue.

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

### Step 3 — create the release branch

```bash
git switch -c release/v<NEW_VERSION>
```

All of Step 6 happens on this branch. `master` refuses direct pushes, so the bump
reaches it through the PR in Step 7.

### Step 4 — bump and preview the diff

Run the bump script in dry-run mode. This NEVER writes; it only prints the unified
diff of what would change.

```bash
uv run python scripts/bump_version.py <NEW_VERSION> --dry-run
```

Expected: the script either prints `Nothing to do: all packages already at version
X.Y.Z.` (shouldn't happen — step 1 already rejected no-op bumps) or prints a unified
diff covering 21 files (`packages/*/pyproject.toml` ×2, `barn/*/pyproject.toml` ×8,
plus each of those 8 barn packages' `haybale.toml` and the framework-owned
`builtin` library's `haybale.toml` nested inside `haywire-core`) followed by
`21 file(s) will change. Target version: X.Y.Z.`. `haybale.toml` is the
runtime-read copy of `version` (`pyproject.toml` stays canon); it's synced
here so `LibraryIdentity` never lags behind a release.

Present the diff verbatim in the chat. Make sure the user can scroll the whole thing
before the next step.

### Step 5 — confirm

**On `--dry-run`**: apply the bump (so the user can `git diff` the real files), then
STOP. Do NOT ask for confirmation, do NOT commit, do NOT tag, do NOT push:

```bash
uv run python scripts/bump_version.py <NEW_VERSION> --yes
```

Tell the user:

> **Dry-run: stopping here.** Bump applied; working tree now has 21 modified files.
> Run `git diff` to inspect, then `git checkout packages barn uv.lock` to roll back.
> To actually cut the release, re-invoke `/haywire-release <NEW_VERSION>` without
> `--dry-run`.

**Otherwise (normal invocation)**: ask via `AskUserQuestion`:

> "Apply the bump, commit `chore: release v<NEW_VERSION>` on `release/v<NEW_VERSION>`,
> merge it into `master` through a PR once its checks pass, and tag the merged commit
> `v<NEW_VERSION>`? (You'll push the tag yourself — I'll give you the exact command.)"

Offer three options:

- **Yes, do it.** Proceeds to steps 6–9 (including the Step 6.5 wheel smoke). This
  answer is the user's word to merge the release PR in Step 7.
- **No, abort.** Switch back with `git switch master` and delete the empty branch
  with `git branch -d release/v<NEW_VERSION>`; just stop.
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

Then verify the bump actually landed everywhere — every release package at
`<NEW_VERSION>`, and every `haybale.toml` in sync with its own `pyproject.toml`:

```bash
uv run python scripts/check_release_versions.py --expect <NEW_VERSION>
```

Expected: `Release version check passed`. This is the same gate both publish
workflows run against the tag, so a failure here is a failure that would
otherwise surface only after tagging and pushing. Stop and fix if it fails.

Then regenerate the per-library docs. This is a **different** thing from the bake
below, and the two are easy to confuse:

| | `haywire docs --all` (this step) | `scripts/bake_docs.py` (next step) |
| --- | --- | --- |
| reads | live component registrations | the hand-written `docs/` site |
| writes | `barn/*/README.md`, `<lib>/{OVERVIEW,QUICKREF}.md`, `<lib>/docs/*.md` | `_baked_docs/` |
| committed? | **yes** — part of the release commit | no, gitignored |

```bash
uv run haywire docs --all
```

Expected: a `Total coverage gaps: N` summary. The gap lines are advisory (components
with no docstring) and do **not** block a release.

It **MUST run after the bump**: the generator stamps each index with the version it
reads from `haybale.toml` at generation time, so running it before the bump stamps the
OLD version. Nothing else regenerates these files and no CI job checks them, so a
skipped step here is invisible until someone runs the generator by hand.

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
git add barn packages          # picks up NEW generated doc files
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
never considered.

`-u` alone is not sufficient, though: it ignores untracked files, and the doc step
writes a NEW file whenever a component is added or renamed — a rename being a delete
plus an add, `-u` catches the delete and drops the add, committing a half-applied
rename. Hence the second line, which passes directories rather than globs so the
shell never expands them.

Step 2 guaranteed a clean tree, so everything staged is this release's own work: the
version bumps, `uv.lock`, and the regenerated per-library docs. The commit lands on
`release/v<NEW_VERSION>`.

Single-line subject, no body. The commit subject is exactly that — `chore: release v`
prefix followed by the version. The CI workflow doesn't care about the message, but
following the convention keeps `git log --oneline` searchable for past releases.

After `uv lock`, `uv.lock` will always have changed (the version lines moved), so it's
part of the staged set — confirm it's in the commit with `git diff --cached --name-only`
(expect exactly 20 paths: 10 `pyproject.toml` + 9 `haybale.toml` + `uv.lock`). The
baked docs are gitignored, so they are correctly absent from this set.

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

### Step 7 — merge the release PR

Push the branch and open the PR:

```bash
git push -u origin release/v<NEW_VERSION>
gh pr create --base master --title "chore: release v<NEW_VERSION>" \
  --body "Version bump to <NEW_VERSION>, lockfile and regenerated library docs."
```

Wait for its checks (about 6 minutes), then merge:

```bash
gh pr checks --watch
gh pr merge --squash
```

If a check fails, STOP and show the failure: the bump broke something CI catches and
the local steps did not. Fix it on the release branch and push again.

### Step 8 — tag the merged commit, and hand the tag push to the user

A squash merge makes a new commit on `master`; that one is the release, not the
branch's commit. Update `master` and tag it:

```bash
git switch master
git pull --ff-only
git log --oneline -1          # expect: chore: release v<NEW_VERSION> (#N)
git tag v<NEW_VERSION>
git branch -d release/v<NEW_VERSION>
```

This creates a *lightweight* tag. For a release that deserves a release-notes page,
use `git tag -a v<NEW_VERSION> -m "Release v<NEW_VERSION>"` instead; ask via
`AskUserQuestion` only if the user explicitly asked for release notes.

**Do NOT push the tag yourself.** A tag push publishes the release, and the local
`block-dangerous-git.sh` hook blocks it. Print the exact command for the user to run
in their own terminal:

> **Final step — run this in your terminal to ship the release:**
>
> ```bash
> git push origin v<NEW_VERSION>
> ```
>
> The tag triggers the publish workflow (`.github/workflows/publish.yml`). Watch it
> with `gh run watch`.

Frame Step 9 as what happens *once the user pushes*, not as something that already
occurred.

### Step 9 — CI handoff

Tell the user (note: the push is theirs to run from Step 8 — phrase this as what
happens *once they push*, not as something that already occurred):

> Once you push tag `v<NEW_VERSION>` (Step 8), CI will:
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
> - **Gate failure**: fix the tests through a PR, then delete and recreate the tag
>   yourself (`git tag -d v<NEW_VERSION> && git push origin :refs/tags/v<NEW_VERSION>`,
>   then tag the new `master` commit and push it again).
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

- Steps 0–4 run identically (show current, get target, CI check, release branch,
  preview diff).
- Step 5 applies the bump (`scripts/bump_version.py <VERSION> --yes`) so the working
  tree contains the actual changes that would ship, then STOPS without asking for
  confirmation. The user sees:

  > **Dry-run: stopping here.** Bump applied; working tree now has 21 modified files.
  > Run `git diff` to inspect, then `git checkout packages barn uv.lock` to roll back.
  > To actually cut the release, re-invoke `/haywire-release <VERSION>` without
  > `--dry-run`.

- Steps 6–9 (commit, PR, tag, CI handoff) are skipped entirely. To abandon, roll
  back the files, then `git switch master` and `git branch -d release/v<VERSION>`.

This gives the operator a realistic preview — the same files modified the same way as
a real release — without any persistent or shared-state action. Rollback is a single
`git checkout` away.

## What this skill does NOT do

- Bump versions outside `[tool.haywire.release]` (lockstep_unpublished is in scope —
  the bump script handles it; CI doesn't publish those packages, but they still get
  versioned together).
- Edit any file other than via the bump script.
- Push the tag. A tag push publishes the release; the local `block-dangerous-git.sh`
  hook blocks it, so Step 8 hands the user the command. Pushing the release branch is
  allowed.
- Run the test suite. `master` only holds commits whose CI passed, and Step 2 checks
  that result; the release PR's checks cover the bump.
- Force-push tags or branches. If a tag exists at the target version, the push fails
  loudly — the user must delete the old tag deliberately (per the recovery procedure
  above).
- Authenticate to PyPI. That's CI's job via OIDC Trusted Publisher.
- Watch the workflow run by default. The user can opt in via `gh run watch`.

## Related skills and tools

- [`scripts/bump_version.py`](../../../scripts/bump_version.py) — the version-rewriting
  CLI this skill calls. Documented in [`scripts/README.md`](../../../scripts/README.md).
- [`scripts/check_release_versions.py`](../../../scripts/check_release_versions.py) — the
  read-back for the bump, run at Step 6 and again by CI against the tag. Unlike
  `check_deps.py`, it is a gate: it exits non-zero on any disagreement.
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
