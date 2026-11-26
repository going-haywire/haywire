---
name: orchestrators-plug-into-four-task-events-through-one-slot-per-tool
description: the repository stays orchestrator-neutral; a task has four events (created, viewed, message the lead, merged), each with one neutral part, and every orchestrator (T3 Code, herdr, …) is an optional slot that only translates those events to the neutral parts
status: accepted
see-also: ADR-0089, ADR-0081
level: architectural
---

# Orchestrators plug into four task events through one slot per tool

**Context.**

- The lead and its tasks (one session per worktree) were written for herdr: its addresses, `hc send`, `herdr-app` and its worktree folder were in the workflow skill, the session-start hook and the task view.
- The maintainer moves to T3 Code as the orchestrator (S8 spike, PR #158). Other developers may bring other tools, or none: contributors need no orchestrator at all.
- What a task needs from any orchestrator is small: a worktree with the setup run, a view of the tasks, a way to report to the lead, and cleanup after the merge. Each of these already has a neutral script or rule.

**Decision.**

- **A task has four events, each with one neutral part:**

  | Event | Neutral part |
  |---|---|
  | Created | `scripts/worktree_setup.py` in the new worktree |
  | Viewed | `tasks.py` in the workflow skill |
  | Message the lead | The workflow skill's report rule |
  | Merged | `finish.py <branch>` (ADR 0089) |

- **An orchestrator only translates those events.** Logic goes into the neutral parts; a tool's files call them.
- **One slot per tool**, every slot optional:
  - `plugins/haywire-dev/orchestrators/<tool>/session.sh`: prints session-start context when its tool runs the session, nothing otherwise. The slot decides that itself.
  - `plugins/haywire-dev/orchestrators/<tool>/agents.py` (optional): prints the tool's live agent sessions as `{"agents": [{"cwd", "address", "status"}]}` for the task view.
  - `plugins/haywire-dev/skills/haywire-workflow/orchestrators/<tool>.md`: the agent's how-to for the four events in that tool.
  - `docs/collaboration/orchestrators/<tool>.md`: a person's setup.
  - A file the tool requires at the repository root (`t3.json`) stays thin: it only calls neutral scripts.
- **The neutral parts name no tool.** `hooks/session-place.sh` runs every slot's `session.sh` and joins what they print; `tasks.py` runs every slot's `agents.py`; the workflow skill and the docs link to the slot pages. Adding a tool adds a slot and touches no neutral file.
- **The plugin carries the slots**, so the org's libraries get them; a library's root file (`t3.json`) comes from the project template.
- **T3 Code is the first slot, herdr the second.**

**Considered.**

- *Adopt one orchestrator as the repository's own* (firstmate, then T3). Ties contributors to one tool; firstmate also merges and tears down with its own scripts, outside the merge guard and `finish`.
- *The dispatcher detects each tool by its environment.* Adding a tool would change a neutral hook; the slot's `session.sh` checks its own environment instead.
- *One shared how-to with tool sections.* Every new tool edits the neutral skill.

**Consequences.**

- A session without an orchestrator gets no place context and no session column in the task view; the user relays messages, as before.
- Two tools in one session (T3 started from a herdr terminal) both speak at session start.
- T3 has no `agents.py`: the task view shows no session for its tasks; the lead reads its threads through T3's own tools.
- A behaviour a tool needs beyond translation is a change to a neutral part, reviewed as such.

## Amendment (ADR 0094)

The slots moved from `plugins/haywire-dev/orchestrators/` to core's `dev/orchestrators/<tool>/`, and the agent's how-to from the workflow skill's folder to `docs/collaboration/orchestrators/<tool>-agent.md` (ADR 0094). The contract is unchanged.

## Amendment (2026-11-26, #261)

Starting a folder's studio is not a task event (nothing fires it, and it runs in the main
folder too), but it follows the same rule: one neutral part, `dev/scripts/studio.py
start|stop|status`, which a tool's files only call. It runs the umbrella's `haywire-studio`
(ADR 0081) when that is on the `PATH`, else the checkout's own environment, and says which.
`t3.json` calls it in core and, through `../haywire-repo`, in every library; the agent-facing
docs name it. A slot that wires the umbrella's `haywire-studio` directly (herdr's key binding)
still starts the same full studio.
