#!/bin/bash
# At session start, tells the agent where it runs when that is herdr: its address, how to
# reach other agents. A worktree session whose tab is still called by its number gets the tab
# renamed to its branch; in the main folder the agent is told to name it by role, and the
# other live sessions in that folder are listed.
# Says nothing outside herdr or without hc.

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

# A tab still called by its number is unnamed; a name the user chose is left alone.
tab_name=""
case "$where" in *" / "*) tab_name=${where#* / } ;; esac
unnamed=false
case "$tab_name" in "" | *[!0-9]*) ;; *) unnamed=true ;; esac
rename_cmd="herdr-app do tab.rename --id $tab --name"

tab_hint=""
if $main_folder; then
  $unnamed && [ -n "$tab" ] && tab_hint="You run in the main folder. Before anything else, name your tab after your role (lead, research, ...): \`$rename_cmd <role>\`."
else
  branch=$(git -C "$dir" branch --show-current 2>/dev/null)
  if $unnamed && [ -n "$branch" ] && [ -n "$tab" ]; then
    if command -v herdr-app >/dev/null 2>&1 && bounded herdr-app do tab.rename --id "$tab" --name "$branch" >/dev/null; then
      tab_hint="Your tab is now named \`$branch\`."
    else
      tab_hint="Before anything else, name your tab after your branch: \`$rename_cmd $branch\`."
    fi
  fi
fi

context="You run in herdr as ${where:+\`$where\` (}\`$HC_TERMINAL_ID\`${where:+)}. Other agents: \`hc ls\`. Message one: \`hc send <address> \"...\"\` (it arrives as their next input). Protocol: \`hc --skill\`. Refer to an agent by its space / tab, the address only in brackets.${tab_hint:+ $tab_hint}"

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
