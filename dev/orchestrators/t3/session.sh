#!/bin/bash
# T3 Code's slot (ADR 0090), run by hooks/session-place.sh at session start: prints that the
# agent runs in a T3 thread and where the T3 how-to is, its role (lead, or the task of the lead
# recorded in the worktree's git folder), then what the T3 setup still lacks, if anything, for
# the agent and (as `user: ` lines) for the developer. Prints nothing outside T3.

[ "$CLAUDE_CODE_ENTRYPOINT" = "t3-code" ] || [ -n "$T3CODE_THREAD_ID" ] || exit 0

echo "You run in T3 Code${T3CODE_THREAD_ID:+ as thread \`$T3CODE_THREAD_ID\`}. Message another thread with \`t3_thread_send\` (it arrives as its next input); refer to a thread by its title, the branch for a task. Lead and tasks in T3: core's \`docs/collaboration/orchestrators/t3-agent.md\` (the bridge serves it as \`farmhand://dev/collaboration/orchestrators/t3-agent.md\`)."

dir=$(cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null && pwd -P) || exit 0
unfinished=""

# In a worktree, the imported setup script has built the environment. T3 before 0.1.11 dropped
# t3.json's `async: false` on import, so T3 may start the agent alongside that script; wait here
# while it runs: it writes haywire-setup-started into the worktree's git folder first and
# haywire-setup-done last. A setup that has not started within HAYWIRE_T3_SETUP_START_WAIT
# never runs (T3 runs no script for a worktree it re-creates), so the wait ends there; a
# started one gets HAYWIRE_T3_SETUP_WAIT. Both are seconds.
dirs=$(git -C "$dir" rev-parse --path-format=absolute --git-dir --git-common-dir 2>/dev/null)
git_dir=$(sed -n 1p <<<"$dirs")
set_up() {
  [ -d "$dir/.venv" ] && [ -f "$git_dir/haywire-setup-done" ]
}
started() {
  [ -f "$git_dir/haywire-setup-started" ] || [ -f "$git_dir/haywire-setup-done" ]
}
if [ -n "$dirs" ] && [ "$git_dir" != "$(sed -n 2p <<<"$dirs")" ]; then
  waited=0
  until set_up || [ "$waited" -ge "${HAYWIRE_T3_SETUP_WAIT:-300}" ] \
    || { ! started && [ "$waited" -ge "${HAYWIRE_T3_SETUP_START_WAIT:-10}" ]; }; do
    sleep 1
    waited=$((waited + 1))
  done
  if ! set_up; then
    started && unfinished="$waited" || unfinished=0
  fi
fi

# The role comes from the lead file worktree_setup.py --lead writes (workflow, Lead and tasks).
core=$(cd "${BASH_SOURCE[0]%/*}/../../.." && pwd -P)
if [ -z "$dirs" ]; then
  : # not a git folder: no role to tell
elif [ "$git_dir" = "$(sed -n 2p <<<"$dirs")" ]; then
  echo "This is a main folder: you are a lead (a peer, if the user started you as one). Brief a task with the template \`$core/docs/collaboration/brief.md\` (\`farmhand://dev/collaboration/brief.md\`)."
elif lead=$(sed -n 1p "$git_dir/haywire-lead" 2>/dev/null) && [ -n "$lead" ]; then
  echo "You are a task of $lead; report to it with \`t3_thread_send\` before each turn ends, and pass on what the user tells you directly."
else
  echo "No lead is recorded for this worktree. If your brief names your lead, record it: \`python3 $core/dev/scripts/worktree_setup.py --lead <link>\`. Otherwise ask the user once whether you are a task (and of whom) or a peer."
fi

# What T3's own settings lack (worktree cleanup, branch naming): doctor.py says it.
if command -v python3 >/dev/null 2>&1; then
  python3 "${BASH_SOURCE[0]%/*}/doctor.py" --hook --repo "$dir" ${unfinished:+--setup-unfinished "$unfinished"}
fi
exit 0
