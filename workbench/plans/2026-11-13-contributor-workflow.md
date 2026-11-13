# Contributor workflow: design and slices

Settled in an inquisition on 2026-11-13 (questions Q1–Q27 below). Each slice's last task
marks its row in *Status* done, with commit, date and deviations.

## Problem

The repository assumes one person, the maintainer, working with agents. An outside
developer (who will also use agents) meets maintainer-only rules, instructions that are
duplicated and already contradict each other (`development.md` runs `uv run mypy .`, CI
runs mypy on a path list), personal tooling presented as required, and no written
process. Their agent cannot tell it is on a fork. Fork PRs bring prompt-injection and
code-execution risks the current setup does not address.

## Principles

1. **One home per piece of information.** Every rule, command, procedure and fact lives in
   exactly one file; every other file links to it.
2. **Welcoming.** Assume good intentions. Process steps never show a contributor a red ✗.
3. **Untrusted input is read without power.** What reads untrusted content can do nothing
   harmful; what can act never reads it raw.

## Decisions

| # | Area | Decision |
|---|---|---|
| 1A | Roles | Two roles now: maintainer and contributor, decided by write access to `going-haywire/haywire`. Designed so a collaborator role (write access, no merge or release) can be added later. |
| 2A | Where rules live | `CONTRIBUTING.md` (repo root) holds the process rules; the `haywire-workflow` skill holds only agent steps and links to it. |
| 3A | One owner per kind of information | `CONTRIBUTING.md`: process rules. `docs/guides/development.md`: setup and the only command list. `tests/README.md`: test tiers and traps. `CLAUDE.md` (AGENTS.md points to it): agent-only content plus links. Skill: agent steps for both roles. |
| 4A | Role detection | A `SessionStart` hook runs `gh repo view going-haywire/haywire --json viewerPermission`; ADMIN/MAINTAIN/WRITE → maintainer, else contributor. Without `gh`, login or network: contributor. |
| 5A | Backlog | GitHub issues are the backlog (`good first issue`, `help wanted`). `open_issues.md` and `internals/issues/` move there. Plans stay as files, linked from their issue. |
| 6A | Issue first | Small fixes (clear bug, docs, typo, tests) may go straight to a PR; anything else needs an agreed issue first. Claim an issue by commenting. |
| 7A | Contributor's agent | Commits and pushes to the fork freely. Opens, readies or comments on anything upstream only on the person's word. Opens the PR when it is worth a review. Runs the checks from `development.md` locally first (CI does not run on fork branches). |
| 8A | Introduction | Before a first PR, a contributor writes (personally, not an AI) an introduction issue: who, what, why. The maintainer answers and sets `introduction accepted`. Then 6A applies. |
| 9D | Enforcing the introduction | The contributor's agent checks for an accepted introduction before offering a PR; a workflow checks every PR from a non-collaborator. |
| 10B | PR without an accepted introduction | A welcome comment and the label `needs introduction`; checks stay green; the PR stays open; the label is removed automatically on acceptance. The merge guard refuses while the label is set. |
| 11A | Reviewing a fork PR | A script (not an agent) fetches diff, description, comments, commit messages and CI results, makes hidden content visible (HTML comments, invisible Unicode, bidi controls) and flags agent and CI files. A dedicated reviewer agent with read-only tools (no Bash, no Write/Edit, no MCP, no web) reads that file and the trusted `master`, and returns a report with a section for content that reads like instructions. Only the main session posts, labels or merges, on the maintainer's word. Detailed design deferred (handoff H1). |
| 12B | PRs touching agent or CI files | `CLAUDE.md`, `AGENTS.md`, `.claude/**`, `.github/**` (and any successor of them) get the label `agent files` and a friendly comment; the maintainer reads them line by line and removes the label; the merge guard refuses while it is set. |
| 13A | Rules in private memory | Repo-wide rules move to their one home: design principles to an architecture doc or `docs/reference/design-principles.md` (linked from CLAUDE.md), the test rule to `tests/README.md`, glossary/ADR timing to `doc-authoring.md`, one-home-per-instruction to `CONTRIBUTING.md`. The maintainer's memory keeps only personal preferences. |
| 14A | Root clutter | Item by item from a table the maintainer signs off: delete `.context_dump`, `.windsurf`, `open_issues.md` (after 5A), `profile_report.json`, `skills-lock.json`; untrack `.scratch`; repoint every reference in the same PR. |
| 15A | Docs vs. working material | `docs/` holds only published docs. Working material moves to `workbench/plans/` (plans, designs, handoffs; dated) and `workbench/playground/` (experiments). `CLAUDE.md` states the plan location once, overriding any skill default; the maintainer's personal `writing-plans` skill uses the same path. `internals/`, `docs/superpowers/` and the working notes in the `docs/` root move; the `exclude_docs` entry in `mkdocs.yml` goes. |
| 16A | Tools | `CONTRIBUTING.md` lists required tools (`uv`, `git`, `gh` logged in, `jq`) and optional ones with one line each (herdr, farmhand, CodeGraph, the sibling repos). Sandcastle is removed. The hooks warn once when `jq` or `gh` is missing instead of failing open. |
| 17A | Running all libraries together | A personal umbrella environment in the parent folder (outside every repo): a `pyproject.toml` with every package of every repo as an editable path source; one `uv sync` there runs the full studio. Each repo keeps its own environment for its tests and CI. The `barn/` symlinks, workspace excludes, gitignore lines and sibling linking in `worktree_setup.py` go. Editing via a VS Code multi-root workspace. Spike first (slice 0). |
| 18A | Test results on fork PRs | `ci.yml` only uploads reports and the event file; a `workflow_run` workflow from `master` publishes the comment and check. |
| 19A | PR template | Short: what and why with `Fixes #n` (or "small fix" and why); checklist (introduction accepted or maintainer, checks pass, docs updated, no version changes); AI assistance (none / partly / mostly, tool); what to look at first. Each item links to its rule. The skill's PR body uses the same headings. |
| 20A | Standard files | `SECURITY.md` (GitHub private vulnerability reporting, switched on; supported versions) and `CODE_OF_CONDUCT.md` (Contributor Covenant) now; `CODEOWNERS` with the collaborator role. |
| 21A | Conduct contact | A dedicated address the maintainer provides; placeholder until then. |
| 22A | Contribution terms | MIT in = MIT out, one line in `CONTRIBUTING.md`; no DCO, no CLA. |
| 23A | Labels | `introduction` (set by its issue form), `introduction accepted` (maintainer), `needs introduction` (workflow), `agent files` (workflow; maintainer removes). |
| 24A | Issue forms | Introduction, bug report, idea/feature; `config.yml` links to private security reporting and the docs; blank issues stay allowed. |
| 25A | Trying a fork PR live | Only after the review judged it safe: check it out into its own worktree (`git worktree add ../review-pr-<n>`, `gh pr checkout <n>`), `uv sync` there, run by hand or from an agent session started in the main folder, never inside the review worktree; remove the worktree, then merge. Doubtful PRs: GitHub Codespaces or not at all. |
| 26A | Actions pinning | Every third-party Action pinned to a full commit hash with the version as a comment; Dependabot proposes updates. |
| 27B | Delivery | Slices below; 3 and 4 may run in parallel worktrees. |

### The rule for workflows with rights

A workflow that has write rights or secrets never checks out, installs or runs code from an
unmerged PR.

| Trigger | Workflow file from | Rights | PR code | Ours |
|---|---|---|---|---|
| `pull_request` from a fork | the PR | read-only, no secrets | fine | `ci.yml` |
| `pull_request_target` | `master` | write | never; metadata through the API only; no shared caches | labeller (9D, 10B, 12B) |
| `workflow_run` | `master` | write | never; uploaded reports are data | test-results publisher (18A) |
| `push` to `master`, tags | `master` | write, publishing | fine: already merged | `ci.yml`, `docs.yml`, `publish.yml` |

Locally the maintainer always holds write rights; there 25A applies: the review is the gate.

## Out of scope

A collaborator role now; `CODEOWNERS`; DCO or CLA; an AI reviewer running on GitHub;
closing PRs automatically or red checks for process steps; refusing PRs that touch agent
files; merging the external libraries into this repo; building the reviewer agent, moving
the backlog, or a devcontainer now (handoffs H1–H3).

## Slices

| # | Slice | Decisions | Needs |
|---|---|---|---|
| 0 | **Spike** (personal, outside the repo): the umbrella environment; answers S1–S5 below | 17A, 25A | – |
| 1 | **Repo hygiene**: `workbench/`; clutter table signed off and applied; Sandcastle removed; sibling-link plumbing removed (if slice 0 succeeded); `exclude_docs` removed | 14A, 15A, 16A, 17A | 0 |
| 2 | **Single-home docs**: `CONTRIBUTING.md`; `development.md` as the only command list (mypy corrected); `CLAUDE.md` slimmed to agent-only content plus links; memory rules moved; `SECURITY.md`; code of conduct with contact placeholder; PR template; issue forms; labels created; private vulnerability reporting switched on | 2A, 3A, 5A, 6A, 8A, 13A, 16A, 19A–24A | 1 |
| 3 | **Agent side**: role hook; skill rewritten as shared steps plus contributor and maintainer endings; introduction check in the skill; hooks warn on missing `jq`/`gh`; merge guard also refuses on `needs introduction` and `agent files` | 4A, 7A, 9D, 10B, 12B, 16A | 2 |
| 4 | **CI**: `workflow_run` publisher; introduction and agent-file labeller on `pull_request_target` without checkout; all Actions pinned; Dependabot | 9D, 10B, 12B, 18A, 26A | 2 |

### Spike questions

- S1. `uv sync` in the umbrella never changes a repo's own environment.
- S2. How `haywire docs --all` finds libraries that are not under `barn/`.
- S3. Hot-reload works on editable installs from another folder.
- S4. Whether a session started in the main folder loads `CLAUDE.md` files from additional
  directories (decides 25A's "agent session started in the main folder").
- S5. Whether the `report` job fails or only warns on a fork PR (decides how urgent 18A is).
- S6. Which folder the VS Code extension starts a session in for a multi-root workspace.
- S7. Running the full studio against a worktree's code.

### Spike results (2026-11-13)

A trial umbrella (18 packages as editable path sources, Python pinned to 3.12.12) synced in
1:36 min from the uv cache.

| | Result |
|---|---|
| S1 | **Holds.** After the umbrella sync, the environments of haywire-repo, spandrel, stream, visiongraph and protokol were unchanged (package lists compared before and after). |
| S2 | **No change needed.** `generate_all_docs` keeps libraries whose resolved module folder lies under the repo root, so sibling libraries were never included, symlinks or not; each sibling generates its docs in its own repo. |
| S3 | **Holds.** The studio started from the umbrella watched the real sibling folders; rewriting `haybale_spandrel/nodes/inpaint.py` unchanged reloaded and re-registered `InpaintNode`. A bare `touch` (metadata only) triggers nothing on macOS; an editor save does. |
| S4 | **Holds by default.** Claude Code loads `CLAUDE.md` and rules from additional directories only when `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` is set; settings and hooks come only from the session's starting folder. 25A therefore requires that variable unset. |
| S5 | **Open.** Needs a real fork PR; verified in slice 4 with a test fork. |
| S6 | **Dropped.** The maintainer moves to herdr, whose sessions start in a terminal folder. |
| S7 | **Holds.** `uv run --with-editable <worktree>/packages/haywire-core --with-editable <worktree>/barn/haybale-core …` from the umbrella imports the overlaid packages from the worktree and the rest from the main checkouts, leaves the umbrella unchanged, and `entry_points()` yields 16 libraries with no duplicate (the overlay's copy wins). Code listing all distributions sees an overlaid package twice. |

Found on the way:

- uv applies a sibling repo's workspace `[tool.uv.sources]` to that repo's library, so a
  sibling's dev `pyproject.toml` leaks into the umbrella. `haywire init --dev` writes those
  sources as absolute paths (`packages/haywire-studio/src/haywire_studio/init.py`, the
  `dev_repo` sources), so they work on one machine only; `haybale-comfyui`'s still point to
  the Linux machine and break the umbrella there.
- The umbrella needs the repos' Python pin (`.python-version` 3.12.12): visiongraph's
  `mediapipe-numpy2` has no wheel for 3.13.
- A studio started from the umbrella listens on the usual port, where the farmhand plugin
  then connects with a token the umbrella project does not know.

## Facts to write down, each in its one home

- CI for a fork PR runs upstream, with the PR's workflow files, a read-only token, no
  secrets, and the maintainer's approval for first-time contributors → `CONTRIBUTING.md`.
- Never start an agent session in a checkout of a fork PR → `CONTRIBUTING.md` (maintainer
  part) and the skill's maintainer ending links to it.
- The mypy invocation is the path list of CI's `types` job → `development.md`.

## Terms

Defined in `CONTRIBUTING.md` (process vocabulary, not Haywire domain terms), added with
slice 2: maintainer, contributor, collaborator (future), introduction issue, accepted
introduction, agent files, review worktree, umbrella environment, workbench.

## ADR candidates

1. The introduction gate for first contributions (8A, 9D, 10B).
2. Handling untrusted PRs: the read-only reviewer, publishing through `workflow_run`, and
   the rule for workflows with rights (11A, 18A, the table above).
3. The umbrella environment instead of symlinks or a monorepo (17A).

## Inputs owed by the maintainer

- The conduct contact address (21A).
- Sign-off of the clutter table (14A), produced at the start of slice 1.

## Handoffs (not built now)

- H1. The reviewer agent (11A): its tool list, the fetch script, the report format.
- H2. Moving the existing backlog to GitHub issues (5A): `open_issues.md`,
  `internals/issues/`, `.scratch` notes, open items in the maintainer's memory.
- H3. `devcontainer.json` for Codespaces and contributor setup (25A).
- H4. Today's macOS flake (`test_root_ghost_pins_leave_the_card_body[chromium-set-t2b]`,
  run 43417492321) as a comment on issue #47.

## Status

| # | Slice | State | Commit | Date | Deviations |
|---|---|---|---|---|---|
| 0 | Spike | done | | 2026-11-13 | S5 moved to slice 4; S6 dropped; S7 added |
| 1 | Repo hygiene | done | | 2026-11-13 | `.scratch` measuring tools kept in `workbench/playground/perf/`; `internals/issues/` became issues #77–#79; ~45 dangling plan/handoff pointers removed; release skill, codemap and the PyPI guide's symlink advice updated |
| 2 | Single-home docs | done | | 2026-11-13 | mypy paths moved to `[tool.mypy] files` (CI runs plain `uv run mypy`); personal reporting preference moved to the gitignored `CLAUDE.local.md`; skill's duplicated command blocks replaced by links; conduct contact still a placeholder |
| 3 | Agent side | open | | | |
| 4 | CI | open | | | |
