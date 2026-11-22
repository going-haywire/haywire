#!/bin/bash
# T3 Code's slot (ADR 0090), run by hooks/session-place.sh at session start: prints that the
# agent runs in a T3 thread and where the T3 how-to is, then what the T3 setup still lacks,
# if anything, for the agent and (as `user: ` lines) for the developer. Prints nothing outside T3.

[ "$CLAUDE_CODE_ENTRYPOINT" = "t3-code" ] || [ -n "$T3CODE_THREAD_ID" ] || exit 0

echo "You run in T3 Code${T3CODE_THREAD_ID:+ as thread \`$T3CODE_THREAD_ID\`}. Message another thread with \`t3_thread_send\` (it arrives as its next input); refer to a thread by its title, the branch for a task. Lead and tasks in T3: core's \`docs/collaboration/orchestrators/t3-agent.md\` (the bridge serves it as \`farmhand://dev/collaboration/orchestrators/t3-agent.md\`)."

dir=$(cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null && pwd -P) || exit 0
unfinished=""

# In a worktree, the imported setup script has built the environment. T3's import drops
# t3.json's `async: false`, so T3 may start the agent alongside that script; wait here until it
# is done: its last step writes haywire-setup-done into the worktree's git folder.
# HAYWIRE_T3_SETUP_WAIT is seconds.
dirs=$(git -C "$dir" rev-parse --path-format=absolute --git-dir --git-common-dir 2>/dev/null)
set_up() {
  [ -d "$dir/.venv" ] && [ -f "$(sed -n 1p <<<"$dirs")/haywire-setup-done" ]
}
if [ -n "$dirs" ] && [ "$(sed -n 1p <<<"$dirs")" != "$(sed -n 2p <<<"$dirs")" ]; then
  waited=0
  until set_up || [ "$waited" -ge "${HAYWIRE_T3_SETUP_WAIT:-300}" ]; do
    sleep 1
    waited=$((waited + 1))
  done
  set_up || unfinished="${HAYWIRE_T3_SETUP_WAIT:-300}"
fi

# What the T3 setup lacks, from T3's own settings file: doctor.py says it, and fixes it on --fix.
if command -v python3 >/dev/null 2>&1; then
  python3 "${BASH_SOURCE[0]%/*}/doctor.py" --hook --repo "$dir" ${unfinished:+--setup-unfinished "$unfinished"}
fi
exit 0
