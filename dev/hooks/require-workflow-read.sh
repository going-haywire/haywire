#!/bin/bash
# Refuses git commit, git push and the gh pr commands that change a PR until this
# session has read the development workflow (recorded by mark-workflow-read.sh).

INPUT=$(cat)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

START='(^|[;&|(]|\$\()[[:space:]]*'
if echo "$COMMAND" | grep -qE "${START}(git[[:space:]]+(commit|push)|gh[[:space:]]+pr[[:space:]]+(create|ready|merge|edit|close|reopen|review|comment))([[:space:]]|$)"; then
  if [ -n "$SESSION" ] && [ -f "${TMPDIR:-/tmp}/claude-haywire-workflow/$SESSION" ]; then
    exit 0
  fi
  echo "BLOCKED: read the development workflow before committing, pushing or changing a PR in this session: the Farmhand bridge's resource farmhand://dev/collaboration/workflow.md, or the file docs/collaboration/workflow.md in core (from a library: ../haywire-repo/docs/collaboration/workflow.md). Follow it, then run the command again." >&2
  exit 2
fi
exit 0
