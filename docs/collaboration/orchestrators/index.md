---
status: draft
doc_template: guide
scope: The orchestrator slot, how an app that runs the lead and its tasks plugs into the repository through four task events, and how to add a tool
see-also:
  - ../lead-and-tasks.md
  - ../../adr/0090-orchestrators-plug-into-four-task-events-through-one-slot-per-tool.md
---

# Orchestrators

An **orchestrator** is an app that runs the [lead and its tasks](../lead-and-tasks.md) as
agent sessions side by side, each task in its own worktree, and carries their messages.
You need none: without one you open the sessions yourself and pass the messages on. The
repository works with any orchestrator through one **slot** per tool
([ADR 0090](../../adr/0090-orchestrators-plug-into-four-task-events-through-one-slot-per-tool.md)).

| Tool | Page |
|---|---|
| T3 Code | [T3 Code](t3.md) |
| herdr | [herdr](herdr.md) |

## The four events

A task has four events. Each has one neutral part that works without any orchestrator; a
tool only translates its own way of doing things to it.

| Event | The neutral part |
|---|---|
| A task is created | [`dev/scripts/worktree_setup.py`](https://github.com/going-haywire/haywire/blob/master/dev/scripts/worktree_setup.py) runs in the new worktree: the branch from the latest `master`, `uv sync`, a studio port of its own |
| The tasks are viewed | [`tasks.py`](https://github.com/going-haywire/haywire/blob/master/dev/scripts/tasks.py) lists every worktree with its PR, checks and, when a slot can tell, its session |
| A task messages the lead | The report rule in [the workflow](../workflow.md#lead-and-tasks): *PR opened*, *Ready*, *Blocked*, … one line each with the PR's URL |
| The PR is merged | [`finish.py <branch>`](https://github.com/going-haywire/haywire/blob/master/dev/scripts/finish.py) deletes the branches and frees the worktree ([ADR 0089](../../adr/0089-permanent-refs-have-no-bypass-and-agents-clean-up-only-through-finish.md)) |

## A slot

Every file of a slot is optional:

| File | What it does |
|---|---|
| `dev/orchestrators/<tool>/session.sh` | At session start, prints a paragraph for the agent when its tool runs the session (where it runs, how to message the lead), nothing otherwise; lines starting with `user: ` are shown to you, the developer, for something only you can fix (a slot that uses them tells the agent too, for tools that do not show them) |
| `dev/orchestrators/<tool>/agents.py` | Prints the tool's live sessions, `{"agents": [{"cwd", "address", "status"}]}`, for the task view |
| `docs/collaboration/orchestrators/<tool>-agent.md` | The agent's how-to: the four events in this tool |
| `docs/collaboration/orchestrators/<tool>.md` | Your setup: what to install, which settings to choose, and how to start the studio from it |
| A file the tool reads at the repository root | Only calls the neutral scripts; [`t3.json`](https://github.com/going-haywire/haywire/blob/master/t3.json) is one |

The hook `session-place.sh` runs every slot's `session.sh`, and `tasks.py` every slot's
`agents.py`. The `haywire-dev` plugin carries the slots, so the organisation's libraries get
them too.

## Adding a tool

1. Write the slot's files above, starting with the agent's how-to: for each of the four
   events, what the lead and the task do in this tool, ending in the neutral part.
2. Keep logic out of the slot. If the tool needs a behaviour the neutral parts lack,
   change the neutral part in its own pull request.
3. Add the tool to the table on this page and its page to the menu (`mkdocs.yml`).
4. Touch no neutral file otherwise: the workflow, the hooks and `tasks.py` find the
   slot by its folder.
