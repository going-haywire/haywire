---
serve: developer
status: current
doc_template: reference
scope: Read to find where a file of the development tooling lives, which layer it belongs to and who runs it — repo tooling, agent tooling, orchestration, in a project, core, an org library and going-haywire/.github
see-also:
  - basics.md
  - workflow.md
  - new-org-library.md
  - ../adr/0092-agent-tooling-comes-from-the-place-of-work.md
---

# Development tooling: what lives where

How the whole setup works, for when something is broken or an agent has to look into it.
Setting things up needs none of this page: [setting someone up](../agents/start.md) (a project or a
developer's clones) and [a new organisation library](new-org-library.md) (a library repository) are
the steps.

## Three layers, two workflows

| Layer | What it is | Setting up | Change → PR → merge → release |
|---|---|---|---|
| **① Repo tooling** | GitHub and CI: checks, rulesets, publishing | the CI callers and `dependabot.yml` (from `.github`'s workflow templates); the rulesets and merge settings (`library-settings.sh`) | `ci.yml`, `nightly.yml`, `pr-intake.yml` calling `.github`'s reusable workflows; `publish.yml` |
| **② Agent tooling** | on top of ①: what lets an agent session do the work | the **agent files** a repository commits (written by `haywire init`) | the **Farmhand bridge**, core's `dev/hooks/` and scripts, the workflow page |
| **③ Orchestration** | on top of ②: running the lead and its tasks as sessions | `t3.json`; an orchestrator's setup page and doctor | the orchestrator's slot in `dev/orchestrators/<tool>/`, its agent page |

**Agent files** are the files a repository commits for ② and ③, of three kinds:
**harness configs** (one per agent harness, JSON, read by the harness at session start: `.mcp.json`
starts the bridge, `.claude/settings.json` allows it and wires the hooks), the **orchestrator file**
(`t3.json`), and **declarations** (`[tool.haywire.agents]` in `pyproject.toml`, the `.gitignore`
lines, `CLAUDE.md`). `haywire init` writes a project's; `haywire init --org-files` an org library's.
Nobody installs anything per machine or per folder: every clone and worktree has them through git.

The trees below show only the folders that matter here, with every file in them. The word after a
file says who runs or reads it; click its marker for what it is, its layer and what it does.

**Who:** `agent` the agent session · `Claude` Claude Code · `hook` Claude Code at a session or tool
event · `bridge` the Farmhand bridge · `event` the neutral part of a task event, run by an
orchestrator (T3 through `t3.json`, herdr through its agent page) or by hand · `T3` the T3 Code
orchestrator · `CLI` the `haywire` command · `CI` GitHub Actions · `GitHub` GitHub itself ·
`git` git itself · `you` a person.

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

1.  **② Harness config** · Starts the Farmhand bridge from the project's environment: `uv run --frozen --quiet haywire farmhand bridge`.
2.  **② Harness config** · Allows the bridge's tools (`mcp__farmhand`) and switches the server on. Claude Code honours it once the folder is trusted.
3.  **② Declaration** · For every other harness: read `CLAUDE.md`.
4.  **② Declaration** · How to work in the project and release it with `haywire share`; names `haywire studio start|stop`.
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
├── .github/
│   ├── workflows/           # CI (7)
│   └── ISSUE_TEMPLATE/      # GitHub (8)
├── dev/
│   ├── README.md            # you (9)
│   ├── hooks/
│   │   ├── session-role.sh  # hook (10)
│   │   ├── session-place.sh # hook (11)
│   │   ├── block-dangerous-git.sh   # hook (12)
│   │   ├── require-workflow-read.sh # hook (13)
│   │   ├── mark-workflow-read.sh    # hook (14)
│   │   └── guard-pr-merge.sh        # hook (15)
│   ├── scripts/
│   │   ├── worktree_setup.py # event (16)
│   │   ├── finish.py        # event (17)
│   │   └── tasks.py         # agent (18)
│   └── orchestrators/
│       ├── t3/session.sh    # hook (19)
│       ├── t3/doctor.py     # you (20)
│       ├── herdr/session.sh # hook (21)
│       └── herdr/agents.py  # agent (22)
├── docs/
│   ├── agents/start.md      # agent (23)
│   └── collaboration/
│       ├── workflow.md      # bridge (24)
│       ├── contributing.md  # bridge (25)
│       ├── new-org-library.md # bridge (26)
│       ├── second-machine.md # bridge (27)
│       ├── agent-tooling.md # bridge (28)
│       └── orchestrators/
│           ├── t3-agent.md  # bridge (29)
│           └── herdr-agent.md # bridge (30)
├── packages/haywire-studio/src/haywire_studio/
│   ├── farmhand/bridge.py   # CLI (31)
│   ├── cli/studiocmd.py     # CLI (32)
│   └── agents.py            # CLI (33)
├── pyproject.toml           # bridge (34)
├── t3.json                  # T3 (35)
├── CLAUDE.md                # agent (36)
└── AGENTS.md                # agent (37)
```

1.  **② Harness config** · Starts the Farmhand bridge from core's own environment.
2.  **② Harness config** · Runs every `dev/hooks/*.sh` at its Claude Code event, allows the bridge's tools, formats edited Python with ruff.
3.  **② Rule** · Loaded for Python work: points to the coding standards.
4.  **② Skill** `release` · Cuts a lockstep release through a release pull request, on the word "publish".
5.  **② Skill** `verify` · The full local quality suite, the checks CI runs.
6.  **② Skill** `check-rename` · Finds string references an IDE rename missed, with its detector script.
7.  **① Workflows** · Core's own CI, intake, publishing and docs; core needs no callers of `.github`'s.
8.  **① Issue templates** · Core's own, because the introduction form lives where introductions are filed; every other community file comes from `.github`.
9.  **② Doc** · What `dev/` holds and how the libraries reach it.
10. **② Hook** · At session start: the agent's role, maintainer or contributor, from the GitHub login's access.
11. **③ Hook** · At session start: joins what each orchestrator slot's `session.sh` prints.
12. **② Hook** · Before a shell command: blocks git commands that rewrite or delete remote history or push a tag.
13. **② Hook** · Before a shell command: refuses a commit, push or PR change until the session read the workflow page.
14. **② Hook** · After a read: records that the session read the workflow page, as a file or through the bridge.
15. **② Hook** · Before `gh pr merge`: refuses a draft, a labelled, an unresolved or a red pull request.
16. **② Script** · The neutral part of *created*: starts the branch, links core beside a library worktree, `uv sync`, a studio port, the done marker. Run by T3 on worktree creation, by herdr's lead, or by hand.
17. **② Script** · The neutral part of *merged*: frees the worktree and deletes the branch, only once its PR merged. Run by T3 when a thread settles, or by the task itself.
18. **② Script** · The task view: worktrees, their PRs and, where a slot can tell, their sessions.
19. **③ Hook** · T3's slot: where the agent runs, its how-to, and what the T3 setup still lacks; waits for the worktree setup.
20. **③ Script** · T3's slot: checks your T3 settings against `t3.json` and adds what is missing.
21. **③ Hook** · herdr's slot: the agent's address and how to reach the others.
22. **③ Script** · herdr's slot: lists herdr's live sessions for `tasks.py`.
23. **② Instructions** · The one starting point: an agent sets a person up, user or developer, from a machine with only a harness.
24. **② Instructions** · The development workflow: branches, PRs, CI, live check, merge, finish, releases, lead and tasks. The gate wants it read.
25. **② Instructions** · The rules for everyone who contributes, *In a library* included; `.github`'s `CONTRIBUTING.md` points here.
26. **① ② ③ Instructions** · Setting up a library repository, step by step.
27. **② Instructions** · Setting up another machine.
28. **Reference** · This page.
29. **③ Instructions** · How lead and tasks run in T3 Code.
30. **③ Instructions** · How lead and tasks run in herdr.
31. **② Connection** · `haywire farmhand bridge`: the stdio MCP server between a session and its project's studio; serves the instructions; sends the Farmhand principal's token itself.
32. **② CLI** · `haywire studio start|stop|status`: the folder's studio in the background, on a port of its own.
33. **② CLI** · The agent files: a project's harness configs (`haywire init`), an org library's files (`haywire init --org-files`); the one list of supported harnesses.
34. **② Declaration** · `[tool.haywire.agents] developer-docs = "docs"`: the developer pages the bridge serves here.
35. **③ Orchestrator file** · T3's scripts: worktree setup, finish on settle, the studio.
36. **② Declaration** · Core's own always-in-context rules for agents (architecture, editing, traps); the process lives in the docs.
37. **② Declaration** · For every other harness: read `CLAUDE.md`.

## An org library: `going-haywire/haybale-<name>`

It has no tooling of its own: everything runs from core beside it. Its files are written by
`haywire init --org-files`, the agent files from core and the CI files from `.github`.

```sh
haybale-<name>/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml           # CI (1)
│   │   ├── nightly.yml      # CI (2)
│   │   ├── pr-intake.yml    # CI (3)
│   │   └── publish.yml      # CI (4)
│   └── dependabot.yml       # GitHub (5)
├── .mcp.json                # Claude (6)
├── .claude/
│   └── settings.json        # Claude (7)
├── pyproject.toml           # bridge (8)
├── t3.json                  # T3 (9)
├── .gitignore               # git (10)
└── CLAUDE.md                # agent (11)
```

1.  **① CI caller** · Calls `.github`'s `library-ci.yml`, pinned to a commit, on every pull request and on the default branch. Written once from `.github`'s workflow template, then the library's own.
2.  **① CI caller** · The same checks every night against core's `master` as it is then.
3.  **① CI caller** · Calls `.github`'s `pr-intake.yml`: labels and welcomes pull requests.
4.  **① Workflow** · Generated by `haywire share`: publishes the library on a release tag.
5.  **① Config** · Moves the CI callers' pins to `.github`'s next commit, weekly.
6.  **② Harness config** · Starts the Farmhand bridge from the library's environment.
7.  **② Harness config** · Runs core's hooks from `../haywire-repo/dev/hooks/`, checks at session start that core is there, allows the bridge.
8.  **② Declaration** · `[tool.haywire.agents] developer-docs = "../haywire-repo/docs"`: core's developer pages, served here.
9.  **③ Orchestrator file** · T3's scripts: the worktree setup through the library's main folder, finish, the studio.
10. **② Declaration** · Ignores the machine-local `.haywire` files (port, studio pid and log).
11. **② Declaration** · The library's own lines, and the block naming where the workflow comes from (replaced by every `--org-files` run).

## The organisation: `going-haywire/.github`

What GitHub distributes to every repository, what the libraries call, and what acts on GitHub.
Only the workflow templates take part in a library's files.

```sh
.github/
├── workflow-templates/
│   ├── ci.yml               # CLI (1)
│   ├── nightly.yml          # CLI (2)
│   ├── pr-intake.yml        # CLI (3)
│   ├── *.properties.json    # GitHub (4)
│   └── dependabot.yml       # CLI (5)
├── .github/workflows/
│   ├── library-ci.yml       # CI (6)
│   └── pr-intake.yml        # CI (7)
├── rulesets/library/        # you (8)
├── scripts/library-settings.sh # you (9)
└── CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, .github/ # GitHub (10)
```

1.  **① Template** · A library's CI caller, with `$default-branch` and `@main`; `haywire init --org-files` fills in the branch and pins the commit.
2.  **① Template** · The nightly caller.
3.  **① Template** · The intake caller.
4.  **① Template metadata** · Makes GitHub offer the callers under *Actions → New workflow*.
5.  **① Template** · A library's `dependabot.yml` (no metadata: GitHub does not offer it, the command copies it).
6.  **① Reusable workflow** · A library's lint and tests against core's `master`.
7.  **① Reusable workflow** · The intake: labels from a pull request's metadata, never its code.
8.  **① Rulesets** · *Permanent refs*, *Release tags*, *PR gate*.
9.  **① Script** · Applies the rulesets, merge settings and labels to one library repository (an admin, once).
10. **① Community files** · GitHub shows them in every repository that has none of its own: the contributing pointer, the security policy, the code of conduct, the PR template, the libraries' issue templates.

## How each journey receives it

| Journey | Instructions | Hooks | Studio connection | Start a studio |
|---|---|---|---|---|
| A user, any harness | the bridge, from the project | — | the bridge | `uv run haywire studio start` |
| A developer in core | the bridge and `CLAUDE.md` | `.claude/settings.json` | the bridge | `uv run haywire studio start` |
| A developer in an org library or a worktree | the bridge, from core beside it | from core beside it | the bridge | `uv run haywire studio start` |
