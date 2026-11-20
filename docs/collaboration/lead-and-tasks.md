---
status: draft
doc_template: workflow
scope: W11, one lead session per machine starts tasks in worktrees, receives their reports, and merges and publishes on the maintainer's word
see-also:
  - index.md
  - task-with-live-check.md
---

# Lead and tasks

!!! note "Provisional"
    This page draws the lead layer as it runs today, on herdr with `hc`. A trial of
    firstmate as the lead layer may change it.

**For:** the maintainer running several tasks at once. Without a lead, the maintainer is
the lead and each task session does the lead's part itself.

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant Lead as Lead (main folder)
    participant herdr
    participant Task as Task (worktree, tab = branch)
    participant GH as GitHub

    You->>Lead: ① what to do
    Lead->>Lead: worktree + branch from master, worktree_setup.py
    Lead->>herdr: a space with the brief
    herdr->>Task: the session starts
    Task->>Lead: PR opened / live check waiting / ready / blocked / needs a decision
    Lead->>You: ② decisions by name: space / tab, PR URL
    You->>Lead: "merge" / "publish" / an option
    Lead->>GH: merge, watch master, warn tasks that now conflict
    Lead->>Task: "merged"
    Task->>Task: finish
    Task->>Lead: finished
    You->>herdr: close the space
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| ① Start a task | lead | [The workflow skill: lead and tasks](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#lead-and-tasks) |
| Worktrees and their rules | lead, task | [The workflow skill: parallel sessions](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#parallel-sessions) |
| Reports, names, `hc send` | task, lead | [The workflow skill: lead and tasks](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#lead-and-tasks) |
| ② Decisions | you | [The workflow skill: asking the user for a decision](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#asking-the-user-for-a-decision) |
| Merge, watch master, finish | lead, task | [The workflow skill: finishing as the maintainer](https://github.com/going-haywire/haywire/blob/master/plugins/haywire-dev/skills/haywire-workflow/SKILL.md#finishing-as-the-maintainer) |
| The task view | lead | `tasks.py` in the workflow skill's folder |
