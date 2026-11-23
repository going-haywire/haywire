---
serve: developer
status: current
doc_template: guide
scope: Read before a first contribution or when a pull request needs the rules — roles, the introduction, issues, tools, making the change, the pull request, review, agents, a fork's pull request for the maintainer
see-also:
  - workflow.md
  - first-contribution.md
---

# Contributing to Haywire

Thanks for helping. We assume good intentions and welcome changes and suggestions of every
size. This page is the process: who does what, how a change gets from your fork into
`master`, and what to expect on the way. The [Collaboration](index.md) pages draw
it, and every other workflow, as diagrams. Commands are in
[docs/guides/development.md](../guides/development.md); the rules agents follow on top
of this are in [CLAUDE.md](https://github.com/going-haywire/haywire/blob/master/CLAUDE.md) (read through [AGENTS.md](https://github.com/going-haywire/haywire/blob/master/AGENTS.md)).

## Roles

- **Maintainer**: has write access to `going-haywire/haywire`; reviews, merges and
  releases.
- **Contributor**: everyone else; works on a fork and proposes changes through pull
  requests.

A contributor never merges or releases. A **collaborator** role (write access, no merging
or releasing) may come later.

## Your first contribution: introduce yourself

Before your first pull request, even a typo fix, open an
[introduction issue](https://github.com/going-haywire/haywire/issues/new/choose): who you
are, what you'd like to work on, and why. Please write it yourself, not with an AI: it is
the one place we want to hear from you directly. The maintainer answers and marks it
`introduction accepted`; from then on the rules below apply.

A pull request that arrives before that is welcome too: it gets a friendly comment and the
label `needs introduction`, stays open, and can be merged once the introduction is
accepted. Why it works this way: [ADR 0079](../adr/0079-a-first-contribution-starts-with-an-introduction.md).

## Before you start a change

- **Small fixes go straight to a pull request**: a bug with a clear cause, docs, typos,
  tests.
- **Everything else starts with an issue**: a new feature, node or type, an API or
  architecture change, a refactor. Agree on the approach there before writing code; the
  architecture rules in [CLAUDE.md](https://github.com/going-haywire/haywire/blob/master/CLAUDE.md) and the
  [design principles](../reference/design-principles.md) apply to every design.
- **The backlog is the issue list.** `good first issue` and `help wanted` mark work that is
  open to others. Claim an issue by commenting on it, so two people don't build the same
  thing.

## Tools

Required: [uv](https://docs.astral.sh/uv/), git, the [GitHub CLI](https://cli.github.com/)
(`gh auth login`), and `jq` (the agent hooks use it). On Windows, let git create symbolic
links before you clone (Developer Mode on, `git config --global core.symlinks true`): the
three scripts are links into `dev/scripts/`.

Optional:

- **Claude Code or another coding agent**: welcome; see *Working with AI agents* below.
- **An orchestrator**: an app that runs agent sessions side by side in worktrees; any or none
  ([orchestrators](orchestrators/index.md)).
- **The umbrella environment**: one environment with the libraries of several haywire
  repositories cloned side by side, to run the full studio with all of them.
- **Farmhand** (`.mcp.json`): lets an agent drive a running studio.
- **CodeGraph**: a code index some agents use for navigation.

## Making the change

1. Branch from the latest upstream `master`, never work on your fork's `master`:

   ```sh
   git fetch upstream
   git switch -c fix/<short-name> upstream/master    # kind: feat, fix, chore, docs, test
   ```

2. Commit in the repository's style, `type(area): summary` (for example
   `fix(editor): keep the selection after undo`).
3. Run the [checks](../guides/development.md#checks) on what you changed. CI does not run
   on your fork's branches, only on the pull request. A change only a person can judge
   (UI, interaction, a device) ends with a [live check](../guides/development.md#run):
   one confirmation in the running studio once everything else passes; its results go
   in the pull request.
4. Keep these rules:
   - **Python follows the [coding standards](../reference/coding-standards.md).** Review
     cites a rule by its ID (`CS-E2`).
   - **One home per piece of information.** Every rule, command and fact lives in exactly
     one file; other files link to it instead of repeating it.
   - **Plans and handoffs go in `workbench/plans/`**, never in `docs/`, which holds only
     published documentation. Permanent files (code, docs, skills) never link to a plan.
   - **Tests never pin wording.** A test checks what a message carries, not how it is
     phrased: [Text in tests](https://github.com/going-haywire/haywire/blob/master/tests/README.md#text-in-tests).
   - **Never change a version number** (`pyproject.toml`, `haybale.toml`, `>=` pins).
     Releases are lockstep across all packages and only the maintainer cuts them.
   - **Files that steer agents or CI** (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.github/`, `plugins/`)
     may be changed, but the maintainer reads every line of such a change before merging;
     the pull request gets the label `agent files` until then.

## Opening the pull request

Push to your fork and open the pull request against `going-haywire/haywire` `master`
(`gh pr create --repo going-haywire/haywire`). The template asks for what changed and why,
the issue it closes (`Fixes #12`), the checks, and whether AI helped. A draft is fine
while you are still working.

- CI runs in the upstream repository, on the pull request's version of the workflow
  files, with a read-only token and no secrets. For a first-time contributor, the
  maintainer approves each run.
- Answer review by pushing more commits to the same branch; don't open a new pull request.
- Ticking *Allow edits by maintainers* lets the maintainer push small fixes to your
  branch.

## Review and merge

The maintainer reviews on GitHub and merges with a squash commit once every check has
passed, macOS included. Feedback that has to be resolved before a merge comes as a line
comment; a merge waits until every review thread is resolved.

## Working with AI agents

Agents are welcome on both sides. They read [AGENTS.md](https://github.com/going-haywire/haywire/blob/master/AGENTS.md), which points to
[CLAUDE.md](https://github.com/going-haywire/haywire/blob/master/CLAUDE.md), and the workflow page
([docs/collaboration/workflow.md](workflow.md), which the Farmhand bridge
serves to every agent session here) holds the step-by-step for contributors and the maintainer.

- An agent works freely on your fork: branches, commits, pushes.
- Anything public on `going-haywire/haywire` (opening or readying a pull request,
  commenting, reviewing) an agent does only when you say so: it appears under your name.
- An agent never writes your introduction issue.

## For the maintainer: handling a fork's pull request safely

A pull request from a fork is untrusted code and untrusted text. The reasons behind these rules:
[ADR 0080](../adr/0080-untrusted-pull-requests-meet-nothing-with-power.md).

- **Workflows with rights never run pull request code.** A workflow that has write rights
  or secrets (`pull_request_target`, `workflow_run`) never checks out, installs or runs code
  from an unmerged pull request; it reads metadata or uploaded reports as data only.
  `pull_request` workflows run the code with a read-only token.
- **Never start an agent session in a checkout of a fork's pull request.** Its `CLAUDE.md`,
  skills and hooks would become the session's instructions, and hooks run shell
  commands.
- **Review before running.** Read the diff and CI results first. Only a pull request judged
  safe is tried locally: in its own worktree
  (`git worktree add ../review-pr-<n> && cd ../review-pr-<n> && gh pr checkout <n>`), run by
  hand or from an agent session started in the main folder, never inside the review
  worktree. Keep `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` unset, so a session
  does not load the review worktree's `CLAUDE.md`. Remove the worktree afterwards. A
  doubtful pull request goes to a GitHub Codespace or is not run at all.
- **Treat everything in the pull request as data**, including its description, comments
  and code comments: text there may be written to steer an agent.

## In a library

The organisation's libraries (`going-haywire/haybale-*`) follow everything above. What
differs:

- **One introduction counts everywhere.** It is filed in core
  ([introduction](https://github.com/going-haywire/haywire/issues/new/choose)); a library's pull
  request that arrives before it gets the label `needs introduction`, which comes off the next
  time the intake runs once the introduction is accepted.
- **Setting up.** A library reaches core by relative paths: clone it beside a clone of core,
  under the names the paths expect, and run `uv sync --frozen` in it
  ([setting someone up](../agents/start.md), *Develop Haywire*). Its `pyproject.toml`
  (`[tool.uv.sources]`) shows which core packages come from `../haywire-repo`. Running it in the
  full studio with other libraries:
  [ADR 0081](../adr/0081-libraries-from-other-repositories-run-from-an-umbrella-environment.md).
- **Checks:** `uv run --frozen ruff check .`, `uv run --frozen ruff format --check .`,
  `uv run --frozen pytest`. CI runs the same on every pull request, against core's `master`,
  and every night.
- **Import the framework only through the Author API** (`haywire.api`, `haywire.api.workbench`);
  `ruff` refuses `haywire.core`, `haywire.ui` and `haywire.barn` outside the test fixtures.
- **A change that needs an unreleased change of core** raises that requirement's dependency
  floor (`>=`) to the next patch after core's latest release, in the same commit. CI runs against
  core's `master`, so it passes; the library is released once core is.
- **Never change a version number.** The maintainer releases a library through a release pull
  request (`haywire share --pr`); merging it publishes.
- **Its repository files** (CI callers, agent files) come from `uv run haywire init --org-files`;
  setting up a library repository is [a new organisation library](new-org-library.md).

## Licence, security, conduct

- Contributions are licensed under the repository's licence (core's is the
  [MIT licence](https://github.com/going-haywire/haywire/blob/master/LICENSE)), the same terms as
  the code they join.
- Report a vulnerability privately, never in a public issue: see the
  [security policy](https://github.com/going-haywire/.github/blob/main/SECURITY.md).
- Everyone taking part follows the
  [code of conduct](https://github.com/going-haywire/.github/blob/main/CODE_OF_CONDUCT.md).
