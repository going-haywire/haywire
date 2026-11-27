---
serve: developer
status: current
doc_template: reference
scope: Read as a lead before starting a task — the brief's sections, to copy and fill in as the task's first message
see-also:
  - workflow.md
  - lead-and-tasks.md
---

# The brief

A lead starts each task with a brief as its first message (*Lead and tasks* in
[the workflow](workflow.md)). Copy the block, fill in every section, and write *none* where
nothing applies; a missing section is something the task has to guess.

```markdown
## Brief

**Issue:** <issue URL>

**Branch:** <kind>/<name>

**Acceptance:**
- <what the task proves done, one point each: tests, checks, docs>

**Decided:** <choices already made, which the task does not re-open>

**Approved:** none | push and draft PR | … — commit locally until this line says more.

**Reserved for the owner:** <anything the task asks about, never decides: an architecture
choice, a public name, a new hook or script>

**Lead link:** <[<tag> ◆ lead](t3-thread://v2/<environment>/<thread id>) | herdr address>
Record it first: `python3 <core>/dev/scripts/worktree_setup.py --lead <link>`, the bare
`t3-thread://…` URL or the herdr address (skip when the session-start hook already names it).

**Read first:** docs/collaboration/workflow.md, the orchestrator's `<tool>-agent.md`,
<the plan or the files to start from>
```

**Approved** is the only place a task reads its limits from. The lead widens it with a
message naming the line ("Approved: push and draft PR"); an owner's answer in the task's
thread widens it too, and the task reports it to the lead as *Decided*. A question for the
owner follows *Asking the user for a decision* in [the workflow](workflow.md).
