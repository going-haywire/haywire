---
name: haywire-workflow
description: Step-by-step procedures for working in this repository through branches, pull requests and CI — starting a task, committing, pushing and opening a PR, reading CI, asking the user for a decision, merging, checking master after a merge, cleaning up, keeping a branch current, running parallel sessions in worktrees, and setting up a second machine. Use it whenever starting, shipping or merging a piece of work, when a PR or CI run needs attention, or when the user has to decide something.
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

This is for working in the main folder alone. When sessions run side by side, each task
gets a worktree instead (*Parallel sessions*).

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
```

Commit messages follow the repository's style
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

4. Check `master` after the merge. Each PR passed CI against the `master` it last saw;
   two PRs that pass alone can still break `master` together. Watch the merge's run:

   ```sh
   gh run list --branch master --workflow CI --limit 1    # the merge's run id
   gh run watch <id> --exit-status
   ```

   If it fails, fix forward at once: a `fix/` branch and PR for the break, and tell the
   user with the run's URL and the PR's URL. Then look at the other open PRs:

   ```sh
   gh pr list --state open --json number,title,mergeable,url
   ```

   A PR now `CONFLICTING` needs *Keeping a branch current*; tell the session or the user
   that owns it.

5. Clean up. GitHub deletes the remote branch; delete the local one in a command of its
   own (the hook reads the whole command line, so never next to a push). In a worktree,
   remove the worktree first (*Parallel sessions*), then run this in the main folder:

   ```sh
   git switch master
   git pull --ff-only
   git branch -d <branch>
   ```

   If `git branch -d` refuses because the squash merge is not an ancestor, the branch is
   the user's to delete (`-D` is blocked).

## Keeping a branch current

When `master` moved on and the branch needs it (a conflict, a fix it depends on):

```sh
git fetch origin
git merge origin/master
```

Conflicts are resolved by hand except in generated files:

- Generated library docs (`barn/*/README.md`, `OVERVIEW.md`, `QUICKREF.md`, `docs/*.md`)
  are regenerated with `uv run haywire docs --all`.
- `uv.lock` is taken from `master` and relocked:
  `git checkout origin/master -- uv.lock && uv lock`.

Then run the tests of both sides' areas before committing the merge.

## Parallel sessions

Each task runs in its own worktree (another folder on its own branch, sharing the
history) with its own session. Two sessions in one folder overwrite each other's
uncommitted work and branch switches.

**Starting one.** The main folder stays on an up-to-date `master` and holds no task work:
it is where worktrees branch from. The user creates the worktree in
[herdr](https://herdr.dev/guide/): right-click a space whose terminal is in the main
folder → *New worktree*, branch name such as `fix/edge-drag`. herdr checks it out at
`~/.herdr/worktrees/haywire-repo/fix-edge-drag` and opens a space there, listed under the
repo. The worktree items appear only on a space herdr sees inside the repo; *Open
worktree* opens a space on an existing one. Without herdr:

```sh
git worktree add ~/.herdr/worktrees/haywire-repo/<kind>-<name> -b <kind>/<name> origin/master
```

**First thing in a new worktree**, with the system Python since there is no environment
yet:

```sh
python3 scripts/worktree_setup.py
```

It starts the branch from the latest `origin/master` (if the branch has no commits yet;
otherwise it reports how far behind it is), links the sibling libraries, runs `uv sync`,
and gives the studio its own port in `.haywire/settings.json`. Safe to run again. A
session started in the worktree still reads the main folder's memory; CodeGraph indexes
only the main folder, so search with grep there.

**Rules while streams run side by side:**

- Never `git stash`: the stash is shared by every worktree. Commit work in progress on
  the branch instead.
- Run only the tests of the area changed; CI runs the whole suite. Browser tests in two
  worktrees at once are fine: each checkout has its own harness ports.
- Only one stream at a time changes `haybale-spandrel` or `haybale-visiongraph`. They are
  linked, not copied, so every worktree sees the same checkout and its branch.
- `~/.haywire` (global settings, security document, models, volumes) is shared too: a
  library installed or a setting changed there is seen by every stream.

**When the branch is merged**, the user right-clicks the worktree's space → *Remove
worktree* in herdr (it deletes the folder and keeps the branch), or without herdr:

```sh
git worktree remove ~/.herdr/worktrees/haywire-repo/<kind>-<name>
```

then *Finishing* step 5 deletes the branch from the main folder.

**A second machine** works on its own clone: [second-machine.md](second-machine.md).
