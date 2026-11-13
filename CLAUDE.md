# General Guidelines

When reporting information to me, be extremely concise and sacrifice grammar for the sake of concision.

## Architecture

Haywire is a Blueprint-inspired visual programming system with a **dual-flow model**: control pins define execution order, data pins pass values.

This project uses Python with NiceGUI framework. The codebase has a haywire DI framework. Do not introduce patterns that have no existing equivalent: check in related code for existing architectural approaches before design.

When working on architecture or design patterns, do NOT assume singleton patterns, library ownership models, or registration paths. Ask for confirmation before implementing architectural decisions that affect class hierarchies or dependency injection.

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

Run `uv run mkdocs serve` to preview the published site at `http://127.0.0.1:8000`.

### Design rules

UI/UX visual rules, tokens, and anti-patterns are canonical in `docs/reference/design-guide.md` — see the Documentation section above. Do not create a second design-rules doc under `.insights/`.

## Git and pull requests

Before the first branch, commit, push or `gh pr` command of any task, however small, load the `haywire-workflow` skill and follow it; releases: `/haywire-release`. The non-obvious parts: [.insights/project_pr_workflow.md](.insights/project_pr_workflow.md).

- Work on a branch started from an up-to-date `master`; never commit on `master`.
- Commit and push freely on a branch, without asking; open a draft PR on the first push. CI runs on every push.
- `master` takes changes only through a PR whose checks passed. Merge only on the user's word ("merge"), once the checks are green.
- Never change a version number in a feature PR (`pyproject.toml`, `haybale.toml`, `>=` pins). Releases are lockstep across all packages and happen only through `/haywire-release` in its own release PR ([docs/reference/publish_releases.md](docs/reference/publish_releases.md)). If an instruction says "bump X" or a pin needs a version that does not exist yet, stop and ask.
- Destructive git commands stay with the user: `.claude/hooks/block-dangerous-git.sh` lists and blocks them.
- Whenever the user has to decide or review something, give them what they need in one look: the URL of every PR, issue or CI run involved, markdown links to the local files and lines that matter, the options lettered with a recommendation, and the evidence. They should never have to go and find it.

## Testing

- Before a commit: `ruff check` and `ruff format --check` on the changed files, mypy on the changed packages, and the tests of the areas changed. The full suite is CI's job on every push; run it locally (`/verify`, about 5 minutes) only when asked.
- Use `force_immediate_validation()` only when you need the `ValidationResult` synchronously, or for graphs left on the default (timer) scheduler. See ADR 0002.

### Commands

```sh
uv run haywire                           # run the app
uv run haywire docs barn/haybale-mylib   # generate one library's docs (README/OVERVIEW/QUICKREF/docs/*.md)
uv run haywire docs --all                # every in-repo library, one load
uv run ruff check .                      # lint (line-length = 109)
uv run ruff format --check .             # formatting; "ruff check" as an instruction means both
```

mypy's paths are the `types` job in `.github/workflows/ci.yml` (`haybale-visiongraph` and `haybale-spandrel` are local-only links and stay out). Choosing and running tests, and the pre-edit baseline: the `haywire-workflow` skill; test tiers, parallelism and traps: `tests/README.md`.

## Traps and gotchas

This codebase has many silent failure modes (NiceGUI slots and events, test isolation, DI globals, registries, edge and pin rendering, settings). Each known one has a file in `.insights/`, indexed in [.insights/INDEX.md](.insights/INDEX.md). Check the index first whenever a symptom is silent or surprising: assume a known trap before a new bug.

A new trap gets a file in `.insights/` and an entry in the index.

## Sandcastle

The repo has an autonomous agent loop (Docker sandbox, ticket queue, review branches) — setup, usage, and model variants are documented in [.sandcastle/README.md](.sandcastle/README.md).
