---
name: haywire-release
description: >
  Walk the author through cutting a release of the haywire monorepo. Checks that
  CI passed on master, bumps every Tier 1+2 package to a new lockstep version (via
  scripts/bump_version.py), shows a unified diff of every change, then on
  confirmation commits `chore: release vX.Y.Z` on a release branch and opens a PR;
  the user's "publish" is the word to merge it once its checks pass, and the merge is the
  publish: CI tags the merge commit, publishes, and writes the release notes.
  Starts with a view of what the release would ship (commits, waiting libraries,
  reminders, a proposed version) and ends by reporting the release notes and the
  libraries the release unblocks, offering to publish them. Supports `--dry-run` to
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
- **`--dry-run`** (optional) — perform every step *except* commit/push. The bump
  is applied to the working tree so the user can `git diff` to inspect, then roll
  back with `git checkout .` if abandoning.

## Procedure

The procedure runs in the steps below, starting with a read-only view of what the release
would ship (Step 0). `master` only receives changes through PRs whose checks passed (CLAUDE.md, *Git
and pull requests*), so the release does not run the test suite locally: it checks CI's
result for the commit it releases, and the version bump goes through a PR like any
change. Each step includes the exact command to
run, what to expect, and what to do on failure.

### Step 0 — what this release would ship

A read-only view that changes nothing. Show it all in one message, then go on to Step 1.

Bring `master` up to date and read the current version:

```bash
git switch master
git pull --ff-only
git fetch --tags
grep -E '^version = ' packages/haywire-core/pyproject.toml | head -1
git tag --list 'v*' --sort=-v:refname | head -1
```

The version line is `version = "X.Y.Z"` (the lockstep version, from the foundation
package); the tag is the last release. If the file is missing or the line is not found,
the workspace layout has changed: stop and ask the user. Tell the user:

> Current release version: **X.Y.Z**; last tag: **vX.Y.Z**

**0.1 What changed since the last tag.** Group the commits by type, each with its PR link
(a subject ending `(#N)` links to `https://github.com/going-haywire/haywire/pull/N`):

```bash
git log v<LAST>..HEAD --format='%h %s'
```

Types: `feat`, `fix`, `perf`, `refactor`, then `docs`/`test`/`chore`/`ci`/`build` as one
line with a count. A `!` after the type (`refactor!:`) marks a breaking commit: list those
first. No commit since the tag means nothing to release: say so and stop.

**0.2 Waiting libraries.** The organisation's libraries whose master asks for a core
version that is not released yet:

```bash
uv run python scripts/release_sweep.py floors
```

It reads the dependency floors (the `>=` bounds) of every `barn/*/pyproject.toml` on core's
`pip_publish_order` packages. Each one above the last tag is a library that waits for this
release: show it, with the floor, so the user can see whom a release frees. A library whose
wait no floor records is held by a reminder (0.3). Exit code 2 means a command failed: say
the report could not be made, never that no library waits.

**0.3 Reminders.** Decisions recorded for this release:

```bash
gh issue list --repo going-haywire/haywire --label todo-pre-release --state open \
  --json number,title,url
```

Usually `[]`. Otherwise list each issue with its URL and ask the user whether to deal
with it first or release anyway; a reminder is a help, not a gate. Also list the open
`after-core-release` reminders (`uv run python scripts/release_sweep.py reminders`,
against `HEAD`): they show what a library waits for that no floor records. If `gh`
cannot answer (not logged in, no network), say the reminders could not be read; never
report that none are open. The convention:
[sharing-libraries §7.1](../../../docs/guides/sharing-libraries.md#71-release-reminders).

**0.4 What this release breaks in the libraries.**

```bash
uv run python scripts/release_sweep.py names
```

It compares the Author API name lists (`tests/api/names.py`) at `HEAD` with the last
release tag, and scans every `haybale-*` repository of the organisation (shallow clones,
deleted afterwards) for imports of each removed or newly deprecated name. It also counts
each library's imports of internal modules (`haywire.core`, `haywire.ui`,
`haywire.barn`), which may change in any release.

For a removed name a library imports, ask the user whether to keep it a while longer as
deprecated (ADR 0085) or release and draft an `after-core-release` reminder for that
library (opened only on their word). Exit code 2 means a command failed: say the report
could not be made, never that nothing breaks.

**0.5 Dependency audit (a report, not a gate).** Surfaces any package whose declared
dependencies have drifted from what it imports:

```bash
uv run python scripts/check_deps.py
```

The script wraps `deptry` per package (using a module-name map so inter-package deps
are not mis-flagged) and prints `clean` or a per-package list, and always exits 0:

- **MISSING (DEP003)**: imported but not declared. The most important class: a package
  that imports e.g. `nicegui` without declaring it works in the dev workspace
  (transitively present) but can break when installed standalone from PyPI.
- **UNUSED (DEP002)**: declared but never imported. Cosmetic; bloats install size.
- **NOT INSTALLED (DEP001)**: imported but not available at all. A real bug.

If there are findings, summarise them and ask whether to fix now (edit the relevant
`pyproject.toml`s, re-sync, re-run) or release as-is. Do not auto-edit dependencies or
block the release: `deptry` has known false positives (deliberate version pins like
`attrs`, a transitive of `cattrs`; extras like `visiongraph[all]`), so the operator
decides. The `KNOWN_OK` map in the script already suppresses the documented ones; add a
new false positive there rather than removing a needed dependency.

**0.6 Library nightly results.** Each library's latest `nightly` run, its tests against
core's `master`:

```bash
uv run python scripts/release_sweep.py nightly
```

Show every row with its date and run URL. `failed` is a break this release would ship:
link the run and ask the user whether to fix it first or release anyway. Report
`inconclusive` (a cancelled run), `running`, `no run`, `no workflow` and `disabled`
(GitHub turns a schedule off after 60 days without activity in the repository) as they
are, never as green. A run older than the commits since the last tag did not see them:
say so. Exit code 2 means a command failed: say the results could not be read.

**0.7 A proposed version.** Propose, never impose; the user answers in Step 1. While core
is below 1.0:

- **minor** (`0.X.0`) when any commit since the last tag is breaking (`!`), or the `names`
  report lists a removed API name, or there are 10 or more `feat` commits;
- **patch** (`0.X.Y`) otherwise.

Give the numbers behind it (feat count, breaking commits, removed names). The rule follows
the releases from v0.3.0 to v0.5.3: minors carried a breaking commit or a large batch of
features, patches the rest (the 10 is a threshold read off that history, not a law).

### Step 1 — get the new release version

If the user supplied a version on the invocation line (e.g. `/haywire-release 0.0.2`),
use it. Otherwise ask via `AskUserQuestion`:

> "New release version? Current is X.Y.Z; Step 0.7 proposes <PROPOSAL>. Use semver (patch / minor / major)."

Validate the input against the regex `^\d+\.\d+\.\d+(?:[a-z0-9.+!*-]*)?$` (PEP 440-ish:
`X.Y.Z` with optional pre/post/dev suffix). Reject and re-prompt on malformed input.

Also reject if the new version equals the current version — the bump script would
report "Nothing to do" and the release would be a no-op.

- **At `0.1.0`: revisit every published framework floor.** In-repo packages use
  `>=` floors, so they are unaffected. But `~=0.0.X` specifiers published in the
  wild exclude `0.1.0` by construction: any third-party haybale carrying a
  compatible-release requirement will stop being installable on the new
  framework unless its author republishes with a widened specifier. Announce it
  before merging the release PR.

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
diff covering the `pyproject.toml` of every release package (`packages/*` and `barn/*`),
the `haybale.toml` of each barn package and the framework-owned `builtin` library's
`haybale.toml` nested inside `haywire-core` (27 files for v0.5.4), followed by
`N file(s) will change. Target version: X.Y.Z.`. `haybale.toml` is the
runtime-read copy of `version` (`pyproject.toml` stays canon); it's synced
here so `LibraryIdentity` never lags behind a release.

Present the diff verbatim in the chat. Make sure the user can scroll the whole thing
before the next step.

### Step 5 — confirm

**On `--dry-run`**: apply the bump (so the user can `git diff` the real files), then
STOP. Do NOT ask for confirmation, do NOT commit, do NOT push:

```bash
uv run python scripts/bump_version.py <NEW_VERSION> --yes
```

Tell the user:

> **Dry-run: stopping here.** Bump applied; working tree now has the bumped files modified.
> Run `git diff` to inspect, then `git checkout packages barn uv.lock` to roll back.
> To actually cut the release, re-invoke `/haywire-release <NEW_VERSION>` without
> `--dry-run`.

**Otherwise (normal invocation)**: ask via `AskUserQuestion`:

> "Publish v<NEW_VERSION>? I apply the bump, commit `chore: release v<NEW_VERSION>` on
> `release/v<NEW_VERSION>`, open the release PR and merge it once its checks are green,
> and the merge publishes v<NEW_VERSION>: CI tags the merge commit, publishes to PyPI and
> deploys the marketstall. You run no command."

Offer three options:

- **Publish.** Proceeds to steps 6–10 (including the Step 6.5 wheel smoke). This
  answer is the user's word "publish": it merges the release PR in Step 7, and so
  publishes.
- **No, abort.** Switch back with `git switch master` and delete the empty branch
  with `git branch -d release/v<NEW_VERSION>`; just stop.
- **Apply the bump but don't commit/push yet.** Runs
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
workflows run against the release version, so a failure here is a failure that would
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
glob. A glob expands to every `barn/*` entry on disk — and if anything untracked sits
there (a local symlink to another checkout, say), git aborts the whole `git add` with
`pathspec '…' is beyond a symbolic link` and **nothing gets staged** — the commit then
silently fails with "no changes added." `git add -u` sidesteps this entirely: it only
touches files git already tracks.

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
(expect the bumped `pyproject.toml` and `haybale.toml` files, `uv.lock`, and the
regenerated `QUICKREF.md` files: 41 paths for v0.5.4). The baked docs are gitignored, so
they are correctly absent from this set.

### Step 6.5 — wheel-build smoke (before the PR)

Build the haywire-core wheel locally to prove it builds from the baked docs
*before* the release PR is merged. `uv build` builds the wheel from an extracted sdist; a broken
docs force-include (the v0.0.26 failure) or a missing bake surfaces here as a
build error instead of blowing up in the merge run, where it would block the release:

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
misconfigured. Do NOT open the PR. Clean up the smoke artifacts afterward:

```bash
rm -f dist/haywire_core-<NEW_VERSION>-py3-none-any.whl dist/haywire_core-<NEW_VERSION>.tar.gz
```

(These are gitignored under `dist/`, but removing them keeps the tree tidy.)

### Step 7 — open the release PR and merge it

Push the branch and open the PR:

```bash
git push -u origin release/v<NEW_VERSION>
gh pr create --base master --title "chore: release v<NEW_VERSION>" \
  --body "Version bump to <NEW_VERSION>, lockfile and regenerated library docs."
```

Run the push and `gh pr create` as two separate commands: the push hook reads a whole
chained command and blocks it as a tag push when the PR title (`release v0.5.4`) follows
a `git push`.

The title must start `chore: release v`: `scripts/check_version_changes.py` fails any PR
that changes a version unless it does, and the merge commit carries that title.

Wait for its checks (about 6 minutes, macOS included once the PR is ready, not draft):

```bash
gh pr checks --watch
```

If a check fails, STOP and show the failure: the bump broke something CI catches and
the local steps did not. Fix it on the release branch and push again.

Once every check is green, merge. The user's "publish" in Step 5 is the word; do not ask
again. Read the PR's comments first, as in the `haywire-workflow` skill (*Finishing as the
maintainer*, step 3); a comment from a person is answered before the merge.

```bash
gh pr merge --squash
```

The merge is the publish. Say so in the message that follows, with the PR's URL.

### Step 8 — watch the merge run

A squash merge makes a new commit on `master`; that one is the release. The push starts
the `Publish Release` workflow, which tags it. Watch the run:

```bash
gh run list --workflow "Publish Release" --branch master --limit 1
gh run watch <id> --exit-status
```

Expected jobs, in order: `plan` (finds the version differs from the latest tag), `gate`,
`build`, `tag` (creates `v<NEW_VERSION>` on the merge commit), `publish`,
`deploy-marketstall`, `release-notes`. A failed gate or build leaves no tag. The
`CI` workflow runs on the same commit; check it too (`haywire-workflow`, step 4).

Do not tag and do not push a tag: CI does, and the local `block-dangerous-git.sh` hook
blocks a tag push from here. Then bring the working copy up to date and let go of the
release branch:

```bash
git switch master
git pull --ff-only
git fetch --tags
git tag --list v<NEW_VERSION>        # expect the tag, made by CI
uv run python scripts/finish.py release/v<NEW_VERSION>
```

### Step 9 — if the merge run fails

[`publish_releases.md`](../../../docs/reference/publish_releases.md) (*Recovery*) has the
procedures. In short:

- **Gate or build failed** (no tag exists): fix the cause through a PR. While `master`
  carries a version without a tag, the next push to `master` releases it, so the fix's
  own merge publishes it (hold other merges until then). To release a different version
  instead, open a new release PR with it.
- **Publish failed after the tag was made:** re-run only the failed jobs
  (`gh run rerun <id> --failed`); publishing skips packages already on PyPI. A full
  re-run finds the tag and ends green without publishing.
- **The tag job failed** (for example a ruleset refused the tag): publish is held back too.
  Tell the user what the job's log says; the fix is theirs to decide. Then re-run the
  failed jobs.
- **A tag pushed by the user** publishes that tag without the tag job; that recovery stays
  theirs.

### Step 10 — report the release, and what it unblocks

Once the run succeeded and PyPI serves `haywire-core <NEW_VERSION>`, report to the user:

```bash
gh release view v<NEW_VERSION> --json url --jq .url      # the release notes
uv run python scripts/release_sweep.py floors --ref v<NEW_VERSION>
uv run python scripts/release_sweep.py reminders --ref v<NEW_VERSION>
```

The release URL first. Then the libraries `floors` lists as `unblocked`: each now has a
core release that satisfies its dependency floor, so the library's own release can go
ahead. Ask once: "publish <libraries> now?". On "publish", start one release task per
library (*Lead and tasks* in the `haywire-workflow` skill), whose brief is the library
release of *In a library repository*: the release PR, its merge once green, `finish`. Then the reminders: each open one with
the commit on its `Waits for:` line and `released` (the tag contains it), `waiting`,
`unknown commit` (not in this clone: `git fetch`) or `no Waits for line` (read the
issue's body and say what it waits for). Show them as a table with the URLs. Offer, per
released issue, one comment: "Unblocked: haywire-core <NEW_VERSION> contains <sha>."
Post them only on the user's word: they appear under the user's name. Never open a
reminder issue without the user's word either. A library that still shows as `waiting`
needs a later core release.

## Dry-run mode

If the user invoked `/haywire-release --dry-run <VERSION>`:

- Steps 0–4 run identically (what the release would ship, get target, CI check,
  release branch, preview diff).
- Step 5 applies the bump (`scripts/bump_version.py <VERSION> --yes`) so the working
  tree contains the actual changes that would ship, then STOPS without asking for
  confirmation. The user sees:

  > **Dry-run: stopping here.** Bump applied; working tree now has the bumped files modified.
  > Run `git diff` to inspect, then `git checkout packages barn uv.lock` to roll back.
  > To actually cut the release, re-invoke `/haywire-release <VERSION>` without
  > `--dry-run`.

- Steps 6–10 (commit, PR, merge, merge run, report) are skipped entirely. To abandon, roll
  back the files, then `git switch master` and `git branch -d release/v<VERSION>`.

This gives the operator a realistic preview — the same files modified the same way as
a real release — without any persistent or shared-state action. Rollback is a single
`git checkout` away.

## What this skill does NOT do

- Bump versions outside `[tool.haywire.release]` (lockstep_unpublished is in scope —
  the bump script handles it; CI doesn't publish those packages, but they still get
  versioned together).
- Edit any file other than via the bump script.
- Post on other repositories' issues without the user's word (Step 10 drafts, the
  user decides).
- Tag or push a tag. CI tags the merge commit (Step 8); a tag push from here is
  blocked by the local `block-dangerous-git.sh` hook, and a tag pushed by hand is the
  user's recovery. Pushing the release branch is allowed.
- Merge without the user's "publish" (Step 5) and a green PR.
- Run the test suite. `master` only holds commits whose CI passed, and Step 2 checks
  that result; the release PR's checks cover the bump.
- Force-push or delete tags or branches. If a tag exists at the target version the
  merge run refuses to release; the user deletes nothing: a tag is permanent
  (`Release tags` ruleset).
- Authenticate to PyPI. That's CI's job via OIDC Trusted Publisher.
- Watch the workflow run by default. The user can opt in via `gh run watch`.

## Related skills and tools

- [`scripts/bump_version.py`](../../../scripts/bump_version.py) — the version-rewriting
  CLI this skill calls. Documented in [`scripts/README.md`](../../../scripts/README.md).
- [`scripts/check_release_versions.py`](../../../scripts/check_release_versions.py) — the
  read-back for the bump, run at Step 6 and again by CI against the tag. Unlike
  `check_deps.py`, it is a gate: it exits non-zero on any disagreement.
- [`scripts/check_deps.py`](../../../scripts/check_deps.py) — the dependency auditor
  this skill runs at Step 0.5. Wraps `deptry` per package; reports unused/missing
  deps without blocking or editing.
- [`scripts/generate_marketstall.py`](../../../scripts/generate_marketstall.py) — the
  marketplace generator that CI's deploy job runs. Not invoked by this skill (CI
  runs it after publish succeeds).
- [`.github/workflows/publish.yml`](../../../.github/workflows/publish.yml) — the CI
  publish workflow the merge of the release PR starts; [`scripts/release_plan.py`](../../../scripts/release_plan.py)
  decides whether a run releases.
- [`docs/reference/publish_releases.md`](../../../docs/reference/publish_releases.md) —
  operational guide with prerequisites (Trusted Publisher setup, GitHub Pages config),
  recovery procedures, and tier-transition recipes.
