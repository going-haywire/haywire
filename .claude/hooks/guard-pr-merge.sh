#!/bin/bash
# Refuses `gh pr merge` unless the PR is out of draft, has no unresolved review thread,
# and the newest run of every check passed, with at least one macOS check among them
# (macOS runs only once a PR is ready).

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

echo "$COMMAND" | grep -qE '(^|[;&|(]|\$\()[[:space:]]*gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)' || exit 0

block() {
  echo "BLOCKED: gh pr merge: $1. Mark the PR ready, wait for every check (macOS included) to pass, ask the user, and merge only on their word \"merge\"." >&2
  exit 2
}

# The PR argument (number, URL or branch); empty means the current branch's PR.
PR=$(echo "$COMMAND" | sed -nE 's/.*gh[[:space:]]+pr[[:space:]]+merge[[:space:]]+([^-[:space:]][^[:space:];&|]*).*/\1/p')

cd "${CLAUDE_PROJECT_DIR:-.}" || block "cannot enter the project folder"
# shellcheck disable=SC2086
VIEW=$(gh pr view $PR --json isDraft,statusCheckRollup,url 2>&1) || block "cannot read the PR ($VIEW)"

[ "$(echo "$VIEW" | jq -r '.isDraft')" = "false" ] || block "the PR is still a draft"

# The PR url is https://github.com/<owner>/<repo>/pull/<number>.
IFS=/ read -r _ _ _ OWNER REPO _ NUMBER <<< "$(echo "$VIEW" | jq -r '.url')"
OPEN_THREADS=$(gh api graphql -F owner="$OWNER" -F repo="$REPO" -F number="$NUMBER" -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) { reviewThreads(first: 100) { nodes { isResolved } } }
    }
  }' --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not)] | length' 2>&1) \
  || block "cannot read the PR's review threads ($OPEN_THREADS)"
[ "$OPEN_THREADS" = "0" ] || block "$OPEN_THREADS review thread(s) unresolved; read them, address them, resolve them"

# One entry per check and run: keep the newest run of each check.
VERDICT=$(echo "$VIEW" | jq -r '
  [.statusCheckRollup[]
   | if .__typename == "StatusContext"
     then {key: .context, at: (.startedAt // ""), ok: (.state == "SUCCESS"), done: (.state != "PENDING")}
     else {key: ((.workflowName // "") + "/" + .name), at: (.startedAt // ""),
           ok: ((.conclusion // "") | IN("SUCCESS", "SKIPPED", "NEUTRAL")),
           done: (.status == "COMPLETED"), macos: ((.name | test("macos"; "i")) and .conclusion == "SUCCESS")}
     end]
  | group_by(.key) | map(max_by(.at)) as $latest
  | if ($latest | length) == 0 then "no checks reported"
    elif ($latest | map(select(.done | not)) | length) > 0
      then "checks still running: " + ($latest | map(select(.done | not) | .key) | join(", "))
    elif ($latest | map(select(.ok | not)) | length) > 0
      then "checks not passed: " + ($latest | map(select(.ok | not) | .key) | join(", "))
    elif ($latest | map(select(.macos == true)) | length) == 0
      then "no passed macOS check yet"
    else "ok" end')

[ "$VERDICT" = "ok" ] || block "$VERDICT"
exit 0
