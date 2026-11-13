---
status: draft
doc_template: guide
scope: Working on the Haywire repository itself — clone and setup, a project wired to the local clone, running, testing, linting, and building docs
see-also:
  - doc-authoring.md
  - publish-to-pypi.md
  - ../reference/publish_releases.md
---

# Developing Haywire

This page is for contributors working on the Haywire repository: setup and every command. How to contribute (forks, issues, pull requests, review) is in [CONTRIBUTING.md](https://github.com/going-haywire/haywire/blob/master/CONTRIBUTING.md). To use Haywire, see the [README](https://github.com/going-haywire/haywire#readme); to author a library, see [Authoring a haybale](../haybale/haybale-canon.md).

## Repository layout

Haywire is a **uv workspace monorepo**. The root `pyproject.toml` is the workspace, not a package.

| Path | Contents |
|---|---|
| `packages/haywire-core/` | The framework: graph engine, DI, nodes, edges, ports, settings, execution, UI primitives. Published to PyPI. |
| `packages/haywire-studio/` | The application and the `haywire` CLI (`init`, `share`, `docs`). Published to PyPI. |
| `barn/haybale-*/` | Plugin libraries: `haybale-core` (standard types and nodes), `haybale-studio`, `haybale-graph-editor`, `haybale-haystack`, `haybale-marketplace`, plus example and test libraries. |
| `tests/` | Framework tests. |
| `docs/` | This site's sources (see below). |
| `.insights/` | Known traps and silent failure modes, indexed in `.insights/INDEX.md`. |
| `workbench/` | Working material: plans and handoffs (`plans/`), experiments and measuring tools (`playground/`). Not documentation. |

## Setup

Clone your fork (or the repository itself, if you have write access):

```sh
gh repo fork going-haywire/haywire --clone   # origin = your fork, upstream = going-haywire/haywire
cd haywire
uv sync --all-extras --dev
uv run playwright install chromium            # browser tests
```

uv downloads a matching Python (3.12 or newer) if none is installed. All workspace packages install as editable, so changes take effect immediately.

## Scaffold a project against your clone

`haywire init --dev` creates a project whose dependencies are editable paths into your clone instead of PyPI releases:

```sh
cd /tmp
uv run --project <absolute path to your clone> haywire init myTestProject --dev
```

## Run

```sh
uv run haywire                  # launch the studio
uv run python -m haywire_studio # same, with module syntax
```

## Checks

These are the checks CI runs. Before you open a pull request, run them on what you changed:

```sh
uv run ruff check <changed files>          # lint (line length 109); "." for everything
uv run ruff format --check <changed files> # formatting; "ruff check" as an instruction means both
uv run mypy                                # types: the paths in [tool.mypy] files, as CI checks them
uv run mypy <path>                         # one package, while iterating
uv run pytest <tests of the changed area> -q
```

## Tests

```sh
uv run pytest tests/path/to/file.py -q                # one file: the default while iterating
uv run pytest tests/some_dir/ -q                      # one area
uv run pytest tests/ -k "edge" -q                     # by name
uv run pytest -m "not browser and not perf" -n 4 -q   # whole non-browser tier, ~4 min
uv run pytest -m browser -n 4 -q                      # browser tier, ~2 min
```

`-n 4`, never more. Tiers, parallelism and test traps are in [tests/README.md](https://github.com/going-haywire/haywire/blob/master/tests/README.md).

## Build packages and docs

```sh
uv build --package haywire-core          # build one package
uv run mkdocs serve                      # preview this site at http://127.0.0.1:8000
uv run mkdocs build --strict             # what the docs deploy checks
uv run haywire docs barn/haybale-mylib   # one library's generated docs (README/OVERVIEW/QUICKREF/docs/*.md)
uv run haywire docs --all                # every in-repo library, one load
```

The published site is built from `docs/` with Material for MkDocs and redeployed on every push to `master`. See [Writing a doc page](../reference/doc-authoring.md) for conventions. Releases are lockstep across all packages; see [Publish releases](../reference/publish_releases.md).

## Editor tip

For source-link navigation in VS Code, add `code` to your PATH (Command Palette → "Shell Command: Install 'code' command in PATH").
