#!/bin/bash
# Blocks destructive git commands. Plain pushes of branches (master included) are
# allowed; anything that rewrites or deletes remote history, or pushes a tag (which
# publishes a release), stays with the user. See CLAUDE.md, "Git and pull requests".

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')

block() {
  echo "BLOCKED: '$COMMAND' $1. The user has prevented you from doing this." >&2
  exit 2
}

DANGEROUS_PATTERNS=(
  "git reset --hard"
  "git clean -fd"
  "git clean -f"
  "git branch -D"
  "git checkout \."
  "git restore \."
  "reset --hard"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    block "matches dangerous pattern '$pattern'"
  fi
done

if echo "$COMMAND" | grep -qE "git push"; then
  # Force: --force, --force-with-lease, -f, or a +refspec.
  if echo "$COMMAND" | grep -qE "(^|[[:space:]])(-f|--force[^[:space:]]*)([[:space:]]|$)|[[:space:]]\+[^[:space:]]"; then
    block "is a force push"
  fi
  # Deleting or pruning remote refs: --delete, -d, --prune, --mirror, or a :refspec.
  if echo "$COMMAND" | grep -qE "(^|[[:space:]])(-d|--delete|--prune|--mirror)([[:space:]]|$)|[[:space:]]:[^[:space:]]"; then
    block "deletes remote refs"
  fi
  # Tags publish releases: --tags, --follow-tags, refs/tags/, or a version tag name.
  if echo "$COMMAND" | grep -qE "(^|[[:space:]])(--tags|--follow-tags)([[:space:]]|$)|refs/tags/|[[:space:]]v[0-9]+\.[0-9]+"; then
    block "pushes a tag"
  fi
fi

if echo "$COMMAND" | grep -qE "rm -r(f)?"; then
  if ! echo "$COMMAND" | grep -qE "(\.claude|\.scratchpad|/tmp|/private/tmp)"; then
    echo "BLOCKED: 'rm -r' outside safe directories. Only allowed in .claude, scratchpad, or /tmp folders." >&2
    exit 2
  fi
fi

exit 0
