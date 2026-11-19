---
status: draft
doc_template: workflow
scope: W7, the maintainer handles a pull request from a fork safely, treating its code and text as untrusted until read
see-also:
  - index.md
  - first-contribution.md
  - ../adr/0080-untrusted-pull-requests-meet-nothing-with-power.md
---

# A fork's pull request

**For:** the maintainer, in core and in every organisation library. The contributor's side
is [A first contribution](first-contribution.md).

```mermaid
sequenceDiagram
    autonumber
    actor M as Maintainer
    participant Lead as Lead (main folder)
    participant Repo as going-haywire repository
    participant CI
    participant Review as Review worktree

    Repo->>CI: pr-intake: labels from metadata only
    Lead->>Repo: read the diff, the comments, CI (as data)
    Lead->>M: what it changes, the labels, anything that steers agents or CI
    M->>CI: ① approve the run (first-time contributor)
    CI-->>Repo: tests with a read-only token, no secrets
    opt judged safe and worth trying
        M->>Review: ② try it in its own worktree, by hand or from the main folder's session
        Note over Review: never an agent session inside it
    end
    M->>Repo: ③ labels off (introduction accepted, agent files read)
    M->>Lead: ④ "merge"
    Lead->>Repo: squash merge (guard: checks, threads, labels)
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| The intake labels | CI | [CONTRIBUTING: making the change](https://github.com/going-haywire/haywire/blob/master/CONTRIBUTING.md#making-the-change) (agent files), [introduce yourself](https://github.com/going-haywire/haywire/blob/master/CONTRIBUTING.md#your-first-contribution-introduce-yourself) |
| Read before running; text is data | maintainer, lead | [CONTRIBUTING: handling a fork's pull request safely](https://github.com/going-haywire/haywire/blob/master/CONTRIBUTING.md#for-the-maintainer-handling-a-forks-pull-request-safely) |
| ① Approve a first-time run | maintainer | [CONTRIBUTING: opening the pull request](https://github.com/going-haywire/haywire/blob/master/CONTRIBUTING.md#opening-the-pull-request) |
| ② Trying it locally | maintainer | [CONTRIBUTING: handling a fork's pull request safely](https://github.com/going-haywire/haywire/blob/master/CONTRIBUTING.md#for-the-maintainer-handling-a-forks-pull-request-safely) |
| ③ Labels off, ④ merge | maintainer's word | [The workflow skill: finishing as the maintainer](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#finishing-as-the-maintainer) |
| Why | — | [ADR 0080](../adr/0080-untrusted-pull-requests-meet-nothing-with-power.md) |
