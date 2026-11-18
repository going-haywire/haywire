#!/bin/bash
# Records that this session loaded the haywire-workflow skill, through the Skill tool or
# the /haywire-workflow command, under its project name or its plugin name
# (haywire-dev:haywire-workflow). require-workflow-skill.sh reads the record.

INPUT=$(cat)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')
[ -z "$SESSION" ] && exit 0

SKILL=$(echo "$INPUT" | jq -r '.tool_input.skill // empty')
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')

case "$SKILL" in haywire-workflow | haywire-dev:haywire-workflow) LOADED=true ;; *) LOADED=false ;; esac
if $LOADED || echo "$PROMPT" | grep -qE '^[[:space:]]*/(haywire-dev:)?haywire-workflow([[:space:]]|$)'; then
  DIR="${TMPDIR:-/tmp}/claude-haywire-workflow"
  mkdir -p "$DIR" && touch "$DIR/$SESSION"
fi
exit 0
