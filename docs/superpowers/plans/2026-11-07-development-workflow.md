# Development workflow: branches, pull requests, CI and parallel work

Status: agreed 2026-11-07 (decisions A–D as recommended). Steps 1–5 done 2026-11-07 (CI landed in PR #7); step 6, parallel work, open.

The goal: work on several things at once, never wait for the full test suite on this
machine, and only let tested work reach `master`. GitHub does the testing and the gating.
Locally, only fast checks run.

## 1. Primer: pull requests and CI

**Branch.** Every piece of work lives on its own branch (`feat/…`, `fix/…`, `chore/…`).
`master` only ever receives finished, tested work.

**Push.** Uploads the branch to GitHub. Every push starts the test workflows there.

**CI (continuous integration).** GitHub Actions runs the workflows in `.github/workflows/`
on GitHub's machines: lint, types, the test tiers. Each push gets a status: running, passed
or failed, shown as a dot, tick or cross beside the commit. This repository is public, so
Actions minutes on GitHub's standard machines cost nothing.

**Pull request (PR).** A page on GitHub that asks to merge a branch into `master`. It shows
the diff, the check results of the latest push, and any comments. It updates itself with
every push. A PR can start as a *draft* (work in progress) and be marked *ready* later.
Opening one early costs nothing and gives one place to watch a branch.

**Branch protection (a ruleset on `master`).** GitHub rules that refuse:

- a merge whose required checks have not passed,
- a direct push to `master` that bypasses a PR (optional, see decision B),
- a force push or a deletion of `master`.

This turns "only tested work reaches master" and "nothing destructive on master" from
habits into rules GitHub enforces, for people and agents alike. As the repository's
admin, you can still bypass them deliberately.

**Merging.** The PR's button. *Squash and merge* turns the whole branch into one commit
on `master`, which is what the slices so far did by hand. The branch is then deleted on
GitHub automatically. *Auto-merge* is the same button pressed in advance: the PR merges
itself the moment its checks pass.

**Reading results.** On GitHub: the PR's *Checks* tab, failed tests annotated on the lines
that failed, and a summary per run. From the terminal, which is how Claude reads them:

```sh
gh pr checks              # status of the current branch's PR
gh run watch              # wait for the running workflow
gh run view --log-failed  # only the failing steps' output
```

## 2. The day-to-day flow

| Step | Who | What runs | Time |
|---|---|---|---|
| Start a task | Claude | `scripts/worktree new <name>`: branch + worktree + environment | ~1 min |
| Iterate | Claude | the tests of the area being changed | seconds |
| Commit | Claude | ruff on changed files, mypy on changed packages, area tests | < 1 min |
| Push | Claude | CI: everything | ~10 min, in the background |
| Open PR | Claude | `gh pr create --draft` on the first push | |
| Fix | Claude | reads failures with `gh`, fixes, pushes again | |
| Merge | see decision B | squash and merge once green | |
| Release | you | `/haywire-release` from `master`, as now | |

Nobody waits for the full suite. A failure in CI is fixed with another commit on the
branch; the squash merge folds it away.

## 3. Test tiers

| When | Command | Purpose |
|---|---|---|
| Iterating | `uv run pytest tests/<area>/` | fast feedback |
| Before commit | ruff + mypy on what changed, area tests | catch the obvious |
| Every push (CI) | lint, mypy, `-m "not browser and not perf" -n 4`, `-m browser -n 4` | the gate |
| On demand | `/verify`, rewritten to use `-n 4` (~5 min instead of ~18) | a local full run when wanted |

The rule "always run `/verify` before commit" goes away. It is not in this repository or
your settings files; it arrives with Claude's tool instructions, so its source has to be
found and changed. Until then, CLAUDE.md states the new rule explicitly.

Test selection (running only the tests a change affects, for example `pytest-testmon`) is
deferred: with CI carrying the full suite, nothing waits for it.

## 4. CI changes

`tests.yml` triggers on `main` and `develop`, which do not exist here, so it has never run.
Its integration step has `continue-on-error`, so it could not fail either. Rewrite:

- Trigger on every push and on PRs to `master`; cancel a run when a newer push arrives.
- One workflow, four jobs: **lint** (ruff check and format), **types** (mypy, the CLAUDE.md
  command), **tests** (`-m "not browser and not perf" -n 4`), **browser** (installs
  Chromium, `-m browser -n 4`). The jobs run side by side.
- Write JUnit XML and publish it, so failures appear as annotations and a summary.
- Linux on every push; macOS too on PRs (decision C).
- Fold `ruff.yml` and `mypy.yml` into it; keep `ty.yml`, `docs.yml` and the publish
  workflows as they are.

Expect the first runs to fail on things this Mac never shows: the suite has never run on
Linux. Likely suspects: tests needing the local-only libraries `barn/haybale-spandrel` and
`barn/haybale-visiongraph` (gitignored symlinks, absent on GitHub) must skip there; case-
sensitive paths; browser fonts; the timing-sensitive cost tests on slower machines.

## 5. Parallel work

**One worktree per stream.** A git worktree is a second checkout of the same repository in
another folder, on its own branch, sharing the history. `.worktrees/` is already gitignored
for this. Each stream gets its own VS Code window with its own Claude session (decision D).

`scripts/worktree new <name>` (to write) does what a fresh worktree needs here:

1. `git worktree add .worktrees/<name> -b <kind>/<name> master`
2. Recreate the gitignored symlinks `barn/haybale-spandrel` and `barn/haybale-visiongraph`.
3. `uv sync` (its own `.venv`; fast from uv's cache).
4. Give the worktree its own ports: the studio port in its workspace
   `.haywire/settings.json`, and a harness base port for browser tests.

`scripts/worktree remove <name>` removes it once its PR is merged.

**Found while checking:**

- **Browser tests collide across worktrees.** The harness binds 8090 + worker number
  (`tests/ui/harness/conftest.py`). Two worktrees running browser tests at once fight for
  the same ports and fail in confusing ways. Fix: read the base port from an environment
  variable the worktree sets.
- **The studio port** defaults to 8124; two studios need two ports (step 4 above).
- **Shared global state.** `~/.haywire` (global settings, `db/`, volumes, security) is
  shared by all worktrees. Usually harmless; a marketplace install made in one stream is
  seen by all.
- **CodeGraph** indexes the main folder; a new worktree has no `.codegraph/` until indexed.
- **Merge conflicts.** Streams that touch the same files conflict at merge time. Worst
  offenders here: the generated library docs (`OVERVIEW.md`, `QUICKREF.md`, `docs/*.md`),
  `glossary.md`, `CLAUDE.md`. Generated docs are regenerated after updating a branch from
  `master`, never merged by hand. Choose parallel streams in different areas where possible.

**Keeping a branch current.** When `master` moves on, a long-running branch takes it in
with `git merge master` (or a rebase). That is a normal, non-destructive step.

## 6. Local safety: the git hook

`.claude/hooks/block-dangerous-git.sh` blocks every `git push`. It becomes:

- **Allowed:** `git push` of branches and `master`, `git push -u`.
- **Still blocked:** force pushes (`--force`, `-f`, `+refspec`), deleting remote branches
  (`--delete`, `:branch`), `reset --hard`, `clean -f`, `branch -D`, `checkout .`,
  `restore .`, and pushing tags (a tag push publishes a release; that stays yours).

GitHub's ruleset backs this up on `master` independently of the hook.

## 7. Decisions

**A. Commits on feature branches.**
(a) Claude commits freely on feature branches; your consent is needed for merges to
`master` only. (b) Unchanged: consent for every commit.
Recommended: (a). A branch commit is a checkpoint, and the squash merge is the commit
`master` keeps.

**B. Who merges to `master`.**
(a) You say "merge" and Claude runs `gh pr merge --squash`. (b) You click *Squash and
merge* on GitHub. (c) Claude enables auto-merge when opening the PR.
Recommended: (a) at first, (c) later per PR once you trust the checks. Direct pushes to
`master` are then refused by the ruleset, except your own deliberate bypass.

**C. macOS in CI.**
(a) Linux on every push, macOS on PRs. (b) Linux only.
Recommended: (a). You develop on macOS and users will run it there.

**D. How parallel streams run.**
(a) One VS Code window and Claude session per worktree. (b) One session dispatching
subagents into worktrees.
Recommended: (a). Each stream keeps its own conversation and context; you switch windows.

## 8. Transition, in order

Each step is small and usable on its own.

1. **CI** (branch `chore/ci`). Rewrite `tests.yml`, push, iterate until green on GitHub.
   Claude needs push access for this step: the hook change from section 6 goes first.
2. **GitHub settings** (you, in the repository's *Settings → Rules* and *General*):
   ruleset on `master` (require a PR, require the four checks, block force push and
   deletion), allow squash merge only, enable auto-merge, delete branches after merge.
   Claude can walk you through it.
3. **First PR.** Push `feat/carrier-metadata` (and the visiongraph and spandrel branches to
   their repositories) and merge it through the new flow.
4. **Local rules.** CLAUDE.md gets a short *Git and testing* section with sections 2, 3 and
   6; `/verify` uses `-n 4`; `/haywire-release` follows section 9; memory updated (commit
   consent, push access).
5. **Parallel work.** `scripts/worktree`, the harness port fix, then two streams side by
   side as the trial.
6. **Later, if CI time ever hurts:** test selection, a merge queue, splitting the browser
   tier across more machines.

Sibling repositories (`haybale-visiongraph`, `haybale-spandrel`) can adopt the same flow
afterwards; they are smaller and their suites are fast.

## 9. Releases

`master` only holds commits whose checks passed, so a release no longer runs the suite
locally. The version bump goes through a short PR like any other change, because the
ruleset refuses direct pushes to `master`.

`/haywire-release` becomes:

1. Check that the latest `master` commit's CI run passed (`gh run list --branch master`);
   stop if it did not, or if it is still running.
2. Bump the versions on a `release/vX.Y.Z` branch, commit `chore: release vX.Y.Z`, push,
   open a PR and enable auto-merge.
3. Once it merges, tag the merged commit on `master` (a squash merge makes a new commit;
   the branch's commit is not the one to tag).
4. You push the tag. `publish.yml` builds and publishes, as now. Its own unit-test gate
   stays as a last check.

The local test run and ruff step leave the skill; the dependency audit stays. Updated in
step 4 of section 8.

**Later, if stamping locally gets in the way:** a manual *Release* workflow on GitHub that
takes the version and does steps 2 and 3. It needs a token other than the workflow's own,
since a tag pushed with `GITHUB_TOKEN` does not start `publish.yml`, and permission to
write to the protected `master`.

**Identity.** Claude pushes with your git credentials, so GitHub cannot tell the two of you
apart: any bypass of the ruleset you keep for yourself applies to Claude too. The local
hook is what keeps destructive commands on `master` with you; the ruleset guards against
accidents by either. A separate GitHub identity for Claude would split the two, if ever
needed.
