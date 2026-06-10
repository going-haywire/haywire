# Module: Tests

> pytest suite organised by area (core, ui, studio, libraries, haystack, integration). Aims for 100% coverage on `haywire-core`; uses markers to separate fast unit tests from slow integration runs.

**Path:** `tests/`
**Language:** Python 3.10+ (pytest, pytest-playwright)
**Owner:** All teams (each owns tests near their module)
**Tree hash:** (updated 2026-06-10)
**Mapped at:** b5068ae7 (2026-06-10)

---

## 1. Scope & Purpose

The full automated test suite for the workspace. Tests are grouped by the area of the codebase they cover:

- `tests/core/` — engine: di, execution, graph (clipboard, compatibility, node-warnings), node, settings, signals, state, session, reactive, library.
- `tests/graph_editor/` — graph-editor plugin: graph-app-state, dirty-sync, warning-badge, compatibility-summary.
- `tests/ui/` — UI primitives: editor/panel/slot/theme/signals/canvas handlers, **widget/** (new: base-floor, bind-nested/sugar, skin-profile, sync-path, cost-attribution, expect-args-cache, etc.).
- `tests/studio/` — studio app: app shell, library state container, edit state, focus, haystack editor.
- `tests/libraries/` — library-system behaviour (focus IDs, reactive clipboard).
- `tests/haystack/` — haystack-specific tests.
- `tests/integration/` — slow, full-stack tests.
- `tests/test_init_scaffolding.py`, `tests/test_smoke.py`, `tests/test_share_bump_keyword.py` — CLI scaffolding, smoke, share.

## 2. Folder Architecture

```
tests/
├── conftest.py
├── test_smoke.py
├── test_init_scaffolding.py
├── test_share_bump_keyword.py
├── core/
│   ├── test_di/  test_execution/  test_graph/  test_node/
│   ├── test_session/  test_settings/  test_signals/  test_state/
│   ├── test_library/  test_debug/  test_reactive.py
│   └── test_graph/:
│       ├── test_clipboard_payload.py (new)
│       ├── test_compatibility_on_load.py (new)
│       ├── test_node_warnings.py (new)
│       ├── test_show_widget_strategy.py (new)
├── ui/
│   ├── widget/ (new: base-floor, bind-*, skin-profile, sync-path, cost-attribution, etc.)
│   ├── editor/  panel/  graph_canvas/  harness/  reactive/
│   ├── test_app_shell.py  test_editor_registry.py  test_theme_registry.py
│   └── ~40 tests total
├── graph_editor/
│   ├── test_compatibility_summary.py (new)
│   ├── test_graph_app_state.py
│   └── test_warning_badge.py (new)
├── studio/
├── libraries/
├── haystack/
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
