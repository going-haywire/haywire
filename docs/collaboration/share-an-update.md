---
status: draft
doc_template: workflow
scope: W2, a library author shares an update of an already shared library, straight from the default branch or through a release pull request
see-also:
  - index.md
  - ../guides/sharing-libraries.md
---

# Share an update

**For:** library authors whose library is already shared once
([Create and first share](create-and-share.md)).

```mermaid
sequenceDiagram
    autonumber
    actor You as Author
    participant Agent as Your agent (optional)
    participant Studio as haywire share
    participant Host as Your repository
    participant PyPI

    You->>Host: commit and push the change
    Agent->>You: open release reminders? release anyway?
    You->>Agent: ① "yes"
    alt default branch accepts pushes
        Studio->>Studio: preflight, dependency floors, bump, docs, marketstall
        Studio->>Host: commit, tag, push
    else protected default branch (share --pr)
        Studio->>Host: release branch and its pull request
        You->>Host: ② merge the release pull request
        Host->>Host: publish.yml tags the merge
    end
    Host->>PyPI: publish.yml uploads (distribute = pypi)
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| Commit and push | author | [Sharing libraries §4.1](../guides/sharing-libraries.md#41-git-requirements) |
| ① Release reminders | the author's agent proposes, the author decides | [Sharing libraries §7.1](../guides/sharing-libraries.md#71-release-reminders) |
| Share | author or agent | [Sharing libraries §2](../guides/sharing-libraries.md#2-publishing); the agent acts on `share --status` through the project's `CLAUDE.md` |
| A dependency floor no PyPI release satisfies stops the share | `share` | [Sharing libraries §4.4](../guides/sharing-libraries.md#44-dependency-floors-must-exist-on-pypi) |
| ② Through a release pull request | author | [Sharing libraries §7.2](../guides/sharing-libraries.md#72-releasing-through-a-pull-request-advanced) |
| The upload | `publish.yml` | [Publishing to PyPI §4](../guides/publish-to-pypi.md#4-the-workflow) |

!!! note "A project created by an older haywire"
    The publishing workflow comes from `haywire init` and does not update itself. A project
    created before the release-PR mode copies `.github/workflows/publish.yml` and
    `.github/publish_plan.py` from a fresh `haywire init`
    ([Sharing libraries §7.2](../guides/sharing-libraries.md#72-releasing-through-a-pull-request-advanced)).
