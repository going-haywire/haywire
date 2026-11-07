# Branches, pull requests and CI: the non-obvious parts

The rules are in CLAUDE.md, *Git and pull requests*. This file holds what they rest on.

## CI (`.github/workflows/ci.yml`)

- **Required checks** (ruleset on the default branch): `lint`, `types`,
  `tests (ubuntu-24.04)`, `browser (ubuntu-24.04)`. The macOS jobs run only once a PR is
  ready for review, so they cannot be required: a draft would never satisfy them.
- **A cancelled job is not a failure:** a newer push to the same branch cancels the
  older run.
- **Runners are pinned to `ubuntu-24.04`:** `ubuntu-latest` can move to a release
  Playwright does not support yet.
- **The inotify limit is raised on Linux:** the suite leaks file watchers and exceeds the
  default of 128 instances. The leak is unfixed.
- **`--maxfail=0`** overrides `pyproject.toml`'s 5, so one run shows every failure.
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
- **The hook reads the whole command line, text included:** a `git branch -d` next to a
  push, or a heredoc whose text names a blocked command, is refused. Put such text in a
  file and run the file.
