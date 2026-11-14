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

## Identity and the hook

- Claude pushes with the user's git credentials, so GitHub cannot tell the two apart: the
  ruleset's admin bypass applies to both. The local hook
  (`.claude/hooks/block-dangerous-git.sh`) is what keeps destructive commands with the
  user.
- **More hooks enforce the workflow.** `session-role.sh` (`SessionStart`) tells the agent
  its role from the login's permission on `going-haywire/haywire`: write access makes a
  maintainer, anything else, including a failed check (no `gh`, no network, 8 s limit), a
  contributor; it also warns when `jq` or `gh` is missing, since the other hooks then check
  nothing. `require-workflow-skill.sh` refuses `git commit`, `git push` and the `gh pr`
  commands that change a PR until the session has loaded the `haywire-workflow` skill;
  `mark-workflow-skill.sh` records the load per session id under
  `$TMPDIR/claude-haywire-workflow/`. `guard-pr-merge.sh` refuses `gh pr merge` while the
  PR is a draft, carries `needs introduction` or `agent files`, has an unresolved review
  thread, or the newest run of any check has not passed, and until a macOS check has
  passed. The user merges by hand when they want to override it. `tests/scripts/test_claude_hooks.py`
  runs them all against a stand-in `gh`.
- **Only line-comment threads can block a merge.** A conversation comment has no resolved
  state, and Claude comments with the user's account, so no hook can tell whether one was
  answered; the skill has Claude read them all before merging. Feedback that must block a
  merge goes in a line comment.
- **The hook reads the whole command line, text included:** a `git branch -d` next to a
  push, or a heredoc whose text names a blocked command, is refused. Put such text in a
  file and run the file.
