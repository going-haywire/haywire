---
status: draft
doc_template: workflow
scope: W9, the maintainer releases core when they decide; one "publish" opens and merges the release PR, and CI tags and publishes
see-also:
  - index.md
  - core-and-library-change.md
  - ../adr/0088-a-release-is-the-merge-of-a-release-pr-and-ci-tags-it.md
---

# A core release

**For:** the maintainer and the lead. Core releases are batched: merged changes wait on
`master` until the maintainer starts a release.

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant Lead as Lead (/release)
    participant GH as Core on GitHub
    participant CI as publish.yml
    participant PyPI

    You->>Lead: ① "release"
    Lead->>You: what it would ship: changes, waiting libraries,<br/>their nightly runs, reminders, a proposed version
    Lead->>GH: master's CI green?
    Lead->>Lead: release branch, bump, diff, wheel smoke
    Lead->>You: the diff: "publish vX.Y.Z?"
    You->>Lead: ② "publish"
    Lead->>GH: release PR → checks → merge
    GH->>CI: version changed on master
    CI->>CI: plan → gate → build → tag vX.Y.Z
    CI->>PyPI: every core package
    CI->>GH: GitHub release with notes
    Lead->>You: the notes, then the libraries it unblocks: "publish them?"
    You->>Lead: ③ "publish" → a release task per library
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| ① When to release | maintainer | [ADR 0087](../adr/0087-releases-are-batched-and-a-librarys-dependency-floor-guards-its-release.md) |
| What it would ship, the version proposal | lead | [The release skill](https://github.com/going-haywire/haywire/blob/master/.claude/skills/release/SKILL.md), step 0 |
| Waiting and unblocked libraries | lead | `scripts/release_sweep.py floors` and `nightly`, read by the release skill |
| ② "publish" | maintainer | [The release skill](https://github.com/going-haywire/haywire/blob/master/.claude/skills/release/SKILL.md), step 5 |
| The merge run | CI | [Publishing releases](../reference/publish_releases.md), [ADR 0088](../adr/0088-a-release-is-the-merge-of-a-release-pr-and-ci-tags-it.md) |
| ③ The unblocked libraries | lead asks | [The release skill](https://github.com/going-haywire/haywire/blob/master/.claude/skills/release/SKILL.md), the last step; then [A library release](library-release.md) |
