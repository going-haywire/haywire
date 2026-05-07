## Architecture

Haywire is a Blueprint-inspired visual programming system with a **dual-flow model**: control pins define execution order, data pins pass values.

This project uses Python with NiceGUI framework, reactive property descriptors, and a custom settings/theme system. The codebase has a haywire DI framework. Do not introduce patterns that conflict with the existing reactive props system.

When working on architecture or design patterns, do NOT assume singleton patterns, library ownership models, or registration paths. Ask for confirmation before implementing architectural decisions that affect class hierarchies or dependency injection.

## Skills & Commands

When user runs a slash command or skill, execute it immediately without asking clarifying questions. If the skill loads context, treat it as context — don't interpret it as a user request for configuration.

Before editing any file, read it first. Before modifying a function, grep for all callers. Research before you edit. 

### Package Layout

- **`packages/haywire-core/`** — publishable core (`import haywire`)
  - `haywire/core/` — graph engine, DI, nodes, edges, ports, types, execution, settings
  - `haywire/ui/` — NiceGUI renderers, widgets, canvas, themes, panels, etc.
- **`packages/haywire-studio/`** — CLI application (`haywire` entry point)
  - `app.py` — main `HaywireApp` class (~500 lines)
  - `config.py` — global/project TOML config
  - `haystack.py` — file-centric multi-graph registry
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

## Documentation

When looking up how a system works (API, parameters, behaviour), check `docs/` first before reading source code. Layout:

- `docs/components/<area>/<area>-canon.md` — extension-point authoring guides (nodes, types, ports, adapters, settings, widgets, themes, editors, panels, states, libraries, haybale-package).
- `docs/architecture/<area>/<area>-arch.md` — framework internals (execution pipeline, library system, hot-reload, settings resolution, session/state, studio).
- `docs/reference/glossary.md` — canonical vocabulary, including the five distinct meanings of "library".
- `docs/reference/design-guide.md` — visual / UX rules and design tokens.

Run `uv run mkdocs serve` to preview the published site at `http://127.0.0.1:8000`.

## UI Style Guidelines
`docs/reference/design-guide.md` contains guidelines for UI design and implementation. Follow these when implementing new UI features or refactoring existing ones.

## Testing

- Always run the full test suite (`pytest` or equivalent) after any refactor or multi-file change and confirm all tests pass before presenting work as complete.
- Call `force_immediate_validation()` after node setup in tests to flush the dirty queue before asserting.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.
- When patching classes from `barn/haybale-*/` modules in tests, resolve the class and patch target via `importlib.import_module(...)` and `patch.object(module, "Foo", ...)` — top-of-file imports go stale after library bootstrap reloads the module. Reference: `tests/ui/test_canvas_handlers/test_session_context_menu_provider.py`.

/