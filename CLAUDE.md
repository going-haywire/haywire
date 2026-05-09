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

## Documentation

When looking up how a system works (API, parameters, behaviour), check `docs/` first before reading source code. Layout:

- `docs/components/<area>/<area>-canon.md` — extension-point authoring guides (nodes, types, ports, adapters, settings, widgets, themes, editors, panels, states, libraries, haybale-package).
- `docs/architecture/<area>/<area>-arch.md` — framework internals (execution pipeline, library system, hot-reload, settings resolution, session/state, studio).
- `docs/reference/glossary.md` — canonical vocabulary, including the five distinct meanings of "library".
- `docs/reference/design-guide.md` — contains guidelines for UI design / UX rules and design tokens. Follow these when implementing new UI features or refactoring existing ones.

Run `uv run mkdocs serve` to preview the published site at `http://127.0.0.1:8000`.


## Testing

- Always run the full test suite (`pytest` or equivalent) after any refactor or multi-file change and confirm all tests pass before presenting work as complete.
- Call `force_immediate_validation()` after node setup in tests to flush the dirty queue before asserting.
- In test files, import `haywire.core.graph.editor` before other haywire modules to avoid circular import errors.

### Commands

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

## Traps and gotchas

Things that aren't visible from the code itself — bugs we hit, framework quirks, "don't do X because Y" rules. Long-form versions live in [.insights/](.insights/); read the relevant file before debugging in that area.

### Framework gotchas (NiceGUI / Quasar / Vue 3)

- [feedback_nicegui_async.md](.insights/feedback_nicegui_async.md) — slot stack is per-asyncio-task; `asyncio.ensure_future()` makes `ui.notify()` crash. Three safe patterns.
- [feedback_nicegui_dialog_theming.md](.insights/feedback_nicegui_dialog_theming.md) — `.style()` color doesn't reach Quasar pseudo-elements; use `hui.dialog_card()` (carries `hw-panel`).
- [feedback_nicegui_autofocus.md](.insights/feedback_nicegui_autofocus.md) — autofocus in dynamic popups needs `ui.timer(0.1, ...) + run_javascript`.
- [feedback_nicegui_compact_panels.md](.insights/feedback_nicegui_compact_panels.md) — `compact-fields` utility class for dense field layouts.
- [feedback_nicegui_headless_tab_panels.md](.insights/feedback_nicegui_headless_tab_panels.md) — `ui.tab_panels` works without `ui.tabs`; keep-alive container pattern.
- [project_popup_vue.md](.insights/project_popup_vue.md) — `__enter__` must return a `ui.column`; Vue 3 doesn't proxy `_`-prefixed `data()` properties.

### Test traps

- [feedback_barn_module_reload_test_trap.md](.insights/feedback_barn_module_reload_test_trap.md) — top-of-file imports of barn classes go stale after `importlib.reload`. Use `importlib.import_module` + `patch.object`.
- [project_registry_force_reload_bug.md](.insights/project_registry_force_reload_bug.md) — fixed in `7b7d86e`; symptom was `assert Foo is Foo` failing (same name, distinct objects). If it ever recurs, look for `force_reload=True` on initial registry scans.

### Architecture traps

- [project_di_context.md](.insights/project_di_context.md) — DI context uses module-level globals, NOT `ContextVar`. ContextVar broke hot-reload (reload captured a different ContextVar instance than the rest of the app). Don't switch back without solving that.
- [project_graph_canvas_connection.md](.insights/project_graph_canvas_connection.md) — `pin.flow_type.value` (`'data'`) vs `str(pin.flow_type)` (`'FlowType.DATA'`); `lastMousePos` workaround for resume-without-coords.
- [project_minimap.md](.insights/project_minimap.md) — minimap must be sibling of `ZoomPanContainer`, not child. Why `offsetLeft`/`getBoundingClientRect` don't work for node scanning.

### Design rules

- [project_ui_design_system.md](.insights/project_ui_design_system.md) — anti-patterns with reasons: no hardcoded colors, no `box-shadow` on chrome, no `truncate` on QBtn, no `ui.card()` inside `ui.dialog()`.

When you discover a new trap that isn't obvious from the code, add a file to `.insights/` and a one-line entry above. Keep this list under ~20 entries — if it gets longer, demote less-load-bearing ones to a subdir `CLAUDE.md`.
