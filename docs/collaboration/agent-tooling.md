---
serve: developer
status: current
doc_template: reference
scope: Read to find where an agent-facing file lives and who runs it — the adapters, the developer tooling in dev/, the docs pages the Farmhand bridge serves, per repository
see-also:
  - basics.md
  - workflow.md
  - ../adr/0092-agent-tooling-comes-from-the-place-of-work.md
---

# Agent tooling: what lives where

The whole picture in three sentences:

1. One sentence brings any agent to the [start page](../agents/start.md), which sets up a project
   or the clones of the organisation's repositories.
2. Every repository carries small committed **adapters**, one per supported agent harness, which
   point the harness at the repository's own Haywire: the **Farmhand bridge** gives the session
   its instructions and the studio's tools, in the version the repository runs.
3. The organisation's repositories also run core's **`dev/`**: the hooks that guard the
   workflow, the workflow's scripts, and one folder per orchestrator, which only plugs into four
   task events.

Text lives in `docs/` (ADR 0092); the trees below show only the folders that matter here, with
every file in them. The word after a file says who runs or reads it; click its marker for what it
is and does.

**Who:** `agent` the agent session · `Claude` Claude Code · `hook` Claude Code at a session or
tool event · `bridge` the Farmhand bridge · `T3` the T3 Code orchestrator · `CLI` the `haywire`
command · `git` git itself · `you` a person.

## A project (`haywire init`)

```sh
my-project/
├── .mcp.json                # Claude (1)
├── .claude/
│   └── settings.json        # Claude (2)
├── AGENTS.md                # agent (3)
├── CLAUDE.md                # agent (4)
└── pyproject.toml           # CLI (5)
```

1.  **Adapter** · Starts the Farmhand bridge from the project's environment: `uv run --frozen --quiet haywire farmhand bridge`.
2.  **Adapter** · Allows the bridge's tools (`mcp__farmhand`) and switches the server on. Claude Code honours it once the folder is trusted.
3.  **Pointer** · For every other harness: read `CLAUDE.md`.
4.  **Instructions** · How to work in the project and release it with `haywire share`; names `haywire studio start|stop`.
5.  **Config** · The project's environment: Haywire from PyPI, its own library in `barn/`.

## Core: `going-haywire/haywire`

```sh
haywire-repo/
├── .mcp.json                # Claude (1)
├── .claude/
│   ├── settings.json        # Claude (2)
│   ├── rules/
│   │   └── coding-standards.md # agent (3)
│   └── skills/
│       ├── release/SKILL.md # you (4)
│       ├── verify/SKILL.md  # agent (5)
│       └── check-rename/    # agent (6)
├── dev/
│   ├── README.md            # you (7)
│   ├── hooks/
│   │   ├── session-role.sh  # hook (8)
│   │   ├── session-place.sh # hook (9)
│   │   ├── block-dangerous-git.sh   # hook (10)
│   │   ├── require-workflow-read.sh # hook (11)
│   │   ├── mark-workflow-read.sh    # hook (12)
│   │   └── guard-pr-merge.sh        # hook (13)
│   ├── scripts/
│   │   ├── worktree_setup.py # T3 (14)
│   │   ├── finish.py        # T3 (15)
│   │   └── tasks.py         # agent (16)
│   └── orchestrators/
│       ├── t3/session.sh    # hook (17)
│       ├── t3/doctor.py     # you (18)
│       ├── herdr/session.sh # hook (19)
│       └── herdr/agents.py  # agent (20)
├── docs/
│   ├── agents/start.md      # agent (21)
│   └── collaboration/
│       ├── workflow.md      # bridge (22)
│       ├── contributing.md  # bridge (23)
│       ├── second-machine.md # bridge (24)
│       ├── agent-tooling.md # bridge (25)
│       └── orchestrators/
│           ├── t3-agent.md  # bridge (26)
│           └── herdr-agent.md # bridge (27)
├── packages/haywire-studio/src/haywire_studio/
│   ├── farmhand/bridge.py   # CLI (28)
│   ├── cli/studiocmd.py     # CLI (29)
│   └── agents.py            # CLI (30)
├── pyproject.toml           # bridge (31)
├── t3.json                  # T3 (32)
├── CLAUDE.md                # agent (33)
├── AGENTS.md                # agent (34)
└── CONTRIBUTING.md          # you (35)
```

1.  **Adapter** · Starts the Farmhand bridge from core's own environment.
2.  **Adapter** · Runs every `dev/hooks/*.sh` at its Claude Code event, allows the bridge's tools, formats edited Python with ruff.
3.  **Rule** · Loaded for Python work: points to the coding standards.
4.  **Skill** `release` · Cuts a lockstep release through a release pull request, on the word "publish".
5.  **Skill** `verify` · The full local quality suite, the checks CI runs.
6.  **Skill** `check-rename` · Finds string references an IDE rename missed, with its detector script.
7.  **Doc** · What `dev/` holds and how the libraries reach it.
8.  **Hook** · At session start: the agent's role, maintainer or contributor, from the GitHub login's access.
9.  **Hook** · At session start: joins what each orchestrator slot's `session.sh` prints.
10. **Hook** · Before a shell command: blocks git commands that rewrite or delete remote history or push a tag.
11. **Hook** · Before a shell command: refuses a commit, push or PR change until the session read the workflow page.
12. **Hook** · After a read: records that the session read the workflow page, as a file or through the bridge.
13. **Hook** · Before `gh pr merge`: refuses a draft, a labelled, an unresolved or a red pull request.
14. **Script** · The neutral part of *created*: starts the branch, links core beside a library worktree, `uv sync`, a studio port, the done marker.
15. **Script** · The neutral part of *merged*: frees the worktree and deletes the branch, only once its PR merged.
16. **Script** · The task view: worktrees, their PRs and, where a slot can tell, their sessions.
17. **Hook** · T3's slot: where the agent runs, its how-to, and what the T3 setup still lacks; waits for the worktree setup.
18. **Script** · T3's slot: checks your T3 settings against `t3.json` and adds what is missing.
19. **Hook** · herdr's slot: the agent's address and how to reach the others.
20. **Script** · herdr's slot: lists herdr's live sessions for `tasks.py`.
21. **Instructions** · The one starting point: an agent sets a person up, user or developer, from a machine with only a harness.
22. **Instructions** · The development workflow: branches, PRs, CI, live check, merge, finish, releases, lead and tasks. The gate wants it read.
23. **Instructions** · The rules for everyone who contributes; `CONTRIBUTING.md` points here.
24. **Instructions** · Setting up another machine.
25. **Reference** · This page.
26. **Instructions** · How lead and tasks run in T3 Code.
27. **Instructions** · How lead and tasks run in herdr.
28. **Connection** · `haywire farmhand bridge`: the stdio MCP server between a session and its project's studio; serves the instructions; sends the Farmhand principal's token itself.
29. **CLI** · `haywire studio start|stop|status`: the folder's studio in the background, on a port of its own.
30. **CLI** · The one list of supported harnesses and their adapters, which `haywire init` writes.
31. **Config** · `[tool.haywire.agents] developer-docs = "docs"`: the developer pages the bridge serves here.
32. **Config** · T3's scripts: worktree setup, finish on settle, the studio.
33. **Instructions** · Core's own always-in-context rules for agents (architecture, editing, traps); the process lives in the docs.
34. **Pointer** · For every other harness: read `CLAUDE.md`.
35. **Pointer** · GitHub shows it on a pull request; points to the contributing page and the start page.

## An org library: `going-haywire/haybale-<name>`

Its agent files come from `going-haywire/.github`'s `templates/library/`, through
`scripts/library-files.sh`. It has no tooling of its own: everything runs from core beside it.

```sh
haybale-<name>/
├── .mcp.json                # Claude (1)
├── .claude/
│   └── settings.json        # Claude (2)
├── pyproject.toml           # bridge (3)
├── t3.json                  # T3 (4)
├── .gitignore               # git (5)
└── CLAUDE.md                # agent (6)
```

1.  **Adapter** · Starts the Farmhand bridge from the library's environment.
2.  **Adapter** · Runs core's hooks from `../haywire-repo/dev/hooks/`, checks at session start that core is there, allows the bridge.
3.  **Config** · `[tool.haywire.agents] developer-docs = "../haywire-repo/docs"`: core's developer pages, served here.
4.  **Config** · T3's scripts: the worktree setup through the library's main folder, finish, the studio.
5.  **Config** · Ignores the machine-local `.haywire` files (port, studio pid and log).
6.  **Instructions** · The library's own lines, and where the workflow comes from.

## How each journey receives it

| Journey | Instructions | Hooks | Studio connection | Start a studio |
|---|---|---|---|---|
| A user, any harness | the bridge, from the project | — | the bridge | `uv run haywire studio start` |
| A developer in core | the bridge and `CLAUDE.md` | `.claude/settings.json` | the bridge | `uv run haywire studio start` |
| A developer in an org library or a worktree | the bridge, from core beside it | from core beside it | the bridge | `uv run haywire studio start` |
