# Branches, pull requests and CI: the non-obvious parts

The rules are in `CONTRIBUTING.md` (the agent-only ones in CLAUDE.md, *Git and pull
requests*); the procedures in the
`haywire-workflow` skill. CI's own settings are commented in `.github/workflows/ci.yml`.

## CI

- **Only the Linux jobs can be required checks.** The macOS jobs run once a PR is ready
  for review, so a draft would never satisfy them.
- **Two workflows run from `master`, never from the pull request.** `test-results.yml`
  (`workflow_run`, after CI) publishes the test report, and `pr-intake.yml`
  (`pull_request_target`) sets `needs introduction` and `agent files`. Both hold write
  rights and only read data from the pull request, so a change to either takes effect
  after its merge, never in the pull request that makes it.
- **Actions are pinned to commits**, with the version as a comment; Dependabot proposes a
  grouped update weekly. A new Action goes in pinned the same way.
- **A cancelled job is not a failure:** a newer push to the same branch cancels the
  older run.
- **Marking a PR ready right after opening it can lose the macOS run.** Opening and
  readying start two CI runs in the same second; the concurrency rule cancels one of
  them, and when it cancels the ready run, the macOS jobs show as cancelled (and the PR
  as failing). Mark a draft ready only after its first run has started, or re-run the
  cancelled run (`gh run rerun <id>`).
- **Linux and macOS differ in registration order** (the filesystem's order), so code that
  depends on the order libraries or modules register in can behave differently per
  platform. CI's Linux run is where that shows.
- **Thresholds that count work can still depend on the machine:** a slower runner adds
  redraw passes. Bound such counts by the regression they guard against, not by what a
  fast machine measures.

## Merging and tagging

- **A squash merge makes a new commit** on `master`. A tag goes on that commit, never on
  the branch's.
- **Anything pushed, tagged or opened with `GITHUB_TOKEN` starts no further workflow
  run** (only `workflow_dispatch` and `repository_dispatch` are exempt). A run that
  tags must also publish; a tag made by a run never starts `publish.yml`.

## Identity and the hook

- Claude pushes with the user's git credentials, so GitHub cannot tell the two apart: an
  admin bypass applies to both. Two rulesets split the protection by what a bypass may
  do. *Permanent refs* (`master`, `gh-pages`, the `v*` tags) forbids deleting and
  force-pushing with no bypass at all, so nothing running as the user can break it. *PR
  gate* (required checks, the PR rule) lets an admin bypass only through a pull request.
  The local hook (`.claude/hooks/block-dangerous-git.sh`) keeps the rest with the user:
  force pushes, remote deletions, tag pushes, and `gh api` writes to rulesets or branch
  protection (reads pass).
- **`scripts/finish.py` is the only way agents delete a branch.** The hook blocks raw
  `git branch -D` and `git push --delete`; `finish <branch>` deletes the local and remote
  branch and the worktree only after finding the branch's PR merged (closed needs
  `--abandon`, the user's word) and the local branch holding nothing the PR's head
  lacks. The task finishes itself after the lead (or the user) merges. `finish --sweep`
  lists leftovers and acts only with `--yes`.
- **More hooks enforce the workflow.** `session-role.sh` (`SessionStart`) tells the agent
  its role from the login's permission on `going-haywire/haywire`: write access makes a
  maintainer, anything else, including a failed check (no `gh`, no network, 8 s limit), a
  contributor; it also warns when `jq` or `gh` is missing, since the other hooks then check
  nothing. `require-workflow-skill.sh` refuses `git commit`, `git push` and the `gh pr`
  commands that change a PR until the session has loaded the `haywire-workflow` skill;
  `mark-workflow-skill.sh` records the load per session id under
  `$TMPDIR/claude-haywire-workflow/`. `guard-pr-merge.sh` refuses `gh pr merge` while the
  PR is a draft, carries `needs introduction` or `agent files`, has an unresolved review
  thread, or the newest run of any check has not passed, and, in going-haywire/haywire,
  until a macOS check has passed. It reads the PR in the repository `--repo` / `-R`
  names; a library repository without CI may report no checks. The hook parses the
  literal command line, so a loop over `$n` gives it nothing to read: one merge per
  command, with the number written out. The user merges by hand when they want to override it. `tests/scripts/test_claude_hooks.py`
  runs them all against a stand-in `gh`.
- **`agent files` comes back on every push and on *ready*.** `pr-intake.yml` runs on
  `synchronize` and `ready_for_review` and labels by the PR's whole file list, so a push
  (even one that changes no agent file) or marking the PR ready puts the label back after
  the maintainer removed it, and the guard refuses the merge again. Mark the PR ready and
  push everything before asking the maintainer to remove it; the agent never removes it.
- **Only line-comment threads can block a merge.** A conversation comment has no resolved
  state, and Claude comments with the user's account, so no hook can tell whether one was
  answered; the skill has Claude read them all before merging. Feedback that must block a
  merge goes in a line comment.
- **The hook reads the whole command line, text included:** a `git branch -d` next to a
  push, or a heredoc whose text names a blocked command, is refused. Put such text in a
  file and run the file.
