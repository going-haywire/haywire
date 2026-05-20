---
name: haywire-release
description: >
  Walk the author through cutting a release of the haywire monorepo. Runs the
  gate tests, bumps every Tier 1+2 package to a new lockstep version (via
  scripts/bump_version.py), shows a unified diff of every change, then on
  confirmation commits with `chore: release vX.Y.Z`, tags `vX.Y.Z`, and pushes
  the tag so the publish CI workflow takes over. Supports `--dry-run` to
  preview the flow without committing. Use this skill whenever the user wants
  to cut, ship, publish, release, or version-bump the monorepo. Trigger
  phrases: "/haywire-release", "cut a release", "ship a release", "release
  haywire", "bump versions and tag".
---

# `/haywire-release`

Operator's playbook for cutting a release of the haywire monorepo's Tier 1+2 packages.
Composes the existing tools (`scripts/bump_version.py`, `git`, `gh`) into the 10-step
flow documented in [`docs/reference/publish_releases.md`](../../../docs/reference/publish_releases.md).

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

The procedure runs in 10 steps that mirror spec § release flow § local. Each step
includes the exact command to run, what to expect, and what to do on failure.

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

### Step 2 — run the gate tests

```bash
uv run pytest -m "not integration" -q
```

Expected: all tests pass (current baseline: 1156 passed). If anything fails, STOP. Show
the failures to the user and do not proceed — releases must not ship on a red gate.

Also check the working tree is clean:

```bash
git status --short
```

Expected: empty output (or only untracked files unrelated to packages/barn). If there
are modified or staged files, STOP and ask the user to commit or stash them first —
the release commit should contain only the version bump.

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

> "Apply the bump, commit as `chore: release v<NEW_VERSION>`, tag `v<NEW_VERSION>`,
> and push the tag to `<REMOTE>`?"

Offer three options:

- **Yes, do it.** Proceeds to steps 6–8.
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

Then stage the bumped files plus the lockfile and commit:

```bash
git add packages/*/pyproject.toml barn/*/pyproject.toml uv.lock
git commit -m "chore: release v<NEW_VERSION>"
```

Single-line subject, no body. The commit subject is exactly that — `chore: release v`
prefix followed by the version. The CI workflow doesn't care about the message, but
following the convention keeps `git log --oneline` searchable for past releases.

If `uv.lock` wasn't regenerated (e.g. the bump didn't change any dependency strings),
`git add uv.lock` is a no-op — fine, leave the command as-is.

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

### Step 8 — push the branch and the tag

Detect the remote first:

```bash
git remote
```

Expected: a single remote name. If there's exactly one, use it. If there are multiple,
ask the user which one to push to via `AskUserQuestion`:

> "Push to which remote? (options: each name from `git remote`)"

If there are zero remotes, STOP and tell the user — the release can't reach CI without
a remote.

Then push the current branch and the tag together:

```bash
git push <REMOTE> HEAD v<NEW_VERSION>
```

This pushes the branch ref AND the new tag in a single round-trip. The tag triggers
the CI publish workflow (`.github/workflows/publish.yml`) on GitHub.

### Step 9 — CI handoff

Tell the user:

> Tag `v<NEW_VERSION>` pushed to `<REMOTE>`. CI will now:
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
- Force-push tags or branches. If a tag exists at the target version, the push fails
  loudly — the user must delete the old tag deliberately (per the recovery procedure
  above).
- Authenticate to PyPI. That's CI's job via OIDC Trusted Publisher.
- Watch the workflow run by default. The user can opt in via `gh run watch`.

## Related skills and tools

- [`scripts/bump_version.py`](../../../scripts/bump_version.py) — the version-rewriting
  CLI this skill calls. Documented in [`scripts/README.md`](../../../scripts/README.md).
- [`scripts/generate_marketstall.py`](../../../scripts/generate_marketstall.py) — the
  marketplace generator that CI's deploy job runs. Not invoked by this skill (CI
  runs it after publish succeeds).
- [`.github/workflows/publish.yml`](../../../.github/workflows/publish.yml) — the CI
  publish workflow this skill triggers via the tag push.
- [`docs/reference/publish_releases.md`](../../../docs/reference/publish_releases.md) —
  operational guide with prerequisites (Trusted Publisher setup, GitHub Pages config),
  recovery procedures, and tier-transition recipes.
