#!/bin/bash
# Refuses git commit, git push and the gh pr commands that change a PR until this
# session has loaded the haywire-workflow skill (recorded by mark-workflow-skill.sh).

INPUT=$(cat)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

START='(^|[;&|(]|\$\()[[:space:]]*'
if echo "$COMMAND" | grep -qE "${START}(git[[:space:]]+(commit|push)|gh[[:space:]]+pr[[:space:]]+(create|ready|merge|edit|close|reopen|review|comment))([[:space:]]|$)"; then
  if [ -n "$SESSION" ] && [ -f "${TMPDIR:-/tmp}/claude-haywire-workflow/$SESSION" ]; then
    exit 0
  fi
  echo "BLOCKED: load the haywire-workflow skill (Skill tool, skill \"haywire-workflow\") before committing, pushing or changing a PR in this session, follow it, then run the command again." >&2
  exit 2
fi
exit 0
