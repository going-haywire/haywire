---
status: draft
doc_template: workflow
scope: W8, a library needs a core change that is not released yet; both merge at once and the library's dependency floor holds its release until core's
see-also:
  - index.md
  - core-release.md
  - library-release.md
  - ../adr/0087-releases-are-batched-and-a-librarys-dependency-floor-guards-its-release.md
---

# A change across core and a library

**For:** the maintainer and their agents. Example: visiongraph needs a new option in core.
Both changes merge at once; nothing is released early.

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant Core as Core repository
    participant Lib as Library repository
    participant CI
    participant PyPI

    Core->>CI: core PR (task as in W6)
    You->>Core: ① "merge": in master, not released
    Lib->>Lib: library PR; the same commit raises its floor<br/>to the next core patch (>=0.5.5 while PyPI has 0.5.4)
    Lib->>CI: tests against core's master: pass
    You->>Lib: ② "merge"
    Note over Lib: waiting: share refuses a floor PyPI cannot satisfy
    You->>Core: ③ "publish" (when you decide)
    Core->>PyPI: core 0.5.5
    Core-->>You: the release report: visiongraph is unblocked, publish it?
    You->>Lib: ④ "publish"
    Lib->>PyPI: the library's release
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| The core change | task | [A task with its live check](task-with-live-check.md) |
| ② The floor in the same commit | library task | [Library CONTRIBUTING: rules](https://github.com/going-haywire/.github/blob/main/CONTRIBUTING.md#rules-that-are-specific-to-libraries), [Sharing libraries §4.4](../guides/sharing-libraries.md#44-dependency-floors-must-exist-on-pypi) |
| CI against core's `master` | CI | [The workflow skill: in a library repository](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#in-a-library-repository) |
| A wait no floor can record | agent proposes a reminder | [Sharing libraries §7.1](../guides/sharing-libraries.md#71-release-reminders) |
| ③ The core release | lead on your word | [A core release](core-release.md) |
| ④ The unblocked libraries | lead asks, a release task each | [A library release](library-release.md) |
| Why | — | [ADR 0087](../adr/0087-releases-are-batched-and-a-librarys-dependency-floor-guards-its-release.md) |
