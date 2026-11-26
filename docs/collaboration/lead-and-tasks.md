---
status: draft
doc_template: workflow
scope: W11, one lead session per machine starts tasks in worktrees, receives their reports, and merges and publishes on the maintainer's word
see-also:
  - index.md
  - orchestrators/index.md
  - task-with-live-check.md
---

# Lead and tasks

**For:** the maintainer running several tasks at once. Without a lead, the maintainer is
the lead and each task session does the lead's part itself. An
[orchestrator](orchestrators/index.md) runs the sessions and carries their messages; any
will do, or none (then you open the sessions and pass the messages on). Each orchestrator
only translates the four task events below to the same neutral scripts and rules.

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant Lead as Lead (main folder)
    participant Orch as Orchestrator
    participant Task as Task (worktree, named by its branch)
    participant GH as GitHub

    You->>Lead: ① what to do
    Lead->>Orch: worktree + branch from master, the brief
    Orch->>Task: worktree_setup.py, the session starts
    Task->>Lead: PR opened / live check waiting / ready / blocked / needs a decision
    Lead->>You: ② decisions by name: task, PR URL
    You->>Lead: "merge" / "publish" / an option
    Lead->>GH: merge, watch master, warn tasks that now conflict
    Lead->>Task: "merged"
    Task->>Task: finish
    Task->>Lead: finished
    Orch->>Orch: the worktree's folder goes
```

| Step | Who | Where the rule or command lives |
|---|---|---|
| ① Start a task (event *created*); reports and names (event *message the lead*) | lead, task | [The workflow: lead and tasks](workflow.md#lead-and-tasks), [the brief](brief.md), `worktree_setup.py --lead`, the [orchestrator's page](orchestrators/index.md) |
| Worktrees and their rules | lead, task | [The workflow: parallel sessions](workflow.md#parallel-sessions) |
| ② Decisions | you | [The workflow: asking the user for a decision](workflow.md#asking-the-user-for-a-decision) |
| Merge, watch master, finish (event *merged*) | lead, task | [The workflow: finishing as the maintainer](workflow.md#finishing-as-the-maintainer) |
| The task view (event *viewed*) | lead | `tasks.py` in core's `dev/scripts/` |
| The tool itself | you | [Orchestrators](orchestrators/index.md) |
