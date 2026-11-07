---
name: haywire-workflow
description: Step-by-step procedures for working in this repository through branches, pull requests and CI — starting a task, committing, pushing and opening a PR, reading CI, asking the user for a decision, merging, cleaning up, keeping a branch current, and working in a second worktree. Use it whenever starting, shipping or merging a piece of work, when a PR or CI run needs attention, or when the user has to decide something.
---

# Working through branches and pull requests

The rules are in CLAUDE.md, *Git and pull requests*; the reasons and traps in
[.insights/project_pr_workflow.md](../../../.insights/project_pr_workflow.md). This skill
is the how.

## Asking the user for a decision

Every time the user has to decide or review something — a PR to merge, an option to
pick, a failure to judge — hand them everything needed to decide in one look. They
should never have to go and find it.

- **Link it.** A PR or issue: its full URL. A CI run: its URL
  (`gh run view <id> --json url --jq .url`). A local file: a markdown link with the line,
  `[name.py:42](path/to/name.py#L42)`. A diff: the PR's *Files changed* URL
  (`<pr-url>/files`).
- **Say what is decided**, the options lettered, and which one you recommend and why,
  in a sentence each.
- **Put the evidence next to it:** test results, the failing check, the measured
  number, the relevant lines. Quote briefly; link the rest.

A PR ready to merge is reported as: its URL, one line on what it changes, the CI result
with the run's URL, anything the user should look at first (with links), then the
question.

## Starting a task

```sh
git switch master
git pull --ff-only
git switch -c <kind>/<short-name>        # kind: feat, fix, chore, docs, test
```

If another session already works in this folder, use a worktree instead (below).

## Before a substantial change: a baseline

Before a multi-file refactor, a signature change, a type-system edit, or anything whose
failures would be hard to attribute, check the area first:

```sh
uv run ruff check <path>
uv run mypy <path>
```

The code base has no errors; if it does, start an error-fixing session with the user
before the change. After the edit, run the same commands: anything new is yours.

## Choosing and running tests

Run the smallest set that covers the change. The full suite is CI's job on every push.

```sh
uv run pytest tests/path/to/file.py -q          # one file: the default while iterating
uv run pytest tests/some_dir/ -q                # one area
uv run pytest tests/ -k "edge" -q               # by name
uv run pytest -m "not browser and not perf" -n 4 -q   # whole non-browser tier, ~4 min
uv run pytest -m browser -n 4 -q                # browser tier, ~2 min
```

`-n 4`, never more; a run that hangs to the 120 s timeout is a lock cycle, not
flakiness. Redirect long runs to a file and read the tail; the exit code is the signal.
Tiers, parallelism and test traps: `tests/README.md`.

## Committing

Commit on the branch whenever a step is done; no need to ask. Before each commit:

```sh
uv run ruff check <changed files>
uv run ruff format --check <changed files>
uv run mypy <changed packages>
uv run pytest <tests of the changed areas> -q
``` Commit messages follow the repository's style
(`feat(area): …`, `fix(area): …`) and end with the attribution line the session gives.

## Pushing and opening the PR

On the first push, open a draft PR; later pushes update it.

```sh
git push -u origin <branch>
gh pr create --draft --base master --title "<type(area): summary>" --body "<what and why>"
```

The PR body says what changed and why, lists anything still owed (a live check, a
companion branch), and ends with the attribution line. Give the user the PR's URL.

## Reading CI

```sh
gh pr checks                       # status of this branch's PR
gh run watch <id> --exit-status    # wait; run it in the background
gh run view <id> --log-failed      # only the failing steps
```

Fix a failure with another commit and push. A cancelled job is not a failure: a newer
push cancelled it.

## Finishing: ready, review, merge

1. When the work is done, mark the PR ready: `gh pr ready <n>`. macOS joins the checks.
2. Ask the user to review, as in *Asking the user for a decision*.
3. Merge only on the user's word ("merge"), and only once the checks are green:

   ```sh
   gh pr checks <n> --watch
   gh pr merge <n> --squash
   ```

4. Clean up. GitHub deletes the remote branch; delete the local one in a command of its
   own (the hook reads the whole command line, so never next to a push):

   ```sh
   git switch master
   git pull --ff-only
   git branch -d <branch>
   ```

## Keeping a branch current

When `master` moved on and the branch needs it (a conflict, a fix it depends on):

```sh
git fetch origin
git merge origin/master
```

Generated library docs (`barn/*/README.md`, `OVERVIEW.md`, `QUICKREF.md`, `docs/*.md`)
that conflict are regenerated with `uv run haywire docs --all`, never merged by hand.

## A second session in its own worktree

Two sessions in one folder overwrite each other's uncommitted work and branch switches.
A second session gets a worktree: another folder on its own branch, sharing the history.

```sh
git worktree add .worktrees/<name> -b <kind>/<name> origin/master
```

A worktree has no Python environment and none of the gitignored links
(`barn/haybale-spandrel`, `barn/haybale-visiongraph`). Work that only touches docs,
skills or workflows needs neither. Work that runs code or tests needs `uv sync` there
first, and two sessions running browser tests at once collide on the harness ports
(8090 and up). When the branch is merged:

```sh
git worktree remove .worktrees/<name>
```
