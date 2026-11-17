#!/bin/bash
# At session start, tells the agent where it runs when that is herdr: its address, how to
# reach other agents, how to name its tab. In the main folder it also lists the other live
# sessions in that folder. Says nothing outside herdr or without hc.

[ -n "$HC_TERMINAL_ID" ] || exit 0
command -v hc >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

# perl's alarm bounds each call: macOS has no `timeout`.
bounded() { perl -e 'alarm 8; exec @ARGV' "$@" 2>/dev/null; }

dir=$(cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null && pwd -P) || exit 0
self=$(bounded hc get "$HC_TERMINAL_ID")
where=$(jq -r '.labels.where // empty' <<<"$self" 2>/dev/null)
tab=$(jq -r '.labels["herdr.tab"] // empty' <<<"$self" 2>/dev/null)

main_folder=false
[ -d "$dir/.git" ] && main_folder=true

if $main_folder; then
  branch_hint="You run in the main folder: name your tab after your role (lead, research, ...)."
else
  branch=$(git -C "$dir" branch --show-current 2>/dev/null)
  branch_hint="Name your tab after your branch${branch:+ (\`$branch\`)}."
fi

rename=""
[ -n "$tab" ] && rename=" Rename it with: \`herdr-app do tab.rename --id $tab --name <name>\`."

context="You run in herdr as ${where:+\`$where\` (}\`$HC_TERMINAL_ID\`${where:+)}. Other agents: \`hc ls\`. Message one: \`hc send <address> \"...\"\` (it arrives as their next input). Protocol: \`hc --skill\`. Refer to an agent by its space / tab, the address only in brackets. $branch_hint$rename"

if $main_folder; then
  others=$(bounded hc ls --json | jq -r --arg dir "$dir" --arg self "$HC_TERMINAL_ID" '
    [.terminals[]?
     | select(.state == "live" and .address != $self and .cwd == $dir
              and (.agent | IN("zsh", "bash", "fish", "sh") | not))
     | "\(.where // .address) (\(.address))"] | join(", ")' 2>/dev/null)
  if [ -n "$others" ]; then
    context+=" Warning: other live sessions share this main folder: $others. A session that writes moves to a worktree; nobody switches branches under the lead."
  fi
fi

jq -n --arg c "$context" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $c}}' 2>/dev/null \
  || echo "$context"
exit 0
