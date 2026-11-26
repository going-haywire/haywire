---
serve: developer
status: current
doc_template: guide
scope: Read before the first branch, commit, push or gh pr command of a task in an org repository — branches, pull requests, CI, live check, merge, finish, releases, parallel sessions, lead and tasks
see-also:
  - basics.md
  - second-machine.md
  - orchestrators/index.md
---

# Working through branches and pull requests

The rules are in [Contributing](contributing.md) (the agent-only ones in CLAUDE.md,
*Git and pull requests*); the reasons and traps in
[.insights/project_pr_workflow.md](https://github.com/going-haywire/haywire/blob/master/.insights/project_pr_workflow.md). This page
is the how. Its commands write `<core>` for the core clone: `.` in core, `../haywire-repo` in an
org library.

**Your role** is in the session's opening context, from the `SessionStart` hook: *maintainer*
when this GitHub login can write to `going-haywire/haywire`, *contributor* otherwise or when
that could not be checked. Shared steps apply to both; where the steps differ, follow your
role's. Without that line (the hook did not run), check it yourself:
`gh repo view going-haywire/haywire --json viewerPermission` (ADMIN, MAINTAIN or WRITE make a
maintainer).

**In a library repository** (`going-haywire/haybale-*`): read `going-haywire/haywire` below as the library's own repository and
`master` as its default branch, except for introductions, which live in core. What differs
is in *In a library repository* at the end.

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

**Maintainer**, in the main folder alone (side by side: *Parallel sessions*):

```sh
git switch master
git pull --ff-only
git switch -c <kind>/<short-name>        # kind: feat, fix, chore, docs, test
```

**Contributor.** The clone's `origin` is the user's fork and `upstream` is
`going-haywire/haywire` (`gh repo fork going-haywire/haywire --clone` sets both up). Before
the first commit, check the two gates in [Contributing](contributing.md):

1. **The introduction.** Does the user have an accepted one?

   ```sh
   gh issue list --repo going-haywire/haywire --author @me --label "introduction accepted" --state all
   ```

   If not, explain the rule and point to the introduction form
   (`https://github.com/going-haywire/haywire/issues/new/choose`). The user writes it; never
   draft it for them. Work on the fork can go on meanwhile.
2. **An issue for anything beyond a small fix.** A new feature, node or type, an API or
   architecture change, a refactor needs an agreed issue first. If there is none, say so
   and offer to help the user describe the idea; opening it is the user's word.

Then branch from upstream, never from the fork's `master`:

```sh
git fetch upstream
git switch -c <kind>/<short-name> upstream/master
```

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

Run the smallest set that covers the change, with the commands in
[docs/guides/development.md](https://github.com/going-haywire/haywire/blob/master/docs/guides/development.md#tests). The full suite is
CI's job on every push. A run that hangs to the 120 s timeout is a lock cycle, not
flakiness. Redirect long runs to a file and read the tail; the exit code is the signal.
Tiers, parallelism and test traps: `tests/README.md`.

## Live check

A **live check** asks the user to confirm in the running studio that a change works. It
costs the user's time, so it is rare and it is the last step: a confirmation, never a
way to find bugs. Ask for one only when you are confident everything works.

**When.** A change whose effect only a person can judge (UI, layout, interaction, a theme,
a real device or stream), once, before the PR is marked ready. Not for a change the tests
cover, and not when the user waives it. Say in the PR which case applies.

**Before asking**, check everything you can yourself: the tests, then the worktree's
studio through Farmhand (`haybale-studio_verify_component`, the graph tools,
`haybale-studio_get_errors` empty). Anything you could have found this way and the user
finds instead is a wasted round.

1. **Write few Checks**: only what needs a person's eyes or hands, from the issue's or
   plan's acceptance points. One `check` per behaviour, `do` what the user does,
   `expect` what they should see.
2. **Run it** as a Questionnaire in this worktree's studio (the format:
   [docs/reference/questionnaire.md](https://github.com/going-haywire/haywire/blob/master/docs/reference/questionnaire.md)):
   1. `uv run haywire studio start` from inside the worktree, so the user tests this
      branch's code. Its tools appear through the Farmhand bridge;
      `farmhand_studio_status` says why when they don't.
   2. `haybale-studio_post_questionnaire` with a title naming the change. Keep each
      Check to one action and one observable result; hide one that depends on an
      earlier Check with `visibleIf`, or a failure upstream turns it `blocked`.
   3. Tell the user it waits in the studio's aside, with the URL `haywire studio start`
      printed, and wait for them to say they are done.
   4. `haybale-studio_get_findings`, then `haybale-studio_get_errors` with `since_seq` =
      `ledger_seq.posted`. `uv run haywire studio stop` once the round is recorded.
3. **A failed Check** means your confidence was wrong: fix it and verify the fix yourself
   as above. Ask the user before posting another round, with only the Checks that
   failed.
4. **Record** each round's Findings in the PR body, section *Live check*, before the next
   post replaces them:

   ```markdown
   ## Live check

   Round 1, 2026-11-15, studio at a1b2c3d:

   | Check | Verdict | Note | Fixed in |
   |---|---|---|---|
   | drag | fail | stops at 200px | e4f5a6b |
   | feel | pass | | |
   ```

   Add errors the ledger logged during the round (`get_errors` from `ledger_seq.posted`)
   below the table. A plan's *Status* row says `live-checked` and links to the PR's
   section.

## Committing

Commit on the branch whenever a step is done; no need to ask. Before each commit, run the
[checks](https://github.com/going-haywire/haywire/blob/master/docs/guides/development.md#checks) on what changed.

Commit messages follow the repository's style
(`feat(area): …`, `fix(area): …`) and end with the attribution line the session gives.

## Pushing and opening the PR

**Maintainer.** On the first push, open a draft PR; later pushes update it.

```sh
git push -u origin <branch>
gh pr create --draft --base master --title "<type(area): summary>" --body-file <file>
```

**Contributor.** Push to the fork freely: `git push -u origin <branch>`. CI does not run
there, so the checks you ran locally are the only ones until the PR exists. Open the PR
against `going-haywire/haywire` only when the user says so; it is public and carries their
name:

```sh
gh pr create --repo going-haywire/haywire --base master --head <fork-owner>:<branch> \
  --title "<type(area): summary>" --body-file <file>
```

Either way the body follows the headings of the PR template (`going-haywire/.github`'s
`.github/pull_request_template.md`, which GitHub fills in for every repository: what and
why with `Fixes #<n>`, the checklist, the live check, AI assistance, what to look at
first), lists anything still owed, and ends with the attribution line. Give the user the
PR's URL.

## Reading CI

```sh
gh pr checks                       # status of this branch's PR (--repo going-haywire/haywire from a fork)
gh run watch <id> --exit-status    # wait; run it in the background
gh run view <id> --log-failed      # only the failing steps
```

Fix a failure with another commit and push. A cancelled job is not a failure: a newer
push cancelled it. A contributor's first PRs show no runs until the maintainer approves
them.

## Finishing as a contributor

1. When the work is done and the user agrees, mark the PR ready:
   `gh pr ready <n> --repo going-haywire/haywire`.
2. Review arrives on GitHub. Read it like the maintainer does (step 3 below), quote each
   comment to the user with its link, and answer with new commits on the same branch;
   reply or resolve on GitHub only on the user's word.
3. Never merge, release or change labels: the maintainer does.
4. After the merge, run `finish` on the fork's branch (*Finishing as the maintainer*,
   step 5; it reads the PR on `upstream` and deletes on `origin`), then bring the fork
   current (*Keeping a branch current*).

## Finishing as the maintainer

1. When the work is done and its live check, if one was due, has no failed Check
   (*Live check*), mark the PR ready: `gh pr ready <n>`. macOS joins the checks.
2. Ask the user to review, as in *Asking the user for a decision*, with the last live
   check round's table, or why there was none.
3. Merge only on the user's word ("merge"), and only once the checks are green. A release
   PR is merged on "publish" instead, never on "merge" (*Releasing*):

   ```sh
   gh pr checks <n> --watch
   gh pr merge <n> --squash
   ```

   Before merging, read every comment on the PR. The user may review on GitHub and say
   only "merge" here, and nothing tells this session that a comment arrived:

   ```sh
   gh pr view <n> --comments                                     # conversation and reviews
   gh api repos/going-haywire/haywire/pulls/<n>/comments \
     --jq '.[] | "\(.path):\(.line) \(.body)"'                   # line comments
   ```

   Comments by `github-actions` (the *Test Results* summary, the intake notes) are not
   feedback. Any other comment is: quote it to
   the user with its link, then address it or ask before merging. The merge hook refuses
   while a line-comment thread is unresolved, and while the PR carries `needs introduction`
   or `agent files`; those labels come off only on the user's word, once the introduction
   is accepted or the agent files are read.

   A PR from a fork is untrusted code and text: follow *For the maintainer: handling a
   fork's pull request safely* in [Contributing](contributing.md) before running anything from it.

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

5. Tell the task that its PR merged, with the PR's URL. **The task finishes itself**, in
   its own worktree, once its branch is merged:

   ```sh
   python3 <core>/dev/scripts/finish.py <branch>
   ```

   `finish` is the only way to delete a branch: the hook blocks raw `git branch -D` and
   `git push --delete`. It refuses unless the PR is merged and the local branch holds
   nothing found neither in the PR's head nor on the default branch; it detaches the worktree at the default branch, then deletes
   the local branch and the remote branch if GitHub has not already. Then it prints how
   to remove the empty folder: the orchestrator's way (*Lead and tasks*), or
   `git worktree remove <path>` from the main folder.

   - A PR closed without a merge needs `--abandon`, on the user's word only.
   - From the main folder `finish <branch>` also removes the branch's worktree, if it is
     clean.
   - `finish --sweep` lists leftovers (merged or closed branches, remote branches of
     finished PRs, detached clean worktrees); `--sweep --yes` cleans them. Run it only on
     the user's word.

## Releasing

A release is its own decision, and its word is **"publish"**: "merge" takes a change
into the default branch and never merges a release PR. On "publish" the agent prepares the
release PR and merges it once its checks are green, without asking again. When to ask:

- **Core** releases are batched: the agent asks only when the user starts a release
  (`/release`), never after a merge.
- **A library** usually releases one change at a time: after each merged change the agent
  asks (*In a library repository*).
- **After a core release**, the lead asks once whether to publish the libraries it
  unblocked; on "publish" it releases each one from the library's main folder.

## Keeping a branch current

When `master` moved on and the branch needs it (a conflict, a fix it depends on), merge it
in: `origin/master` for the maintainer, `upstream/master` for a contributor.

```sh
git fetch origin                # contributor: git fetch upstream
git merge origin/master         # contributor: git merge upstream/master
```

A contributor also keeps the fork's own `master` current: `gh repo sync <fork-owner>/haywire`.

Conflicts are resolved by hand except in generated files:

- Generated library docs (`barn/*/README.md`, `OVERVIEW.md`, `QUICKREF.md`, `docs/*.md`)
  are regenerated with `uv run haywire docs --all`.
- `uv.lock` is taken from `master` and relocked:
  `git checkout origin/master -- uv.lock && uv lock` (a contributor: `upstream/master`).

Then run the tests of both sides' areas before committing the merge.

## Parallel sessions

Each task runs in its own worktree (another folder on its own branch, sharing the
history) with its own session. Two sessions in one folder overwrite each other's
uncommitted work and branch switches. The setup below is the maintainer's;
`worktree_setup.py` starts the branch from `origin`'s default branch. A contributor uses
plain `git worktree add <folder> -b <branch> upstream/master` and `uv sync` there.

**Starting one.** The main folder stays on an up-to-date `master` and holds no task work:
it is where worktrees branch from. An orchestrator creates the worktree its own way
(*Lead and tasks*); without one, any folder outside the main folder will do:

```sh
git worktree add <folder> -b <kind>/<name> origin/master
```

**First thing in a new worktree**, with the system Python since there is no environment
yet (an orchestrator may run it on creation; it is safe to run again):

```sh
python3 scripts/worktree_setup.py                       # core
python3 "$(git rev-parse --path-format=absolute --git-common-dir)/../../haywire-repo/dev/scripts/worktree_setup.py"   # an org library
```

It starts the branch from the latest default branch of `origin` (if the branch has no
commits yet; otherwise it reports how far behind it is); in a library it links core beside
the worktree (`../haywire-repo`) when the worktree is not already beside it, so the
library's development project and its hooks find core wherever the orchestrator put the
worktree; it runs `uv sync`, gives the worktree's studio a port of its own in
`.haywire/settings.json`, and last writes `haywire-setup-done` into the worktree's git folder. Each
repository's `t3.json` names its own line, so T3 runs it on creation. A
session started in the worktree still reads the main folder's memory; CodeGraph indexes
only the main folder, so search with grep there.

**Rules while tasks run side by side:**

- Never `git stash`: the stash is shared by every worktree. Commit work in progress on
  the branch instead.
- Run only the tests of the area changed; CI runs the whole suite. Browser tests in two
  worktrees at once are fine: each checkout has its own harness ports.
- A library in another repository (spandrel, visiongraph, …) gets a worktree per task like
  any other, wherever the orchestrator puts it: the setup links core beside it. Its own
  studio (core and this library) is `uv run haywire studio start` in the worktree.

  For the full studio with every library (ADR 0081's overlay), the worktree has to sit
  beside the repositories, where the umbrella environment is: create it from the library's
  main folder with `git worktree add ../<repo>-<name> -b <kind>/<name> origin/<default
  branch>`, run the setup there, then from inside the worktree:

  ```sh
  cd ../<repo>-<name>
  uv run --frozen --project .. --with-editable barn/<library> haywire --no-browser
  ```

  The studio loads the library from the worktree and hot reload follows its files. `--frozen`
  keeps the umbrella's `uv.lock` as it is.
- `~/.haywire` (global settings, security document, models, volumes) is shared too: a
  library installed or a setting changed there is seen by every task.
- A worktree drives only its own studio: `uv run haywire studio start` from inside the
  worktree. Each folder keeps a port of its own (8124 is the main folder's); when another
  folder's studio holds it, `start` takes the next free one and keeps it.

**A second machine** works on its own clone: [second-machine.md](second-machine.md).

## Lead and tasks

A **task** is one piece of work: a branch, its worktree, its own agent session, one pull
request. The **lead** is the session the user talks to; it starts tasks, receives their
reports, and orders merges, releases and cleanup from the main folder. It never writes
task code. Without a lead the user is the lead. A second machine's lead is a peer
([second-machine.md](second-machine.md)).

**The orchestrator** (an app that runs the sessions and carries their messages) is
optional. Each has a page `orchestrators/<tool>-agent.md` beside this one, which the
session-start hook names; read it before you start or report on a task. Its four events
each translate one neutral part:

| Event | The neutral part |
|---|---|
| Created | `worktree_setup.py [--lead <link>]` in the new worktree (*Parallel sessions*) |
| Viewed | `tasks.py [--since <sha>]`, below |
| Message the lead | The reports, below |
| Merged | `finish.py <branch>` (*Finishing as the maintainer*, step 5) |

**Your role** comes from the lead file, which `worktree_setup.py --lead` writes into the
worktree's git folder; the session-start hook prints it. With one you are that lead's task.
In a main folder you are a lead. In a worktree without one, record the lead your brief
names, or ask the user once whether you are a task (and of whom) or a peer.

**The user's words set the relationship.** "Spin up a task": you are its lead; it gets the
lead file. "Spin up a thread": it is a peer, with no lead file and your link for messages
only.

**Names.** The lead names the sessions; a task never renames itself:

- the lead `<tag> ◆ lead` (`core ◆ lead`, `core@<machine> ◆ lead`);
- a task `<lead tag> › <branch>`;
- `? ` in front while a task waits on the user.

**Starting a task.** From the main folder on an up-to-date `master`: a worktree on a new
`<kind>/<name>` branch from `origin/master`, `worktree_setup.py --lead <your link>` there,
and the session started with a brief from [the template](brief.md), each the
orchestrator's way.

**A task reports** to the lead through the orchestrator, one line each with the PR's URL,
**before its turn ends**: *PR opened*, *Live check waiting*, *Ready* (with the live check's
table or why there was none), *Blocked* (on what), *Needs a decision*, *Decided*,
*Finished*. Whatever the user told the task directly goes to the lead too.

**A decision lives in the task's thread:**

1. The task writes the lettered options and its recommendation there, ending with the
   lead's link, and sends the lead one line with its own link.
2. The lead puts `? ` before the task's name, marks it unread, and gives the user the line
   and the link.
3. The user answers in the task. That is the user's word for that task, approvals
   included.
4. The task sends the lead "Decided: … (approved: …)"; the lead drops the `? `.

**The lead merges** only on the user's word, watches `master`'s run (*Finishing as the
maintainer*, step 4), warns the tasks whose PRs now conflict, and tells the task "merged";
the task runs `finish`. Releases, libraries' included, are the lead's, from the main folder.

**The lead reports to the user by name** (task, PR URL, state), and runs
`python3 <core>/dev/scripts/tasks.py --since <sha of its last report>` first: every task
with its PR, plus the merges and tags since, which someone else may have made.

## In a library repository

The org's libraries (`going-haywire/haybale-*`) follow the same steps. Their process files
come from [going-haywire/.github](https://github.com/going-haywire/.github) (the reusable CI);
their own rules are *In a library* on the [contributing](contributing.md#in-a-library) page;
this page, the hooks and the Farmhand bridge come from
core beside it, through the library's committed files (`.claude/settings.json`, `.mcp.json`,
`[tool.haywire.agents]` in `pyproject.toml`, `t3.json`). What differs:

- **Layout.** The library is cloned beside core (`../haywire-repo`), which its development
  project and its committed hooks reach by relative paths. A task's worktree can be anywhere:
  its setup links core beside it (*Parallel sessions*).
- **Checks** are the library's own ([contributing: in a library](contributing.md#in-a-library)),
  each with `uv run --frozen`.
- **CI** is `ci.yml`, calling the org's `library-ci.yml`: the library's tests against core's
  `master`, Linux on a draft, macOS added once the PR is ready; `nightly.yml` runs the same
  every night. The merge guard wants every check passed, a macOS check among them.
- **A change that needs unreleased core** raises the library's dependency floor in the same
  commit; CI passes because it runs against core's `master`, and the library is released
  once core is.
- **Releases** go through a release PR (*Releasing*): after a merged change, run
  `uv run --frozen haywire share --status`; if it is `READY`, list what is unreleased and ask
  "publish now, or wait for more?"; if a dependency floor waits for core, say so instead.
  On "publish": `uv run --frozen haywire share --bump patch --pr`, which opens the release
  PR (`STATE: RELEASE_BRANCH_PUSHED` means it could not: run its `NEXT:` command), then
  merge the release PR once its checks are green. The lead runs it, from the main folder.
  The merge run tags and publishes. Never tag by hand.
- **`finish` and the task view** run from core's `dev/scripts/`, as above; they read the
  default branch from the clone (`main` in haybale-stream).
