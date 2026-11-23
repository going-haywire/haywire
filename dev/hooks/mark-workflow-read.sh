#!/bin/bash
# Records that this session read the development workflow, core's
# docs/collaboration/workflow.md: as a file (Read; from a library, through ../haywire-repo)
# or as the Farmhand bridge's resource farmhand://dev/collaboration/workflow.md.
# require-workflow-read.sh reads the record.

INPUT=$(cat)
SESSION=$(echo "$INPUT" | jq -r '.session_id // empty')
[ -z "$SESSION" ] && exit 0

FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
URI=$(echo "$INPUT" | jq -r '.tool_input.uri // empty')

case "$FILE" in */docs/collaboration/workflow.md) READ=true ;; *) READ=false ;; esac
[ "$URI" = "farmhand://dev/collaboration/workflow.md" ] && READ=true
if $READ; then
  DIR="${TMPDIR:-/tmp}/claude-haywire-workflow"
  mkdir -p "$DIR" && touch "$DIR/$SESSION"
fi
exit 0
