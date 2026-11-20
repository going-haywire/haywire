#!/bin/bash
# At session start, tells the agent about the orchestrator it runs in, if any. Each slot
# orchestrators/<tool>/session.sh prints a paragraph when its tool runs the session and
# nothing otherwise (ADR 0090); this hook joins what they print. A line a slot starts with
# `user: ` is for the developer: it goes to the hook's systemMessage, which Claude Code shows
# the user. Says nothing when none speaks.

slots="${BASH_SOURCE[0]%/*}/../orchestrators"
context=""
user=""
for script in "$slots"/*/session.sh; do
  [ -x "$script" ] || continue
  while IFS= read -r line; do
    case "$line" in
      "user: "*) user+="${user:+$'\n'}${line#user: }" ;;
      ?*) context+="${context:+ }$line" ;;
    esac
  done < <("$script" 2>/dev/null)
done
[ -n "$context$user" ] || exit 0

jq -n --arg c "$context" --arg u "$user" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $c}}
  + (if $u == "" then {} else {systemMessage: $u} end)' 2>/dev/null \
  || echo "$context"
exit 0
