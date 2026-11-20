---
name: a-release-is-the-merge-of-a-release-pr-and-ci-tags-it
description: A release is the merge of a release PR holding only the version bump; the merge run passes the PR gate, builds, tags and publishes in one run, so the user no longer pushes tags and "who may publish" becomes "who may merge"
status: accepted
see-also: ADR-0087, ADR-0089
level: architectural
---

# A release is the merge of a release PR, and CI tags it

**Context.**

- Core's release flow: a release branch and PR, a squash merge, the agent tags, the user pushes the tag (a local hook blocks tag pushes), and `publish.yml` gates, builds and publishes.
- Library repositories commit straight to master and `share` pushes the release commit and tag there. That cannot work once master requires PRs.
- A push, tag or PR made with `GITHUB_TOKEN` starts no further workflow run (except `workflow_dispatch` and `repository_dispatch`). A run that tags cannot rely on the tag to start the publish.
- PyPI's trusted publisher is tied to the workflow file and environment, not to the trigger.

**Decision.**

- **A release PR holds only the version bump and generated files.** Merging it is the decision to publish.
- **The merge run tags and publishes in the same run.** Its order is gate → build → tag → publish, so a failed gate leaves no tag.
- **`share` gains an opt-in PR mode** that opens the release PR. Core's release PR already exists. The simple path (push to the default branch) is unchanged.
- **The user no longer pushes tags.** Who may publish is who may merge.

**Considered.**

- *An automated dispatch with a bypass credential.* A secret that can publish, held by CI, for a gain the merge run already gives.
- *Dynamic versioning (version from the tag).* Removes the bump commit but changes every package's build and the lockstep scripts, and leaves master without the released version.

**Consequences.**

- Tag and publish are one run and one workflow file; a split would need a credential that can start further runs.
- The merge of a release PR is the point of no return and is the user's word: "publish", which an agent never takes from a "merge".
- Every release is a GitHub Release with generated notes.
- A failed publish after the merge leaves a merged bump without a release; the run is re-run or fixed forward.
