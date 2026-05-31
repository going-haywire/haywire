# Module: Tests

> pytest suite organised by area (core, ui, studio, libraries, haystack, integration). Aims for 100% coverage on `haywire-core`; uses markers to separate fast unit tests from slow integration runs.

**Path:** `tests/`
**Language:** Python 3.10+ (pytest, pytest-playwright)
**Owner:** All teams (each owns tests near their module)
**Tree hash:** `aca64c64228dd8a4ac1348515225f0ca9915f4ce`
**Mapped at:** a08a6931 (2026-05-31)

---

## 1. Scope & Purpose

The full automated test suite for the workspace. Tests are grouped by the area of the codebase they cover:

- `tests/core/` — engine: di, execution, graph (incl. `test_graph/test_validation_scheduler.py`), node, settings, signals, state, session, reactive.
- `tests/graph_editor/` — graph-editor plugin: `test_graph_editor_dirty_sync.py` (dirty-state propagation).
- `tests/ui/` — UI primitives: editor/panel/slot/theme/signals/canvas handlers.
- `tests/studio/` — studio app: app shell, library state container, edit state, focus, haystack editor.
- `tests/libraries/` — library-system behaviour (focus IDs, reactive clipboard).
- `tests/haystack/` — haystack-specific tests.
- `tests/integration/` — slow, full-stack tests (e.g., `test_haystack_carve_out.py`).
- `tests/test_init_scaffolding.py`, `tests/test_smoke.py` — top-level smoke and CLI scaffolding tests.

## 2. Folder Architecture

```
tests/
├── conftest.py
├── test_smoke.py
├── test_init_scaffolding.py
├── core/
│   ├── test_di/  test_execution/  test_graph/  test_node/
│   ├── test_session/  test_settings/  test_signals/  test_state/
│   ├── test_libraries/  test_debug/  test_reactive.py
├── ui/
│   ├── editor/  panel/  graph_canvas/  harness/  reactive/
│   ├── properties_editor/  test_canvas_handlers/  test_file_browser_menu/
│   ├── test_app_shell.py  test_console_bridge.py  test_signal_bus.py
│   ├── test_panel_registry.py  test_editor_registry.py  test_theme_registry.py
│   └── … (~25 more focused tests)
├── studio/
│   ├── test_app/
│   ├── test_app_library_state_container.py  test_edit_state.py
│   ├── test_file_viewer_on_focus.py  test_graph_editor_on_focus.py
│   └── test_haystack_editor_remove.py  test_library_overview_on_context.py
├── libraries/
│   ├── test_clipboard_reactive.py  test_focuses_have_ids.py
├── haystack/
├── integration/
│   └── test_haystack_carve_out.py
```

## 3. Always-load vs On-demand

### Always-load

- `conftest.py` — shared fixtures (DI reset, library reload helpers).
- A representative test for the area you're changing — pattern-match its setup, especially `force_immediate_validation()` and ordering of imports.

### On-demand

- `tests/integration/` — only when running full-stack flows; these are marked `@pytest.mark.integration`.
- `tests/ui/test_canvas_handlers/` — canvas drag/connect handler tests, heavy on event simulation.

## 4. Rules & Boundaries

- Run the full suite (`uv run pytest`) after any refactor or multi-file change before claiming completion.
- In test files, `import haywire.core.graph.editor` **before** any other haywire module (circular import).
- Call `force_immediate_validation()` after node setup before asserting.
- Do not top-import barn classes — they go stale across `importlib.reload`. Use `importlib.import_module` + `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- Markers:
  - `-m unit` — fast.
  - `-m integration` — slow, full library system.
  - `-m "not integration"` — everything else.
- Coverage target: 100% on `haywire-core`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Shared fixtures | `tests/conftest.py` | DI reset, registry reset |
| Marker definitions | root `pyproject.toml [tool.pytest.ini_options]` | `unit`, `integration` |

---

## Dependencies

### Depends on

- All production modules (engine, UI, studio, all haybale libraries).
- `pytest`, `pytest-cov`, `pytest-playwright`, `playwright`.

### Depended on by

- CI (and humans running `uv run pytest`).

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Smoke test | `tests/test_smoke.py` | First line of defence |
| Init scaffolding | `tests/test_init_scaffolding.py` | Verifies `haywire init` CLI |
| Haystack integration | `tests/integration/test_haystack_carve_out.py` | Full-stack haystack flow |
