#!/bin/bash
# Refuses `gh pr merge` unless the PR is out of draft, carries neither `needs introduction`
# nor `agent files`, has no unresolved review thread, and the newest run of every check
# passed. In going-haywire/haywire there must be checks, with at least one passed macOS
# check among them (macOS runs only once a PR is ready); a repository without CI (the
# libraries) may report none. `--repo` / `-R` is honoured.

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

cd "${CLAUDE_PROJECT_DIR:-.}" || block "cannot enter the project folder"
# shellcheck disable=SC2086
VIEW=$(gh pr view $PR "${REPO_ARG[@]}" --json isDraft,statusCheckRollup,url,labels 2>&1) \
  || block "cannot read the PR ($VIEW)"

[ "$(echo "$VIEW" | jq -r '.isDraft')" = "false" ] || block "the PR is still a draft"

HELD=$(echo "$VIEW" | jq -r '[.labels[].name | select(. == "needs introduction" or . == "agent files")] | join(", ")')
[ -z "$HELD" ] || block "the PR is labelled $HELD; the maintainer removes it after the introduction is accepted or the agent files are read"

# The PR url is https://github.com/<owner>/<repo>/pull/<number>.
IFS=/ read -r _ _ _ OWNER REPO _ NUMBER <<< "$(echo "$VIEW" | jq -r '.url')"
CORE=false
[ "$OWNER/$REPO" = "going-haywire/haywire" ] && CORE=true
OPEN_THREADS=$(gh api graphql -F owner="$OWNER" -F repo="$REPO" -F number="$NUMBER" -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) { reviewThreads(first: 100) { nodes { isResolved } } }
    }
  }' --jq '[.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved | not)] | length' 2>&1) \
  || block "cannot read the PR's review threads ($OPEN_THREADS)"
[ "$OPEN_THREADS" = "0" ] || block "$OPEN_THREADS review thread(s) unresolved; read them, address them, resolve them"

# One entry per check and run: keep the newest run of each check.
VERDICT=$(echo "$VIEW" | jq -r --argjson core "$CORE" '
  [.statusCheckRollup[]
   | if .__typename == "StatusContext"
     then {key: .context, at: (.startedAt // ""), ok: (.state == "SUCCESS"), done: (.state != "PENDING")}
     else {key: ((.workflowName // "") + "/" + .name), at: (.startedAt // ""),
           ok: ((.conclusion // "") | IN("SUCCESS", "SKIPPED", "NEUTRAL")),
           done: (.status == "COMPLETED"), macos: ((.name | test("macos"; "i")) and .conclusion == "SUCCESS")}
     end]
  | group_by(.key) | map(max_by(.at)) as $latest
  | if ($latest | length) == 0 then (if $core then "no checks reported" else "ok" end)
    elif ($latest | map(select(.done | not)) | length) > 0
      then "checks still running: " + ($latest | map(select(.done | not) | .key) | join(", "))
    elif ($latest | map(select(.ok | not)) | length) > 0
      then "checks not passed: " + ($latest | map(select(.ok | not) | .key) | join(", "))
    elif $core and ($latest | map(select(.macos == true)) | length) == 0
      then "no passed macOS check yet"
    else "ok" end')

[ "$VERDICT" = "ok" ] || block "$VERDICT"
exit 0
