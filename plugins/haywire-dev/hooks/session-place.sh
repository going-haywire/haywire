#!/bin/bash
# At session start, tells the agent about the orchestrator it runs in, if any. Each slot
# orchestrators/<tool>/session.sh prints a paragraph when its tool runs the session and
# nothing otherwise (ADR 0090); this hook joins what they print. Says nothing when none speaks.

slots="${BASH_SOURCE[0]%/*}/../orchestrators"
context=""
for script in "$slots"/*/session.sh; do
  [ -x "$script" ] || continue
  said=$("$script" 2>/dev/null)
  [ -n "$said" ] && context+="${context:+ }$said"
done
[ -n "$context" ] || exit 0

jq -n --arg c "$context" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $c}}' 2>/dev/null \
  || echo "$context"
exit 0
