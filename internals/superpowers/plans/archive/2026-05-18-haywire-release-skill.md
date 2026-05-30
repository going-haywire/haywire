# `/haywire-release` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/haywire-release` skill that walks an author through the 10-step release flow from spec §release flow (gate tests → bump versions → preview diff → commit → tag → push), wrapping Plan A's `scripts/bump_version.py` and reusing Plan B's CI workflow trigger (a `v*.*.*` tag).

**Architecture:** Pure-Markdown skill at `.claude/skills/haywire-release/SKILL.md` that instructs Claude (the agent invoking the slash command) to run the release flow step by step. The skill is an orchestration playbook, not a new program — it composes existing tools (`scripts/bump_version.py`, `git`, `gh`) and uses `AskUserQuestion` for the two human-in-the-loop checkpoints (new version number, final commit/tag/push confirmation). Reads the current version from any publishable `pyproject.toml` to display "Current release version" at step 0. Detects the configured remote (the repo uses `haywire-origin`, not `origin`) by querying `git remote`. Supports a `--dry-run` invocation that runs every step but stops before commit/tag/push, leaving the working tree changed so the author can inspect it.

**Tech Stack:** Markdown + YAML frontmatter (matches the existing skill convention at `.claude/skills/check-rename/SKILL.md` and `.claude/skills/verify/SKILL.md`). No new Python code — the skill calls into existing CLIs via Bash. The author's interactive flow uses the harness's `AskUserQuestion` tool for choices and `Bash` for command execution. Tests are end-to-end manual verification: dry-run on a throwaway tag.

**Spec reference:** This plan covers spec §release flow §local (`/haywire-release` author-driven), and implements spec task **T8**. Out of scope: the CI side of the release flow (Plans A/B already ship `bump_version.py` + `publish.yml`); `haywire share`/`init` (Plan D); marketplace runtime (Plan E).

---

## Approach Rationale (read before starting)

**Pure-Markdown skill, no Python script:** The release flow has six tool calls (`grep` → `pytest` → `bump_version --dry-run` → `bump_version --yes` → `git commit/tag` → `git push`) and two human checkpoints. Wrapping that in a `scripts/release.py` would just be a thin shell script with worse interactivity than Claude's native tooling. The check-rename skill demonstrates the boundary: it has a Python *detector* (compares ASTs — non-trivial logic) but the *orchestration* (filter, ask, edit) is Markdown. Plan C has no equivalent non-trivial logic; bump_version owns the rewriting. The skill is the operator's playbook.

**`AskUserQuestion` for confirmation, not raw stdin:** Plan A's bump script already supports an interactive `[y/N]` prompt via `input()`. The skill could just shell out to `bump_version.py 0.0.2` and let it prompt the user directly — but that bypasses the skill's diff-presentation step. Instead the skill runs `bump_version.py 0.0.2 --dry-run` (which always prints the diff, never prompts), shows the diff in chat, then uses `AskUserQuestion` to ask "Apply, commit, tag, and push?". On yes, runs `bump_version.py 0.0.2 --yes` (no prompt this time) followed by git commit/tag/push. This way the author sees the diff in the chat UI rather than scrolling terminal output.

**Reading "current version" cheaply:** The spec's step 0 says "Skill prints: Current release version: x.y.z". The cheapest, most reliable way: read `[project] version` from `packages/haywire-core/pyproject.toml` (the foundation package — always at the lockstep version). One `grep`. No need to parse `[tool.haywire.release].publish_order` and find the first entry — every publishable package is at the same version by definition.

**Detecting the remote name:** This repo uses `haywire-origin`, not `origin`. The skill must NOT hardcode the remote. Use `git remote` to list remotes; if exactly one, use it; if multiple, ask the user which to push to; if zero, refuse with an explanation. The spec doesn't specify this nuance, but it's a real-world correctness issue.

**`--dry-run` as a first-class invocation:** The author should be able to test the skill end-to-end without actually pushing a release. `/haywire-release --dry-run 0.0.2` runs every step including the diff preview, but stops before commit/tag/push. The author can then `git diff` to see the pending changes and `git checkout .` to roll back. This is also how the test for the skill works: run dry-run, observe the diff, roll back.

**Why no automated test for the skill:** Markdown skills aren't unit-testable in the conventional sense (they're prompts for an LLM, not code). Verification is end-to-end: a human (or agent) follows the skill against the live repo with `--dry-run` and confirms the expected behavior. Plan tasks include a verification task that exercises this.

---

## File Structure

### Files created

- `.claude/skills/haywire-release/SKILL.md` — the skill definition. YAML frontmatter (`name`, `description`) + Markdown body with the procedure. ~150 lines.

### Files modified

- None. The skill is self-contained.

### Files NOT touched (out of scope)

- `scripts/bump_version.py` (Plan A) — used as-is.
- `.github/workflows/publish.yml` (Plan B) — triggered by the tag the skill pushes.
- `docs/reference/publish_releases.md` (Plan B) — already references the skill ("The /haywire-release skill (T8 — separate plan) walks the author through the full flow"). No update needed; the existing wording was forward-looking and is now accurate.

---

## Self-Review Plan-Time Checks (already performed by author)

- Spec §release flow steps 0–9 → all 10 steps map to procedure sections in `SKILL.md`. ✅
- `gh` CLI is installed locally (`gh version 2.88.1`); the skill can fall back to plain `git push` if `gh` is unavailable.
- Git remote in this repo is `haywire-origin`. Skill detects via `git remote`, not hardcoded.
- Plan A's bump script writes only when `--yes` is passed AND the user confirms; the skill calls it twice (once `--dry-run`, once `--yes`) to keep the diff preview and the actual write as separate, observable steps.
- The skill's dry-run path leaves the working tree dirty (the bump applied but no commit). Author rolls back with `git checkout .` if abandoning.

---

## Task list

### Task 1: Baseline verification

**Files:** read-only.

- [ ] **Step 1: Confirm pre-edit baseline is clean and we're on the expected branch**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
git branch --show-current
git log --oneline -3
uv run ruff check .
uv run pytest -m "not integration" -q 2>&1 | tail -3
```

Expected:
- Branch: `feat/versioning-pre-release-and-bump-script`
- Top 2 commits: `feat: CI publish workflow + marketstall generator` (Plan B), `feat: versioning migration + bump_version.py script` (Plan A)
- Ruff: `All checks passed!`
- Pytest: `1156 passed, 1 skipped, 75 deselected`

If any of these differ, STOP and notify the user — the plan assumes Plans A and B are landed.

- [ ] **Step 2: Confirm bump_version's public API**

```bash
uv run python scripts/bump_version.py --help
```

Expected: argparse help text showing `new_version` positional, `--root`, `--yes`, `--dry-run` flags. The skill will call this CLI; if its signature has drifted, the skill instructions need to match.

- [ ] **Step 3: Confirm the remote name**

```bash
git remote -v
```

Expected: exactly one remote, `haywire-origin`, pointing at `git@github.com:maybites/haywire.git`. If there's a remote named `origin` instead, OR multiple remotes, note it — the skill's remote-detection logic must handle both cases.

- [ ] **Step 4: Confirm gh CLI is available**

```bash
which gh && gh --version | head -1
```

Expected: a path under `/usr/local/bin` or `/opt/homebrew/bin`, version 2.x. The skill can use `gh release create` as an optional final step (creates a GitHub release page on top of the tag). If `gh` is missing, the skill falls back to plain `git push origin v0.0.2`.

---

### Task 2: Write the skill frontmatter and intro

**Files:**
- Create: `.claude/skills/haywire-release/SKILL.md`

- [ ] **Step 1: Verify the target directory does not yet exist**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
test -e .claude/skills/haywire-release && echo EXISTS || echo MISSING
```

Expected: `MISSING`. If `EXISTS`, the plan needs to be revisited — stop and report.

- [ ] **Step 2: Create the directory and write the frontmatter + section 0**

Create `.claude/skills/haywire-release/SKILL.md` with the following EXACT initial content. (Subsequent tasks 3–8 append the body sections.)

````markdown
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
flow defined in [spec § release flow](../../specs/versioning-and-publishing.md).

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
````

(Note the four-leading-backtick fences around the inner code block to nest the triple-backtick frontmatter cleanly. The actual file should have a normal `---`-delimited frontmatter and a single triple-backtick block for the inline `name`/`description` example — see the actual content above between the four-backtick lines.)

Wait — that's wrong. The four-backtick fences in this plan are just to display the markdown content. The actual SKILL.md should be plain markdown starting with `---\nname: haywire-release\n...`. Let me re-state Step 2 clearly:

The file content begins at the line `---` (frontmatter open) and continues through the line `includes the exact command to run, what to expect, and what to do on failure.`. Everything between those lines, INCLUDING the frontmatter delimiters, goes into the file verbatim.

After saving, the file should be ~50 lines (frontmatter + intro section + procedure preamble).

- [ ] **Step 3: Verify the YAML frontmatter parses**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run --with pyyaml python -c "
import yaml, re, pathlib
text = pathlib.Path('.claude/skills/haywire-release/SKILL.md').read_text()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
assert m, 'no frontmatter found'
data = yaml.safe_load(m.group(1))
print('name:', data['name'])
print('description starts:', data['description'][:80])
"
```

Expected: `name: haywire-release`, description starts with `Walk the author through...`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/haywire-release/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): /haywire-release scaffold (frontmatter + intro)

First slice of the release-flow operator skill. Sets up the
.claude/skills/haywire-release/ directory and lays down the YAML
frontmatter (name + description, trigger phrases) plus the intro
"When to use" and "Inputs" sections.

Procedure body comes in follow-up commits.

Refs spec internals/specs/versioning-and-publishing.md T8.
EOF
)"
```

---

### Task 3: Procedure step 0 — show current version

**Files:**
- Modify: `.claude/skills/haywire-release/SKILL.md`

- [ ] **Step 1: Append the "Step 0: show current version" section**

Append to `.claude/skills/haywire-release/SKILL.md`:

```markdown

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
```

(The inner ``bash`` block in the spec sample should be a literal triple-backtick. The outer code block displaying the section in this plan is a quadruple-backtick fence for clarity.)

- [ ] **Step 2: Smoke test against the real workspace**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
grep -E '^version = ' packages/haywire-core/pyproject.toml | head -1
```

Expected: `version = "0.0.1"`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/haywire-release/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): /haywire-release step 0 — print current version

Reads [project] version from packages/haywire-core/pyproject.toml
(foundation package, always at the lockstep version) and shows
"Current release version: X.Y.Z" to the user.

Refs spec internals/specs/versioning-and-publishing.md § release
flow step 0.
EOF
)"
```

---

### Task 4: Procedure step 1 — prompt for new version

**Files:**
- Modify: `.claude/skills/haywire-release/SKILL.md`

- [ ] **Step 1: Append the "Step 1: prompt for new version" section**

Append to `.claude/skills/haywire-release/SKILL.md`:

```markdown

### Step 1 — get the new release version

If the user supplied a version on the invocation line (e.g. `/haywire-release 0.0.2`),
use it. Otherwise ask via `AskUserQuestion`:

> "New release version? Current is X.Y.Z. Use semver (patch / minor / major)."

Validate the input against the regex `^\d+\.\d+\.\d+(?:[a-z0-9.+!*-]*)?$` (PEP 440-ish:
`X.Y.Z` with optional pre/post/dev suffix). Reject and re-prompt on malformed input.

Also reject if the new version equals the current version — the bump script would
report "Nothing to do" and the release would be a no-op.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/haywire-release/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): /haywire-release step 1 — prompt for new version

Accepts version from the invocation line (e.g. /haywire-release 0.0.2)
or asks interactively via AskUserQuestion. Validates against a PEP
440-ish semver regex and rejects no-op bumps (same version as
current).

Refs spec internals/specs/versioning-and-publishing.md § release
flow step 1.
EOF
)"
```

---

### Task 5: Procedure steps 2–5 — gate, bump, diff

**Files:**
- Modify: `.claude/skills/haywire-release/SKILL.md`

- [ ] **Step 1: Append the "Steps 2-5: gate, bump, diff" section**

Append to `.claude/skills/haywire-release/SKILL.md`:

```markdown

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

```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/haywire-release/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): /haywire-release steps 2-5 — gate, preflight, bump, diff

Step 2 runs the fast test suite and verifies the working tree is
clean. Step 3 confirms branch + unpushed-commits state. Step 4 calls
scripts/bump_version.py --dry-run to show the unified diff. Step 5
uses AskUserQuestion to gate the commit/tag/push, with an
intermediate "apply but don't commit" option for power users.

Refs spec internals/specs/versioning-and-publishing.md § release
flow steps 2-5.
EOF
)"
```

---

### Task 6: Procedure steps 6–8 — commit, tag, push

**Files:**
- Modify: `.claude/skills/haywire-release/SKILL.md`

- [ ] **Step 1: Append the "Steps 6-8: commit, tag, push" section**

Append to `.claude/skills/haywire-release/SKILL.md`:

```markdown

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
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/haywire-release/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): /haywire-release steps 6-8 — commit, tag, push

Step 6 applies the bump (idempotent re-run) and commits with the
chore: release vX.Y.Z subject. Step 7 creates a lightweight tag by
default, with an opt-in annotated form. Step 8 detects the remote
name (handles single, multiple, or zero remotes) and pushes branch
+ tag in one round-trip.

Refs spec internals/specs/versioning-and-publishing.md § release
flow steps 6-8.
EOF
)"
```

---

### Task 7: Procedure step 9 — CI handoff + post-release notes

**Files:**
- Modify: `.claude/skills/haywire-release/SKILL.md`

- [ ] **Step 1: Append the "Step 9: CI handoff + recovery" section**

Append to `.claude/skills/haywire-release/SKILL.md`:

```markdown

### Step 9 — CI handoff

Tell the user:

> Tag `v<NEW_VERSION>` pushed to `<REMOTE>`. CI will now:
> 1. Run the fast test suite (Job 1 — gate).
> 2. Build all 7 wheels (Job 2 — build).
> 3. Publish each wheel to PyPI in dependency order, with idempotent skip if a version
>    already exists (Job 3 — publish, OIDC via Trusted Publisher).
> 4. Generate the marketplace and deploy to GitHub Pages (Job 4 — deploy-marketstall).
>
> Watch progress: `gh run watch` (or visit the Actions tab on GitHub).
>
> If a job fails, see
> [`docs/reference/publish_releases.md`](../../docs/reference/publish_releases.md)
> for recovery procedures. The most common cases:
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

- [`scripts/bump_version.py`](../../scripts/bump_version.py) — the version-rewriting
  CLI this skill calls. Documented in [`scripts/README.md`](../../scripts/README.md).
- [`scripts/generate_marketstall.py`](../../scripts/generate_marketstall.py) — the
  marketplace generator that CI's deploy job runs. Not invoked by this skill (CI
  runs it after publish succeeds).
- [`.github/workflows/publish.yml`](../../.github/workflows/publish.yml) — the CI
  publish workflow this skill triggers via the tag push.
- [`docs/reference/publish_releases.md`](../../docs/reference/publish_releases.md) —
  operational guide with prerequisites (Trusted Publisher setup, GitHub Pages config),
  recovery procedures, and tier-transition recipes.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/haywire-release/SKILL.md
git commit -m "$(cat <<'EOF'
feat(skill): /haywire-release step 9 + dry-run + cross-refs

Step 9 hands off to CI with recovery procedures and an opt-in
`gh run watch`. Adds a dedicated section for --dry-run semantics
(stop after step 4, no working-tree changes). Lists what the skill
does NOT do (force-push, PyPI auth, etc.) and cross-references the
related scripts/workflows/docs from Plans A and B.

Refs spec internals/specs/versioning-and-publishing.md § release
flow step 9 + operational notes.
EOF
)"
```

---

### Task 8: End-to-end dry-run verification

**Files:** read-only.

This task verifies the skill works against the live workspace. It uses `--dry-run`
semantics — no commit, no tag, no push — to exercise every command the skill instructs
Claude to run. The plan author (or Claude executing this task) is the human-in-the-
loop for the AskUserQuestion checkpoints.

- [ ] **Step 1: Read the full skill body and check for placeholder gaps**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
wc -l .claude/skills/haywire-release/SKILL.md
grep -nE 'TODO|TBD|FIXME|implement later|fill in|<placeholder>' .claude/skills/haywire-release/SKILL.md && echo "FOUND placeholders" || echo "no placeholders"
```

Expected: file is roughly 150–200 lines. No placeholders. If any are found, fix them
before proceeding.

- [ ] **Step 2: Verify the YAML frontmatter still parses and has the expected fields**

```bash
uv run --with pyyaml python -c "
import yaml, re, pathlib
text = pathlib.Path('.claude/skills/haywire-release/SKILL.md').read_text()
m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
assert m, 'no frontmatter found'
data = yaml.safe_load(m.group(1))
assert data['name'] == 'haywire-release'
assert len(data['description']) > 100  # description should be substantial
print('OK — frontmatter is well-formed.')
print('Description length:', len(data['description']), 'chars')
"
```

Expected: `OK — frontmatter is well-formed.` and a length over 100 chars.

- [ ] **Step 3: Walk through the skill's steps 0–4 against the live workspace**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo

# Step 0: current version
echo "=== Step 0 ==="
grep -E '^version = ' packages/haywire-core/pyproject.toml | head -1
# Expected: version = "0.0.1"

# Step 2: gate tests
echo "=== Step 2 (gate) ==="
uv run pytest -m "not integration" -q 2>&1 | tail -3
# Expected: 1156 passed

# Step 2 also: working tree clean check
echo "=== Step 2 (clean tree) ==="
git status --short
# Expected: only `?? docs/superpowers/` (pre-existing untracked, ignorable)

# Step 3: branch + unpushed
echo "=== Step 3 ==="
git branch --show-current
git log --oneline @{u}..HEAD 2>/dev/null || echo "(no upstream — release skill will note this)"
# Expected: feat/versioning-pre-release-and-bump-script (no upstream — expected)

# Step 4: dry-run diff for a fake 0.0.99 target
echo "=== Step 4 (dry-run bump preview) ==="
uv run python scripts/bump_version.py 0.0.99 --dry-run | tail -3
# Expected: ends with "10 file(s) will change. Target version: 0.0.99."

# Step 8 (remote detection): the skill must handle this
echo "=== Step 8 (remote detection) ==="
git remote
# Expected: haywire-origin
```

Read each output. Confirm the skill's instructions for that step are consistent with
the actual command output. In particular:

- Step 0 shows `version = "0.0.1"` — the skill's "tell the user: Current release
  version: X.Y.Z" instruction is well-defined.
- Step 2 gate passes with 1156 — green.
- Step 3 has no upstream (this branch is local-only). The skill's `git log @{u}..HEAD`
  command returns non-zero in this case (no upstream); the skill must handle the error
  gracefully. **Verify the skill says "2>/dev/null"** in its step-3 command (which it
  does per Task 5 Step 1).
- Step 4 shows the expected diff summary line.
- Step 8 detects `haywire-origin` as the single remote.

If any of these diverge from the skill's instructions, edit the skill to match
reality.

- [ ] **Step 4: Verify the working tree is still clean (the dry-run wrote nothing)**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
git status --short
```

Expected: only `?? docs/superpowers/` (and `?? .claude/skills/haywire-release/` is now
tracked because we committed it in earlier tasks; should not appear here). The
dry-run bump previewed but didn't write. The pytest run didn't change tracked state.

- [ ] **Step 5: Re-run ruff and the full test suite to confirm no regression**

```bash
uv run ruff check .
uv run pytest -m "not integration" -q 2>&1 | tail -3
```

Expected: ruff clean, 1156 passed (the new skill file isn't Python and pytest doesn't
collect anything from it).

- [ ] **Step 6: Confirm the commit history**

```bash
git log --oneline -10
```

Expected: at the top, 6 commits from Plan C tasks 2–7 (one per task), on top of Plan B's
squashed commit:

```
<sha> feat(skill): /haywire-release step 9 + dry-run + cross-refs
<sha> feat(skill): /haywire-release steps 6-8 — commit, tag, push
<sha> feat(skill): /haywire-release steps 2-5 — gate, preflight, bump, diff
<sha> feat(skill): /haywire-release step 1 — prompt for new version
<sha> feat(skill): /haywire-release step 0 — print current version
<sha> feat(skill): /haywire-release scaffold (frontmatter + intro)
655fc5fd feat: CI publish workflow + marketstall generator
28537691 feat: versioning migration + bump_version.py script
```

---

## Self-Review (already performed by the plan author)

### Spec coverage

Spec § release flow has 10 numbered steps (0–9). Mapping:

| Spec step | Plan task | Skill section |
|-----------|-----------|----------------|
| 0 — print current version | Task 3 | Step 0 |
| 1 — prompt for new version | Task 4 | Step 1 |
| 2 — pytest gate | Task 5 | Step 2 |
| (extra) preflight checks | Task 5 | Step 3 |
| 3 — patch pyproject versions | Task 5 (preview) + Task 6 | Steps 4 (preview), 6 (apply) |
| 4 — update ~= constraints | (same as step 3 — bump_version handles both) | (same) |
| 5 — show unified diff | Task 5 | Step 4 |
| 6 — ask to commit/tag/push | Task 5 | Step 5 |
| 7 — commit `chore: release v…` | Task 6 | Step 6 |
| 8 — tag v… and push branch + tag | Task 6 | Steps 7 + 8 |
| 9 — CI takes over | Task 7 | Step 9 |

All 10 steps mapped. ✅

### Out of scope (correctly deferred to other plans)

- CI side of the flow — covered by Plan B's `publish.yml`. The skill triggers it via
  the tag push.
- `haywire share` / `haywire init` — Plan D.
- Marketplace runtime / Library Manager — Plans E and F.

### Placeholder scan

No "TBD", "implement later", "similar to Task N" — every step contains the actual content. ✅

### Type / signature consistency

Skill instructions reference these external symbols/commands:
- `scripts/bump_version.py <NEW_VERSION>` — matches Plan A's positional arg.
- `scripts/bump_version.py --dry-run` — matches Plan A.
- `scripts/bump_version.py --yes` — matches Plan A.
- `git tag v<NEW_VERSION>` — matches spec § release flow step 8.
- `git push <REMOTE> HEAD v<NEW_VERSION>` — branch + tag in one push, matches spec.
- The remote name is detected (`git remote`), not hardcoded — handles `haywire-origin`. ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-haywire-release-skill.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute in this session with checkpoints.

Which approach?
