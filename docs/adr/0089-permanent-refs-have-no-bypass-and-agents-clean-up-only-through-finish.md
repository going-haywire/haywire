---
name: permanent-refs-have-no-bypass-and-agents-clean-up-only-through-finish
description: master, gh-pages and the v* tags are protected by a ruleset with no bypass at all, a second ruleset gates merges with admin bypass only through a PR, and agents remove their merged branches and worktrees only through a finish script the hook allows
status: accepted
see-also: ADR-0080, ADR-0088
level: architectural
---

# Permanent refs have no bypass; agents clean up only through `finish`

**Context.**

- Agents act as the user: git pushes with the user's SSH key, `gh` with a `repo` and `workflow` token. GitHub cannot tell the two apart, so the admin bypass of the existing ruleset applies to both.
- Only the local hook `block-dangerous-git.sh` stops a destructive command, and it can be edited or not run.
- After a squash merge the safe branch delete refuses and the forced one is blocked, so merged local branches pile up and only the user can delete them. A PR closed unmerged keeps its remote branch.
- The user does not want to give agents power over master.

**Decision.**

- **Two rulesets.** *Permanent refs*: `master`, `gh-pages` and the `v*` tags cannot be deleted or force-pushed, with no bypass at all. *PR gate*: required checks and PRs, admin bypass only through a PR.
- **The hook blocks `gh api` writes to rulesets and branch protection.**
- **A `finish` script ends a merged task**, and the hook allows only that. It checks the PR merged (closed unmerged: `--abandon`, on the user's word) and that nothing is unpushed; inside a worktree it detaches to `origin/master`, then deletes the local and remote branch; from the main folder it also removes a clean worktree. `--sweep` lists leftovers and cleans them on the user's word.
- **The lead merges on the user's word and tells the task "merged"; the task agent runs `finish` itself.** Without a lead the user is the lead.

**Considered.**

- *The hook alone.* The only barrier is a local file the agent could change.
- *Bypass through a PR only, for every ref.* Leaves `gh-pages` and tags deletable by the same credential.
- *A bot identity for agents.* A second account and token to manage; the no-bypass rule already binds the credential agents hold.
- *A relaxed hook that allows forced branch deletes.* Gives agents deletion of any branch, not only proven-merged ones.

**Consequences.**

- Nobody, including the user, can rewrite or delete a permanent ref without first changing the ruleset on GitHub.
- Both `gh-pages` deploys push ordinary commits (`keep_files: true`, `force_orphan: false`), so they are compatible with the no-force rule.
- A change to the rulesets or the hook takes effect only after review; the hook and the rule are changed together.
- `finish` is the single place that knows what "proven merged" means.
