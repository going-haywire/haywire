#!/bin/bash
# Refuses `gh pr merge` unless the PR is out of draft, carries neither `needs introduction`
# nor `agent files`, has no unresolved review thread, and the newest run of every check
# passed. In going-haywire/haywire and the org's libraries (going-haywire/haybale-*) there
# must be checks, with at least one passed macOS check among them (macOS runs only once a
# PR is ready); any other repository may report none. `--repo` / `-R` is honoured; without
# it the PR is read in the folder the command runs in.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

echo "$COMMAND" | grep -qE '(^|[;&|(]|\$\()[[:space:]]*gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)' || exit 0

block() {
  echo "BLOCKED: gh pr merge: $1. Mark the PR ready, wait for every check (macOS included) to pass, ask the user, and merge only on their word \"merge\"." >&2
  exit 2
}

# The words after `gh pr merge`, up to the end of that command: the PR argument (number,
# URL or branch; none means the current branch's PR) and `--repo`. The values of the other
# flags that take one are skipped, so they are never read as the PR.
ARGS=$(echo "$COMMAND" | sed -nE 's/.*gh[[:space:]]+pr[[:space:]]+merge([[:space:]]+([^;&|)]*))?.*/\2/p')
read -ra WORDS <<< "$ARGS"
PR=""
REPO_ARG=()
i=0
while [ "$i" -lt "${#WORDS[@]}" ]; do
  word=${WORDS[$i]}
  case "$word" in
    -R | --repo) REPO_ARG=(--repo "${WORDS[$((i + 1))]}"); i=$((i + 1)) ;;
    --repo=*) REPO_ARG=(--repo "${word#--repo=}") ;;
    -b | --body | -F | --body-file | -t | --subject | -A | --author-email | --match-head-commit) i=$((i + 1)) ;;
    -*) ;;
    *) [ -n "$PR" ] || PR=$word ;;
  esac
  i=$((i + 1))
done

# Without --repo, gh reads a number or a branch in the repository of the folder the command
# runs in: the session's current folder, or the last `cd <dir>` before the merge in the
# same command. Reading it in the project folder would check another repository's PR.
DIR=$(echo "$INPUT" | jq -r '.cwd // empty')
cd "${DIR:-${CLAUDE_PROJECT_DIR:-.}}" || block "cannot enter the session's folder"
CD=$(printf '%s' "$COMMAND" | perl -0pe 's/gh\s+pr\s+merge.*//s' \
  | grep -oE '(^|[;&|(])[[:space:]]*cd[[:space:]]+[^;&|)[:space:]]+' | sed -n '$p' \
  | sed -E "s/.*cd[[:space:]]+//; s/[\"']//g")
if [ -n "$CD" ]; then
  cd "${CD/#\~/$HOME}" || block "cannot enter $CD to read the PR; name it with --repo"
fi
# Only stdout is the answer: gh also writes hints to stderr (since 2.105, when it detects an
# agent), which would break jq. stderr goes to a file, quoted when gh fails.
ERR=$(mktemp "${TMPDIR:-/tmp}/guard-pr-merge.XXXXXX") || block "cannot create a temporary file"
trap 'rm -f "$ERR"' EXIT
gh_failed() {
  local why
  why=$(grep -v '^[[:space:]]*$' "$ERR" | grep -iv '^hint:' | tail -n 3 | tr '\n' ' ')
  block "$1${why:+: $why}"
}
# shellcheck disable=SC2086
VIEW=$(gh pr view $PR "${REPO_ARG[@]}" --json isDraft,statusCheckRollup,url,labels 2>"$ERR") \
  || gh_failed "cannot read the PR (gh pr view $PR ${REPO_ARG[*]} failed)"
echo "$VIEW" | jq -e 'type == "object"' >/dev/null 2>&1 \
  || block "gh pr view $PR ${REPO_ARG[*]} did not answer with JSON"

[ "$(echo "$VIEW" | jq -r '.isDraft')" = "false" ] || block "the PR is still a draft"

HELD=$(echo "$VIEW" | jq -r '[.labels[].name | select(. == "needs introduction" or . == "agent files")] | join(", ")')
[ -z "$HELD" ] || block "the PR is labelled $HELD; the maintainer removes it after the introduction is accepted or the agent files are read"

# The PR url is https://github.com/<owner>/<repo>/pull/<number>.
IFS=/ read -r _ _ _ OWNER REPO _ NUMBER <<< "$(echo "$VIEW" | jq -r '.url')"
STRICT=false
case "$OWNER/$REPO" in going-haywire/haywire | going-haywire/haybale-*) STRICT=true ;; esac
OPEN_THREADS=$(gh api graphql -F owner="$OWNER" -F repo="$REPO" -F number="$NUMBER" -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) { reviewThreads(first: 100) { nodes { isResolved } } }
    }
  }' --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not)] | length' 2>"$ERR") \
  || gh_failed "cannot read the PR's review threads (gh api graphql failed)"
[ "$OPEN_THREADS" = "0" ] || block "$OPEN_THREADS review thread(s) unresolved; read them, address them, resolve them"

# One entry per check and run: keep the newest run of each check.
VERDICT=$(echo "$VIEW" | jq -r --argjson strict "$STRICT" '
  [.statusCheckRollup[]
   | if .__typename == "StatusContext"
     then {key: .context, at: (.startedAt // ""), ok: (.state == "SUCCESS"), done: (.state != "PENDING")}
     else {key: ((.workflowName // "") + "/" + .name), at: (.startedAt // ""),
           ok: ((.conclusion // "") | IN("SUCCESS", "SKIPPED", "NEUTRAL")),
           done: (.status == "COMPLETED"), macos: ((.name | test("macos"; "i")) and .conclusion == "SUCCESS")}
     end]
  | group_by(.key) | map(max_by(.at)) as $latest
  | if ($latest | length) == 0 then (if $strict then "no checks reported" else "ok" end)
    elif ($latest | map(select(.done | not)) | length) > 0
      then "checks still running: " + ($latest | map(select(.done | not) | .key) | join(", "))
    elif ($latest | map(select(.ok | not)) | length) > 0
      then "checks not passed: " + ($latest | map(select(.ok | not) | .key) | join(", "))
    elif $strict and ($latest | map(select(.macos == true)) | length) == 0
      then "no passed macOS check yet"
    else "ok" end')

[ "$VERDICT" = "ok" ] || block "$VERDICT"
exit 0
