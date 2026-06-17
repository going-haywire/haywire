# Module: Tests

> pytest suite organised by area (core, ui, studio, libraries, haystack, integration). Aims for 100% coverage on `haywire-core`; uses markers to separate fast unit tests from slow integration runs.

**Path:** `tests/`
**Language:** Python 3.10+ (pytest, pytest-playwright)
**Owner:** All teams (each owns tests near their module)
**Tree hash:** `7077a73833c0c609ad9ef0e9ff74e6086267c726`
**Mapped at:** 51d1ac64 (2026-06-17)

---

## 1. Scope & Purpose

The full automated test suite for the workspace. Tests are grouped by the area of the codebase they cover:

- `tests/core/` — engine: di, execution, graph (clipboard, compatibility, node-warnings), node, settings, signals, state, session, reactive, library.
- `tests/graph_editor/` — graph-editor plugin: graph-app-state, dirty-sync, warning-badge, compatibility-summary.
- `tests/ui/` — UI primitives: editor/panel/slot/theme/signals/canvas handlers, **widget/** (base-floor, bind-*, skin-profile, sync-path, cost-attribution, etc.). New: `test_panel_rendering.py`, `test_redraw_coordinator.py`, `test_editor_wrapper_set_dirty.py`.
- `tests/studio/` — studio app: app shell, library state container, edit state, focus, haystack editor.
- `tests/libraries/` — library-system behaviour (focus IDs, reactive clipboard).
- `tests/haystack/` — haystack-specific tests. New: `test_haystack_state_rename.py` (library rename support).
- `tests/integration/` — slow, full-stack tests.
- `tests/test_*.py` (CLI/core tests) — scaffolding, smoke, share, marketplace, rename, library storage, init, etc.

## 2. Folder Architecture

```
tests/
├── conftest.py
├── test_smoke.py
├── test_init_scaffolding.py  (updated — storage path helpers)
├── test_share_bump_keyword.py
├── test_rename_cli.py         (new) — haywire rename CLI tests
├── test_library_manager_*.py  (expanded) — marketplace install/uninstall/reload
├── test_marketplace_*.py      (new) — marketplace state/config
├── test_workspace_save_dir.py (new) — workspace dir helpers
├── test_library_storage_dir.py (new) — per-library storage paths
├── core/
│   ├── test_di/  test_execution/  test_graph/  test_node/
│   ├── test_session/  test_settings/  test_signals/  test_state/
│   ├── test_library/  test_debug/  test_reactive.py
│   ├── test_graph/:
│   │   ├── test_clipboard_payload.py
│   │   ├── test_compatibility_on_load.py
│   │   ├── test_node_warnings.py
│   │   └── test_show_widget_strategy.py
│   └── test_marketstall/test_helpers.py (new)
├── ui/
│   ├── widget/  ← base-floor, bind-*, skin-profile, sync-path, cost-attribution
│   ├── editor/  panel/  graph_canvas/  harness/  reactive/
│   ├── test_panel_rendering.py        (new) — panel host rendering
│   ├── test_redraw_coordinator.py     (new) — panel redraw coordination
│   ├── test_editor_wrapper_set_dirty.py (new) — editor dirty-flag behavior
│   └── panel/test_panel_error_boundary.py (removed, merged into test_panel_rendering.py)
├── graph_editor/
│   ├── test_compatibility_summary.py
│   ├── test_graph_app_state.py
│   ├── test_graph_editor_dirty_sync.py (updated)
│   └── test_warning_badge.py
├── studio/
│   └── test_graph_editor_on_focus.py (updated)
├── libraries/
│   ├── test_session_context_menu_provider.py (new)
│   └── test_session_file_menu_provider.py (updated)
├── haystack/
│   └── test_haystack_state_rename.py (new)
└── integration/
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
