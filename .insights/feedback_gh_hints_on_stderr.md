---
name: gh writes agent hints to stderr; never parse 2>&1
description: gh 2.105+ prints a `hint:` block on stderr when it detects an agent (AI_AGENT, CLAUDECODE), so output captured with 2>&1 is no longer JSON; parse stdout only and keep stderr apart for the error message. Hooks run from the main folder's checkout, so a stale main folder runs stale hooks
type: feedback
---

**gh 2.105 and later print a `hint: … gh event listen …` block on stderr** whenever they
detect an agent (`AI_AGENT` or `CLAUDECODE` set, as in every Claude Code session). The
hint is absent in a plain terminal, so a script that captures `gh … --json … 2>&1` works
by hand and fails only under an agent: jq meets the hint first (`Invalid numeric literal
at line 1, column 5`) and whatever the script decides on a parse failure happens
silently. The merge guard read that as "the PR is still a draft" and refused every merge.

**A stale main folder runs stale hooks.** The hooks run from `"$CLAUDE_PROJECT_DIR"/dev/hooks/`,
the main folder's checkout, never a worktree's. A fix to a hook therefore applies only once the
main folder has pulled it: the guard kept failing after the fix had merged, because the main
folder was still behind `origin/master`. Run `git pull --ff-only` in the main folder before a
merge, and after a hook fix lands.

**Why:** the hint is not an error, and gh may add more of them; only stdout is the
command's answer.

**How to apply:** parse gh's stdout alone. Send stderr to a file or a separate variable
and quote it only when gh fails, without the `hint:` lines
(`dev/hooks/guard-pr-merge.sh`, `gh_failed`). In Python keep `capture_output=True`,
never `stderr=subprocess.STDOUT`, for a gh call whose output is parsed. When the parse
itself fails, say so; never let a parse failure fall through to a verdict. A test's fake
gh writes a hint on stderr (`_GH_FOR_GUARD` in `tests/scripts/test_claude_hooks.py`).
