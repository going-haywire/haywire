---
name: agent-tooling-comes-from-the-place-of-work
description: a session's agent tooling comes from the folder it works in (its committed harness configs and its own Haywire environment), not from plugins installed per machine; all text lives in docs/, every other markdown file outside it points there
status: accepted
see-also: ADR-0086, ADR-0090, ADR-0093, ADR-0094
level: architectural
---

# Agent tooling comes from the place of work

**Context.**

- Two Claude plugins (`haywire`, `haywire-dev`) from two marketplaces, an npm proxy and per-machine, per-clone installs carried the agent tooling. A worktree of an org library ran without the workflow and its guardrails (#203), and the arrangement had become something only an agent could follow.
- Every place of work already has its own Haywire environment (`haywire init`, `uv sync`), and an org library already needs core cloned beside it.
- The goals, stated before mechanisms (plan `workbench/plans/2026-11-22-agent-tooling-goals.md`, #215): one starting point, any harness, no setup per folder, tooling that matches the place's Haywire version, guardrails only in org repositories and their forks, one home per piece.

**Decision.**

- **A place of work gets its tooling from itself:** thin committed harness configs, one per supported harness, (`.mcp.json`, `.claude/settings.json`) pointing at its own Haywire environment. `haywire init` writes a project's; `going-haywire/.github`'s `templates/library/` an org library's. No plugin, no marketplace, no install per machine or folder.
- **Developer tooling is code in core's `dev/`** (hooks, scripts, orchestrator slots). Core runs it in place; an org library reaches it through `../haywire-repo/dev/`, and a worktree's setup links core beside it wherever the orchestrator put it.
- **All text lives in `docs/`.** A front-matter marker (`serve: product | developer`) says which pages the Farmhand bridge serves; a repository declares its developer docs in `[tool.haywire.agents]`. Every other markdown file outside `docs/` is a pointer, except core's `CLAUDE.md`, which keeps core's own always-in-context rules and nothing the docs say.
- **One starting point:** a sentence pointing any agent at `docs/agents/start.md`.

**Considered.**

- *One marketplace for both plugins, installed at user scope and switched on per project.* It kept a per-machine install, a version that ignores the place's Haywire, and the tangle (the first design round of #203, set aside).
- *Developer tooling in `going-haywire/.github`.* Ten of the eleven commits that changed it in the week before this decision also changed core's docs or scripts.

**Consequences.**

- A worktree of any org repository has its workflow, hooks and bridge as soon as its setup ran; a fresh clone has them at once.
- Any harness gets the floor (instructions and the studio connection) through MCP; hooks come only where a harness can enforce them. Guarantees stay on GitHub (ADR 0089).
- Instructions served as resources are followed less exactly than a loaded skill (the experiment in the plan), so they are written unambiguously and guarded where it matters.
