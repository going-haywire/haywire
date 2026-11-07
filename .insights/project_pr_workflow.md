# Branches, pull requests and CI: the non-obvious parts

The rules are in CLAUDE.md, *Git and pull requests*; the procedures in the
`haywire-workflow` skill. CI's own settings are commented in `.github/workflows/ci.yml`.

## CI

- **Only the Linux jobs can be required checks.** The macOS jobs run once a PR is ready
  for review, so a draft would never satisfy them.
- **A cancelled job is not a failure:** a newer push to the same branch cancels the
  older run.
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
