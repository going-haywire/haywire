# Agent tooling: goals before mechanisms

Issue: [#203](https://github.com/going-haywire/haywire/issues/203) (one marketplace for every
Haywire plugin, and how library worktrees get haywire-dev). Design session 2026-11-22.

A first round answered #203 question by question and produced 21 decisions that each worked
around the current setup. The result was a tangle of repositories, workflows and harness
support that only an agent could follow. The round was set aside; its findings are kept below
as **building blocks**, not decisions. This plan states what must be true, for whom, with no
mechanism in it. The "how" round comes next and checks every building block against G1–G7.

## Problem

The agent tooling (skills, hooks, the Farmhand connection, scripts), the repositories that hold
it, the development workflow and the support for agent harnesses are intertwined, so that nobody
but an agent can follow how they fit together. A visible symptom: a worktree of an org library
gets neither the workflow skill nor its guardrails (#203).

## Audiences

| Audience | Who | Notes |
|---|---|---|
| **Haywire user** | tries Haywire, works in their own project, builds their own libraries | beginner and advanced differ in degree, not in setup |
| **Haywire developer** | changes core or an org library, as a contributor (fork) or maintainer (write access) | contributor and maintainer differ by permission, not by journey; a developer gets everything a user has |

## Goals

| Goal | User | Developer |
|---|---|---|
| **G1** From nothing to working, through the agent, from **one starting point** that first asks "use Haywire or develop it?" and branches. It assumes only a working agent harness; whatever only the person can do (admin installs, logins, passwords) the agent hands over as one exact step and then checks. | ✓ | ✓ |
| **G2** Any agent harness, Claude first. Every harness gets a **floor**: the instructions (how to work, the workflow) and the studio connection. Guardrails come where a harness can enforce them. The hard guarantees (protected branches, tags, merge rules) live on GitHub, so a harness without hooks is less convenient, never unsafe. | ✓ | ✓ |
| **G3** Every place of work (a project, a clone, a worktree) has what its session needs, with **no setup per folder**, in the version that **matches that place's Haywire**: what the agent is told always matches the code it works with. | ✓ | ✓ |
| **G4** Guardrails apply in every clone and worktree of an **org repository, including forks of one**, and nowhere else. The repository decides, not the person or the machine. | — | ✓ |
| **G5** One home per piece, and its name tells where. A piece **lives with what it describes**: product tooling with the product's code, the development process with its rules, a library's quirks in that library. Nothing is copied. | ✓ | ✓ |
| **G6** The whole thing can be explained from a single picture. | ✓ | ✓ |
| **G7** Orchestrators (T3 Code, herdr, none) are **optional add-ons**: the agent tooling and the guardrails behave the same with any orchestrator or none, and supporting a new one changes neither. | — | ✓ |

## Not in scope

- **N1** Installing or configuring the agent harness itself.
- **N2** Moving guarantees to the client: anything safety-relevant stays on GitHub.
- **N3** Changing the studio's security model: a connection uses the roster as it is.
- **N4** Breaking the simple path (ADR 0086): using Haywire needs neither a harness nor the tooling.
- **N5** Building orchestrator-specific tooling beyond what G7 allows.

## Decisions of this round

| # | Question | Answer |
|---|---|---|
| 1 | Audiences | Two: users and developers |
| 2 | Starting points | One, branching by audience |
| 3 | Where guardrails apply | Org repositories and their forks, nowhere else |
| 4 | Tooling version per place | Matches that place's Haywire |
| 5 | What every harness gets | A floor, guardrails where enforceable, guarantees on GitHub |
| 6 | What decides a piece's home | It lives with what it describes; nothing is copied |
| 7 | What the starting point assumes | A working harness, nothing else |
| 8 | Scope boundary | N1–N5 |

## Decisions of the "how" round

| # | Question | Answer |
|---|---|---|
| H1 | Where a place of work gets its tooling | From the place itself: its committed files (a thin adapter per harness) plus its own Haywire environment. Core's in-place model, generalised. Claude plugins and marketplaces become optional |
| H2 | Where developer tooling lives | As files in core's `dev/` (no package ships it); org repos' adapters call it by path (`./dev/…` in core, `../haywire-repo/dev/…` in libraries and worktrees) |
| H3 | What connects a session to its studio | `haywire farmhand bridge`: a stdio MCP bridge in haywire-studio, started from the place's environment by the committed MCP config. Always up, finds its own project's studio, fetches the token in-process, re-announces tools mid-session. Replaces the npm proxy |
| H4 | How a session gets the product instructions | Through the bridge: a short index as MCP server instructions, details as resources, all from the installed version |
| H5 | Developer instructions and guardrails in org repos | Instructions through the bridge, declared by the repo in a committed neutral file (e.g. `.haywire/agents.toml`); the bridge serves what a folder declares and knows nothing about the org. Guardrails: a committed adapter per harness (Claude: `.claude/settings.json` hooks calling `…/dev/hooks/*.sh`). The workflow gate checks that the developer instructions were read |
| H6 | The one starting point | A sentence the person gives their agent ("Set me up for Haywire: read `<docs>/agents/start.md` and follow it"), in core's README and the docs. The page, always at the latest release, guides prerequisites (handing over what only a person can do), asks "use or develop?", then `haywire init` for users or the sibling-layout clones and `uv sync` for developers |
| H7 | Orchestrator support | One folder per orchestrator, `dev/orchestrators/<tool>/`, holding its slot scripts, the agent's how-to, a person's setup and its doctor. The only link is the contract the neutral side defines (ADR 0090's four task events, plus "a slot may add session context"); neutral parts name no tool; a root file (`t3.json`) only calls neutral scripts |
| H8 | Plugins, marketplaces, the npm proxy | All go: claude-plugin archived (README pointing to the start page); npm `@going-haywire/farmhand-proxy` deprecated, pointing to the bridge; both Claude marketplaces removed; `plugins/haywire-dev/` becomes `dev/` without a plugin manifest; `haywire-live-studio`, both `studioctl`s, the six doc loaders, `haywire-benchmark` and `trim-docs` deleted |
| H9 | Which adapters a repository commits | One for every harness Haywire supports, always; the list lives once in core; `haywire init --refresh-adapters` (users) and the template script (org repos, #153) add a newly supported harness's adapter |
| H10 | How a library worktree finds core | The neutral worktree setup (the "created" event, run by the orchestrator, e.g. T3's `runOnWorktreeCreate`) finds core through the library's main folder (`git rev-parse --git-common-dir`), links it beside the worktree as `haywire-repo`, then runs `uv sync`. Every org repo's orchestrator file calls the setup through the main folder. Unverified: T3's worktree folder per repository, and `uv sync` through a symlinked core |

### Documentation

| # | Question | Answer |
|---|---|---|
| D1 | What the docs are for | Two kinds: **instructions** (how to do it, for the agent) and **reference** (why, and how it fits, for people and agents) |
| D2 | Where text lives | **All text lives in `docs/`**, both kinds, both audiences; the kind is a front-matter marker (e.g. `serve: product \| developer`), not a place. Code folders hold only code (`dev/` hooks and scripts, `dev/orchestrators/<tool>/` slot scripts, the bridge in the package); an orchestrator's text lives in `docs/collaboration/orchestrators/<tool>/`. Every other markdown file (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `.github/CONTRIBUTING.md`, READMEs of `dev/` and `scripts/`, a library's `CLAUDE.md`) is a pointer of a few lines with no rules of its own. The bridge builds its index from the markers: product pages from the wheel (`bake_docs.py` already bakes all of `docs/`), developer pages from the path the repository declares. `mkdocs build --strict` guards links inside `docs/`; a test guards the pointers' links into it |

| D3 | When the docs work happens | In the slice that changes the subject (the project's rule: the doc changes in the same change), plus a final audit in S6: no page names what is gone, no rule appears twice, every markdown file outside `docs/` is a pointer |

D2 refines H4, H5 and H7: the instructions the bridge serves are `docs/` pages, and an
orchestrator's folder keeps its scripts while its text moves to `docs/`.

**Where today's text goes:**

| Today | Goes to |
|---|---|
| `haywire-workflow/SKILL.md`, `.insights/project_pr_workflow.md` | `docs/collaboration/` instruction pages by topic (branch and PR, CI, merge and finish, live check, releasing, in a library), `serve: developer` |
| `second-machine.md`, `docs/collaboration/workstation.md` | the start page (developer branch) and a setup instruction page |
| `haywire-workflow/orchestrators/<tool>.md`, `docs/collaboration/orchestrators/<tool>.md` | `docs/collaboration/orchestrators/<tool>/` (the agent's how-to and a person's setup) |
| `docs/collaboration/orchestrators/index.md` | stays: the contract |
| `haywire-live-studio` | dissolved (H8): CLI help, tool descriptions, the live-check page |
| `docs/collaboration/basics.md`, `index.md`, the 12 journey pages | reference, rewritten around the picture; journey pages keep diagram and decisions and link to instruction pages, restating none |
| `CONTRIBUTING.md`, `.github/CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`, `plugins/haywire-dev/README.md`, `scripts/README.md` | pointers |
| new: product instructions | `docs/` pages marked `serve: product`, the bridge's index built from them |

A **place of work** is any folder an agent session works in: a user's project, a clone of core or
an org library, or a worktree of either. The adapters are committed in the repository, so every
clone and worktree of it carries them.

### Experiment first (before any build)

H4 and H5 rest on one assumption: an agent follows instructions served by an MCP server as
reliably as a loaded skill. Test it before building anything:

1. A throwaway stdio MCP server (Python SDK) with server instructions ("before any `git commit`,
   read the resource `haywire://dev/workflow`") and that one resource, holding a rule the agent
   cannot guess (e.g. a required commit-message trailer).
2. A scratch git repository whose committed `.mcp.json` starts it; no skills, no `CLAUDE.md` rule.
3. Ten headless sessions (`claude -p`) with tasks that end in a commit, some with the instruction
   early in the task, some buried after unrelated work.
4. Measure: was the resource read before the commit, and does the commit carry the trailer.
   Compare with the same rule delivered as a skill.

If MCP delivery falls clearly short, H4/H5 fall back to native skills reached by committed links
(round two's option B) for Claude, keeping the bridge for every other harness.

**Result (2026-11-22, Claude Code 2.1.311, default model, 5 tasks × 2 repetitions per arm):**

| | MCP (instructions + resource) | Skill |
|---|---|---|
| Rule read before the commit | 10/10 | 10/10 |
| Trailer present | 10/10 | 10/10 |
| Trailer exactly as specified ("after a blank line") | 3/10 | 10/10 |
| Mean turns / seconds | 5.3 / 15.9 | 4.9 / 12.1 |

The trigger holds: server instructions made every session read the resource before committing.
Detail fidelity is lower: seven MCP sessions merged the trailer into the `Co-Authored-By` block.
Consequence for the build: rules served as resources are written unambiguously, and whatever
matters is checked by a guard, never left to prose. Untested: long sessions, several competing
resources, harnesses other than Claude. H4 and H5 stand.

## Building blocks from round one

Candidates for the "how" round, each to be kept only if it serves a goal.

**Facts found (true today):**

- haywire-dev is installed per folder (`--scope project`), so a library worktree has none; on the
  maintainer's machine it is installed for one folder only.
- Core runs haywire-dev's files in place (hooks from `.claude/settings.json`, the skill and
  `finish.py`/`tasks.py` by symlink). 10 of the 11 commits touching `plugins/haywire-dev/` between
  2026-11-18 and 2026-11-22 also changed core docs or scripts.
- Two Claude marketplaces exist: `going-haywire` (`.github`, haywire-dev) and `haywire-marketplace`
  (claude-plugin, the `haywire` plugin). A plugin ID is `<plugin>@<marketplace>`.
- **The Farmhand proxy's discovery has been dead since ADR 0028**: it finds `studio.json` only next
  to the deleted `.haywire/farmhand_token`, so it always falls back to port 8124. In a worktree it
  reaches nothing, or the main folder's studio. Published npm 0.1.4 has the same code.
- Developers get the proxy only through the beginner `haywire` plugin; core's settings name a
  `farmhand` `.mcp.json` server that does not exist.
- A library worktree can run its own studio (`uv run haywire` there loads the branch), but gets no
  port of its own: `worktree_setup.py` is core's.
- Two `studioctl` implementations exist (Python in core's `haywire-live-studio`, TypeScript in
  claude-plugin); libraries have neither.
- `haywire-live-studio` names a non-existent `.mcp.json` and the wrong npm package.
- Agent principals live in `~/.haywire/security.json`, can be scoped to one exact workspace path,
  and are read live by a running studio. Authentication is off by default.
- In 198 sessions (2026-10-25 to 2026-11-22) the six doc-loader skills (`haywire-nodes`, `-libs`,
  `-settings`, `-themes`, `-ui`, `-exec`) and `haywire-benchmark` were never used; `trim-docs` is
  an empty folder.
- `haywire init` writes `CLAUDE.md` and an `AGENTS.md` that points to it, and detects no harness.

**Mechanisms proposed (not decided):**

- The proxy reads `studio.json` directly (one folder down, the live pid) and fetches the token
  itself through a read-only `haywire farmhand token --principal farmhand`, so it never reaches
  the model; the user creates the **Farmhand principal** once per machine and chooses its tier.
- `haywire studio start|stop|status` in the product CLI replaces both `studioctl`s and assigns
  worktree ports.
- `haywire agents`: detects harnesses and installs or connects the tooling per harness; runnable
  with `uvx` before anything is cloned.
- A `setup` skill with a `setup.py --check|--fix|--hook` for the developer side.
- One Claude marketplace for every plugin; skill names without the `haywire-` prefix (a plugin
  skill shows as `<plugin>:<skill>`); the beginner repository renamed after the glossary's
  **Farmhand**.
- The `haywire-live-studio` skill dissolved: lifecycle into the CLI's help, Questionnaire traps
  into the tools' descriptions, live-check steps into the workflow skill.
- The doc-loader skills, `haywire-benchmark` and `trim-docs` deleted.

## Candidate glossary terms

Written into `docs/reference/glossary.md` in the change that builds them
([doc-authoring.md](../../docs/reference/doc-authoring.md), *Style*):

- **Claude marketplace**: a catalog Claude Code installs Claude plugins from; a plugin's ID is
  `<plugin>@<marketplace>`. Avoid: bare "marketplace" (that is the haybale Marketplace).
- **Claude plugin**: a bundle of skills, hooks or MCP servers that Claude Code installs from a
  Claude marketplace. Avoid: bare "plugin" (a haybale library is also called one).
- The two plugins by their names (`haywire`, `haywire-dev`) instead of today's "Claude plugin"
  entry, which names only one of them; the Farmhand intro's "Farmhand plugin" likewise.
- **Farmhand principal**, if the proxy-fetched token survives the "how" round.
- **Haywire user** and **Haywire developer**, the two audiences above.
- **Place of work**: any folder an agent session works in (a project, a clone, a worktree).
- **Bridge** (`haywire farmhand bridge`), replacing **Farmhand proxy**.
- **Adapter**: the thin, committed per-harness files of a repository that connect a harness to the
  place's own tooling.
- A flagged ambiguity: "plugin" and "marketplace" in Claude Code always qualified.

## The picture (G6)

1. One sentence brings any agent to the start page, which sets up a repository.
2. Every repository carries thin adapters for every harness, pointing at the place's own Haywire:
   the bridge gives instructions and the studio's tools, in the matching version.
3. Org repositories also point at core's `dev/` (guardrails and developer instructions); an
   orchestrator only plugs into four events there.

## Status

| Slice | State | Pull requests |
|---|---|---|
| S1 Bridge | done 2026-11-22, live-checked (auth on, token never in a transcript) | #216, fix #220 |
| S2 `haywire studio` | done 2026-11-22, live-checked | #217, fix #220 |
| S3 Core `dev/` | done 2026-11-22, live-checked (gate blocks, bridge serves the page) | #218, going-haywire/.github#5 |
| S4 Libraries | done 2026-11-23, live-checked on a T3-style spandrel worktree | #219, going-haywire/.github#6, haybale-comfyui#10, haybale-protokol#22, haybale-spandrel#7, haybale-stream#18, haybale-visiongraph#9 |
| S5 Start page | done 2026-11-23, live-checked (the user journey) | #222 |
| S6 Cleanup | done when #223, going-haywire/.github#7 and going-haywire/claude-plugin#2 merge, claude-plugin is archived and the npm package deprecated | #223, going-haywire/.github#7, going-haywire/claude-plugin#2 |

Deviations from the plan: the developer-docs declaration is `[tool.haywire.agents]` in
`pyproject.toml` (`.haywire/` is gitignored); the worktree setup keeps the per-worktree port
(the umbrella's studio and `t3.json` read it) and marks "done" in the worktree's git folder;
`haywire init --refresh-adapters` was dropped (no projects predate it); core's `CLAUDE.md` keeps
core's own always-in-context rules as the one exception to D2. Found on the way and fixed: the
studio's `started_at` made every running studio look recycled (#216); the studio's startup line
and `user add` printed agent tokens (#216); a stale local docs bake hid the bridge's index and
`free_port` took bound ports (#220).

## Build plan

Each slice ships on its own; the next builds on it. Slice 1 first: it fixes the connection that
is broken today.

Docs per slice (D3): S1 the `serve: product` index pages and the bridge reading the markers;
S2 `haywire-live-studio` dissolved; S3 the workflow as `docs/collaboration/` instruction pages,
`CLAUDE.md`, `AGENTS.md` and the READMEs as pointers, the pointer-link test, the picture page;
S4 the library pointers and `.github/CONTRIBUTING.md`; S5 the start page and `CONTRIBUTING.md`
as a pointer; S6 the audit.

| Slice | What | Done when |
|---|---|---|
| **S1 Bridge** ([#209](https://github.com/going-haywire/haywire/issues/209)) | `haywire farmhand bridge`: stdio MCP server in haywire-studio. Finds its own project's `studio.json` (live pid), connects when the studio comes up and drops when it stops, re-announces tools and resources, fetches the Farmhand principal's token in-process. Its server instructions carry the product index; its resources serve the baked docs. Fallback tools: status, and connect to an explicit port. Core gets the adapter (`.mcp.json`, Claude permission rule). | A core worktree session starts the studio mid-session and its tools appear; with auth on, no token reaches the model or the user |
| **S2 `haywire studio`** ([#210](https://github.com/going-haywire/haywire/issues/210)) | `start\|stop\|status`: detached start in this folder, a port of its own for a worktree, stops only its own studio, reports who holds the port. Worktree ports move out of `worktree_setup.py`. `haywire-live-studio` and core's `studioctl` are dissolved (lifecycle → CLI help, Questionnaire traps → tool descriptions, live-check steps → the workflow instructions). | A live check in a core worktree runs on `haywire studio` and the bridge alone |
| **S3 Core `dev/`** ([#211](https://github.com/going-haywire/haywire/issues/211)) | `plugins/haywire-dev/` becomes `dev/`: hooks, the workflow as instructions served by the bridge (declared in core's `.haywire/agents.toml`), `finish`, `tasks`, `dev/orchestrators/<tool>/` holding each orchestrator's slot, how-to, setup and doctor. The workflow gate checks that the developer instructions were read. Core's adapters for every supported harness (H9). The picture page: one tree per repository with click-open annotations (kind and function per file). | A core session gets product and developer instructions through the bridge; the guardrails hold; `dev/orchestrators/t3` removed leaves everything else working |
| **S4 Libraries** ([#212](https://github.com/going-haywire/haywire/issues/212)) | `dev/worktree_setup.py` (the "created" event): links core beside the worktree, `uv sync`. The library template (#153) with every adapter, `.haywire/agents.toml` and `t3.json`; a refresh PR in each of the five libraries. | A T3-created worktree of a library has instructions, guardrails, the bridge and a running studio without a manual step |
| **S5 Start page** ([#213](https://github.com/going-haywire/haywire/issues/213)) | `agents/start.md` on the docs site; the sentence in core's README; `haywire init` writes every supported harness's adapter, `--refresh-adapters` adds new ones. | A fresh machine with only a harness reaches a running studio (user) or a working library worktree (developer) from the sentence |
| **S6 Cleanup** ([#214](https://github.com/going-haywire/haywire/issues/214)) | claude-plugin archived with a pointer to the start page; npm `@going-haywire/farmhand-proxy` deprecated with a pointer to the bridge; both Claude marketplaces removed; the six doc loaders, `haywire-benchmark` and `trim-docs` deleted; skill renames; ADRs. | Nothing on GitHub, npm or in the docs names a plugin, marketplace or proxy as the way in |

**To verify during the build:**

- T3 places a library's worktrees under `~/.t3/worktrees/<repo>/` (S4).
- `uv sync` accepts a symlinked core as an editable source (S4).
- `list_changed` support and the MCP config location per harness beyond Claude (S1, S5).
- A signal the workflow gate can read for "developer instructions were read" (S3).

**ADRs to draft** (each reverses or amends an accepted decision):

- Agent tooling comes from the place of work, not from installed plugins: supersedes ADR 0086's
  "an org development plugin" and the marketplace part of D2 in the workflow review.
- The bridge replaces the Farmhand proxy: amends ADR 0028's note that the proxy must change.
- One folder per orchestrator: amends ADR 0090's slot layout (the agent's how-to leaves the
  workflow skill).
