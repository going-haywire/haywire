#!/bin/bash
# At session start, tells the agent its role: maintainer when this GitHub login can write
# to the upstream repository, contributor otherwise or when that cannot be checked. Also
# warns once when a tool the other hooks need is missing.
#
# The upstream repository is the clone's `upstream` remote (a contributor's fork has one),
# otherwise its `origin`; going-haywire/haywire when neither names a GitHub repository.

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true
url=$(git remote get-url upstream 2>/dev/null || git remote get-url origin 2>/dev/null)
UPSTREAM=$(echo "$url" | sed -nE 's#^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+/[^/]+)$#\2#p')
UPSTREAM=${UPSTREAM%.git}
UPSTREAM=${UPSTREAM:-going-haywire/haywire}

warnings=""
permission=""
command -v jq >/dev/null 2>&1 || warnings+=" jq is not installed, so the workflow hooks (skill gate, merge guard) check nothing."
if command -v gh >/dev/null 2>&1; then
  # perl's alarm bounds the network call: macOS has no `timeout`.
  permission=$(perl -e 'alarm 8; exec @ARGV' gh repo view "$UPSTREAM" --json viewerPermission \
    --jq .viewerPermission 2>/dev/null)
else
  warnings+=" The GitHub CLI (gh) is not installed: the role cannot be checked and pull requests cannot be handled."
fi

case "$permission" in
  ADMIN | MAINTAIN | WRITE)
    role="Role: maintainer (write access to $UPSTREAM). Follow the maintainer steps of the haywire-workflow skill."
    ;;
  *)
    reason=${permission:+"$permission access"}
    reason=${reason:-"access could not be checked"}
    role="Role: contributor ($reason to $UPSTREAM). Work on your fork: commit and push there freely. Open, ready, comment on or review anything on $UPSTREAM only when the user says so, and never merge or release. Follow the contributor steps of the haywire-workflow skill."
    ;;
esac

context="$role${warnings:+ Warning:$warnings}"
jq -n --arg c "$context" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $c}}' 2>/dev/null \
  || echo "$context"
exit 0
