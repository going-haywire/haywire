# Agent instructions

This file holds what applies to agents only. The process for everyone (roles, forks,
issues, pull requests, review, the rules every change keeps) is
[CONTRIBUTING.md](CONTRIBUTING.md); every command is in
[docs/guides/development.md](docs/guides/development.md); tests in
[tests/README.md](tests/README.md). Follow them; this file does not repeat them.

## Architecture

Haywire is a Blueprint-inspired visual programming system with a **dual-flow model**: control pins define execution order, data pins pass values.

This project uses Python with NiceGUI framework. The codebase has a haywire DI framework. Do not introduce patterns that have no existing equivalent: check in related code for existing architectural approaches before design.

When working on architecture or design patterns, do NOT assume singleton patterns, library ownership models, or registration paths. Ask for confirmation before implementing architectural decisions that affect class hierarchies or dependency injection. Every design follows [docs/reference/design-principles.md](docs/reference/design-principles.md).

## Skills & Commands

When user runs a slash command or skill, execute it immediately without asking clarifying questions. If the skill loads context, treat it as context — don't interpret it as a user request for configuration.

Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit.

### Package Layout

`.codemap/INDEX.md` provides an entry point to get a grasp on the layout of this repo.

## Documentation

When looking up how a system works (API, parameters, behaviour), check `docs/` first before reading source code. Layout:

- `docs/reference/doc-authoring.md` — how to write a page in this docs site: front matter, nav wiring, and linking to live source.
- `docs/reference/glossary.md` — canonical vocabulary, including the five distinct meanings of "library".
- `docs/reference/design-guide.md` — contains guidelines for UI design / UX rules and design tokens. Follow these when implementing new UI features or refactoring existing ones.

Plans, designs and handoffs go in `workbench/plans/` (dated file names), experiments in `workbench/playground/`, whatever a skill's default says.

### Design rules

UI/UX visual rules, tokens, and anti-patterns are canonical in `docs/reference/design-guide.md` — see the Documentation section above. Do not create a second design-rules doc under `.insights/`.

## Git and pull requests

Before the first branch, commit, push or `gh pr` command of any task, however small, load the `haywire-workflow` skill and follow it; releases: `/haywire-release`. The non-obvious parts: [.insights/project_pr_workflow.md](.insights/project_pr_workflow.md).

- Destructive git commands stay with the user: `.claude/hooks/block-dangerous-git.sh` lists and blocks them.
- Before a commit, run the [checks](docs/guides/development.md#checks) on what changed. The full suite is CI's job on every push; run it locally (`/verify`, about 5 minutes) only when asked.
- Whenever the user has to decide or review something, give them what they need in one look: the URL of every PR, issue or CI run involved, markdown links to the local files and lines that matter, the options lettered with a recommendation, and the evidence. They should never have to go and find it.

## Traps and gotchas

This codebase has many silent failure modes (NiceGUI slots and events, test isolation, DI globals, registries, edge and pin rendering, settings). Each known one has a file in `.insights/`, indexed in [.insights/INDEX.md](.insights/INDEX.md). Check the index first whenever a symptom is silent or surprising: assume a known trap before a new bug.

A new trap gets a file in `.insights/` and an entry in the index.

<!-- Fork pull request end-to-end test. Not for merge. -->
