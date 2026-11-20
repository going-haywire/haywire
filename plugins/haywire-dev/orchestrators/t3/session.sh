#!/bin/bash
# T3 Code's slot (ADR 0090), run by hooks/session-place.sh at session start: prints that the
# agent runs in a T3 thread and where the T3 how-to is, then what the T3 setup still lacks,
# if anything, for the agent and (as `user: ` lines) for the developer. Prints nothing outside T3.

[ "$CLAUDE_CODE_ENTRYPOINT" = "t3-code" ] || [ -n "$T3CODE_THREAD_ID" ] || exit 0

echo "You run in T3 Code${T3CODE_THREAD_ID:+ as thread \`$T3CODE_THREAD_ID\`}. Message another thread with \`t3_thread_send\` (it arrives as its next input); refer to a thread by its title, the branch for a task. Lead and tasks in T3: \`orchestrators/t3.md\` in the haywire-workflow skill."

command -v jq >/dev/null 2>&1 || exit 0
dir=$(cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null && pwd -P) || exit 0
missing=()

# In a worktree, the imported setup script has built the environment and given the studio a port.
dirs=$(git -C "$dir" rev-parse --path-format=absolute --git-dir --git-common-dir 2>/dev/null)
if [ -n "$dirs" ] && [ "$(sed -n 1p <<<"$dirs")" != "$(sed -n 2p <<<"$dirs")" ]; then
  if [ ! -d "$dir/.venv" ] || ! jq -e '.network.port.value | type == "number"' "$dir/.haywire/settings.json" >/dev/null 2>&1; then
    missing+=("the t3.json scripts are not imported, so the worktree setup did not run: import all three, *Haywire studio* optional (one click starts this worktree's studio), either yourself in *Project settings → Actions → Import scripts → Import from t3.json*, or the agent offers to do it with \`t3_project_update\` (read the project first, append only the missing scripts) and does so only on your yes; then run \`python3 scripts/worktree_setup.py\` in this worktree now")
  fi
fi

# T3's own settings file is internal and undocumented: when it is missing or unreadable, say nothing.
settings="${T3CODE_HOME:-$HOME/.t3}/userdata/settings.json"
values=$(jq -r '[(.storageCleanup.worktreeOnMerge // false), (.storageCleanup.worktreeKeepWhen // "uncommitted-changes"), (.branchNamingMode // "static")] | map(tostring) | join(" ")' "$settings" 2>/dev/null)
if [ -n "$values" ]; then
  read -r on_merge keep_when naming <<<"$values"
  [ "$on_merge" = "true" ] || missing+=("merged worktrees are not deleted: *Settings → Worktrees → Cleanup → Delete merged worktrees*")
  [ "$keep_when" = "uncommitted-changes" ] || missing+=("worktrees with local changes are not kept by uncommitted changes: *Settings → Worktrees → Cleanup → Keep worktrees with local changes → Uncommitted changes*")
  [ "$naming" = "semantic" ] || missing+=("branches are not named by kind: *Settings → Worktrees → Branch naming → semantic*")
fi

if [ ${#missing[@]} -gt 0 ]; then
  list=""
  for item in "${missing[@]}"; do list+="${list:+; }$item"; done
  echo "T3 setup is incomplete; pass this list to the user in your first reply, before other work: $list."
  echo "user: T3 setup is incomplete:"
  for item in "${missing[@]}"; do echo "user: - $item"; done
fi
exit 0
