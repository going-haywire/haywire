# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## Architecture

Haywire is a Blueprint-inspired visual programming system with a **dual-flow model**: control pins define execution order, data pins pass values.

### Package Layout

- **`packages/haywire-core/`** — publishable core (`import haywire`)
  - `haywire/core/` — graph engine, DI, nodes, edges, ports, types, execution, settings
  - `haywire/ui/` — NiceGUI renderers, widgets, canvas, themes, panels, etc.
- **`packages/haywire-studio/`** — CLI application (`haywire` entry point)
  - `app.py` — main `HaywireApp` class (~500 lines)
  - `config.py` — global/project TOML config
  - `graph_manager.py` — GraphManager, file-centric multi-graph registry
  - `library_manager.py` — runtime library install/UI
  - `init.py` / `share.py` — CLI subcommands
- **`barn/haybale-*/`** — plugin node libraries
- **`tests/`** — pytest test suite (100% coverage)
- **`docs`** — markdown documentation

## Commands

```sh
# Run the app
uv run haywire

# Tests
uv run pytest                        # all tests
uv run pytest -m unit                # unit tests only (fast)
uv run pytest -m integration         # integration tests (full library system, slow)
uv run pytest -m "not integration"   # everything except slow integration tests
uv run pytest tests/ -k "edge"       # filtered by name
uv run pytest --cov                  # with coverage
uv run pytest tests/path/to/file.py  # single file

# Code quality
uv run ruff check .                          # lint (line-length = 109)
uv run ruff format .                         # format
uv run mypy packages/haywire-core/src/       # type checking
```

## Testing Gotchas

- Call `force_immediate_validation()` after node setup in tests to flush the dirty queue before asserting.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
