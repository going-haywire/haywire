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

This page is for contributors working on the Haywire repository. To use Haywire, see the [README](https://github.com/going-haywire/haywire#readme); to author a library, see [Authoring a haybale](../haybale/haybale-canon.md).

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

## Setup

```sh
git clone https://github.com/going-haywire/haywire.git
cd haywire
uv sync
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

## Test and lint

```sh
uv run pytest                              # all tests
uv run pytest -m "not browser and not perf" # fast local loop
uv run pytest tests/ -k "edge"             # filtered
uv run ruff check .                        # lint (line-length 109)
uv run ruff format --check .               # formatting
uv run mypy .                              # type checking
```

`create_node_wrapper()` leaves a pending `NODE_ADDED` in the dirty queue, so tests call `force_immediate_validation()` after setup.

## Build packages and docs

```sh
uv build --package haywire-core   # build one package
uv run mkdocs serve               # preview this site at http://127.0.0.1:8000
```

The published site is built from `docs/` with Material for MkDocs and redeployed on every push to `master`. See [Writing a doc page](../reference/doc-authoring.md) for conventions. Releases are lockstep across all packages; see [Publish releases](../reference/publish_releases.md).

## Editor tip

For source-link navigation in VS Code, add `code` to your PATH (Command Palette → "Shell Command: Install 'code' command in PATH").
