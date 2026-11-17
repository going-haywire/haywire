# S2 rulesets: the commands the user runs

Decision Q11 of [the workflow review](../2026-11-16-workflow-review.md). Run from the
repository root, in this order, as the user (the hook blocks these `gh api` writes for
agents). Each JSON file is the full request body.

```sh
# 1. Permanent refs: master and gh-pages cannot be deleted or force-pushed; nobody bypasses.
gh api -X POST repos/going-haywire/haywire/rulesets \
  --input workbench/plans/2026-11-17-s2-rulesets/permanent-refs.json

# 2. Release tags: v* tags cannot be deleted or moved; creating them stays allowed.
gh api -X POST repos/going-haywire/haywire/rulesets \
  --input workbench/plans/2026-11-17-s2-rulesets/release-tags.json

# 3. PR gate: MasterMerger (id 26753369) loses deletion and non_fast_forward; Admin
#    bypasses only through a pull request. Keeps the four required checks and the PR rule.
gh api -X PUT repos/going-haywire/haywire/rulesets/26753369 \
  --input workbench/plans/2026-11-17-s2-rulesets/pr-gate.json
```

Steps 1 and 2 go first, so `master` is never without a deletion rule.

## Verify

```sh
gh api repos/going-haywire/haywire/rules/branches/master --jq '.[].type'
gh api repos/going-haywire/haywire/rules/branches/gh-pages --jq '.[].type'
gh api repos/going-haywire/haywire/rulesets --jq '.[] | "\(.id) \(.name) \(.enforcement)"'
gh api repos/going-haywire/haywire/rulesets/<release-tags id> \
  --jq '{target, include: .conditions.ref_name.include, rules: [.rules[].type], bypass: .bypass_actors}'
```

The rules API has no endpoint for tags, so the tag ruleset is read directly.

Expected:

- `master` lists `deletion`, `non_fast_forward` (Permanent refs) and
  `required_status_checks`, `pull_request` (MasterMerger).
- `gh-pages` lists `deletion` and `non_fast_forward`.
- The tag ruleset targets `tag`, includes `refs/tags/v*`, lists `deletion` and
  `non_fast_forward`, and has no bypass actors.
- Three rulesets, all `active`.
- The next docs deploy to `gh-pages` succeeds. Both deploy steps
  ([docs.yml](../../../.github/workflows/docs.yml),
  [publish.yml](../../../.github/workflows/publish.yml)) push without force
  (`keep_files: true`, no `force_orphan`), so the non-fast-forward rule does not stop them.

## Roll back

`pr-gate.before.json` is MasterMerger as it is today (the state read on 2026-11-17).

```sh
gh api -X DELETE repos/going-haywire/haywire/rulesets/<id>      # each new ruleset
gh api -X PUT repos/going-haywire/haywire/rulesets/26753369 \
  --input workbench/plans/2026-11-17-s2-rulesets/pr-gate.before.json
```
