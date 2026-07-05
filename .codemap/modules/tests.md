# Module: Tests

> pytest suite organised by area (core, ui, studio, libraries, haystack, integration). Aims for 100% coverage on `haywire-core`; uses markers to separate fast unit tests from slow integration runs.

**Path:** `tests/`
**Language:** Python 3.10+ (pytest, pytest-playwright)
**Owner:** All teams (each owns tests near their module)
**Tree hash:** `e8bb12b9d62fd0e27d696c12467be824f930037f`
**Mapped at:** 19bda1e (2026-07-05)

---

## 1. Scope & Purpose

The full automated test suite for the workspace. Tests are grouped by the area of the codebase they cover:

- `tests/core/` — engine: di, execution, graph, node, settings, signals, state, session, reactive, library, types. Contains the characterization-test suites for the settings/promotion refactors landed under ADRs 0011–0017 (tier collapse, JSON persistence, single-cell model, promotion-as-direction, storage-key id, cell-authoritative settings, widget-selection port contract).
- `tests/graph_editor/` — graph-editor plugin: graph-app-state, dirty-sync, warning-badge, compatibility-summary.
- `tests/ui/` — UI primitives: editor/panel/slot/theme/signals/canvas handlers, **widget/** (base-floor, bind-*, skin-profile, sync-path, cost-attribution, select-widget-options), **menu/** (new — promote/demote flyout menu).
- `tests/studio/` — studio app: app shell, library state container, edit state, focus, haystack editor.
- `tests/libraries/` — library-system behaviour (focus IDs, reactive clipboard).
- `tests/haystack/`, `tests/marketstall/`, `tests/marketplace/`, `tests/execution/`, `tests/scripts/` — area-specific suites (haystack rename, marketstall install pipeline, marketplace config, compile-result, doc/codegen scripts).
- `tests/barn/builtin/` — new: characterization tests for the builtin haybale library (adapters, widgets, ITypes, vectors/color, hoisted widgets).
- `tests/integration/` — slow, full-stack tests.
- `tests/test_*.py` (CLI/core tests) — scaffolding, smoke, share, marketplace, rename, library storage, init, etc.

⚠️ Note: `tests/core/` currently has **two parallel naming schemes** for the same areas — legacy `test_node/`, `test_settings/`, `test_graph/`, `test_types/` (prefixed, established) alongside new unprefixed `node/`, `settings/`, `graph/`, `types/` directories introduced by the promotion/settings refactor commits. Both are live; check both when searching for a test by topic. This looks like an in-progress dir-naming migration — no dedication ADR found for it yet.

## 2. Folder Architecture

```
tests/
├── conftest.py                 (expanded — new shared fixtures for settings/promotion suites)
├── test_smoke.py
├── test_rename_cli.py, test_library_manager_*.py, test_marketplace_*.py, test_workspace_save_dir.py,
│   test_library_storage_dir.py, test_init_scaffolding.py, test_gen_docs_readme_contract.py, ...
├── barn/
│   └── builtin/                (new dir) — test_basic_adapters, test_builtin_library_loads,
│       test_floor_end_to_end, test_type_default_widget, test_type_keys, test_vectors_color,
│       test_widgets_hoisted
├── core/
│   ├── test_di/  test_execution/  test_session/  test_signals/  test_state/
│   ├── test_library/  test_libraries/  test_debug/  test_undo/  test_reactive.py  test_widget_keys.py
│   ├── test_node/       ← legacy (test_base.py expanded, test_decorator.py, test_factory.py)
│   ├── node/            ← (new dir) promotion suites: test_promote_demote, test_promotion_e2e,
│   │                       test_promotion_resolver, test_promotion_roundtrip,
│   │                       test_promotion_serialization, test_promotion_single_cell,
│   │                       test_promotion_storage_key, test_reroute_node, test_reroute_registry
│   ├── test_settings/   ← legacy, heavily expanded: test_canonical_key, test_cell_authoritative_read,
│   │                       test_cell_subscription, test_desugar, test_itype_cutover,
│   │                       test_json_persistence, test_mirror_cell_authoritative, test_no_self_mirror,
│   │                       test_registry_cells, test_single_cell, test_tier_collapse,
│   │                       test_widget_stamping, plus updated test_settings.py / test_hot_reload.py /
│   │                       test_schema_rebasing.py / test_schema_reregister_repopulate.py, own conftest.py
│   ├── settings/        ← (new dir) test_bag_node_ref, test_promoted_shared_cell (supersedes the
│   │                       old read-tier bridge test; promoted ports now borrow the setting's cell)
│   ├── test_graph/      ← legacy (test_compatibility_on_load.py updated)
│   ├── graph/           ← (new dir) test_load_degradation.py — per-item load-hardening
│   ├── test_types/      ← legacy: test_choices_type.py
│   └── types/           ← (new dir) test_field_change_event.py, test_itype_roundtrip.py
├── ui/
│   ├── widget/  ← base-floor, bind-*, skin-profile, sync-path, cost-attribution,
│   │              test_select_widget_options.py (new), own conftest.py (new)
│   ├── menu/    ← (new dir) test_promote_demote_menu.py — promote/demote flyout menu
│   ├── panel/   ← test_promoted_row_state.py (new), test_setting_widget_model.py (new),
│   │              test_render_settings_subscription.py (updated)
│   ├── editor/  graph_canvas/  harness/  reactive/  components/  extends/
│   ├── test_editor_wrapper_set_dirty.py, test_panel_redraw_union.py, test_panel_registry.py, ...
│   └── harness/ (updated for new widget/promotion contracts: test_widgets.py, test_mirror.py,
│                 test_validation.py, test_structural.py, test_external_sync.py removed/merged)
├── graph_editor/
│   ├── test_compatibility_summary.py, test_graph_app_state.py,
│   └── test_graph_editor_dirty_sync.py (updated), test_warning_badge.py
├── studio/  libraries/  haystack/  marketstall/  marketplace/  execution/  scripts/
└── integration/
```

## 3. Always-load vs On-demand

### Always-load

- `conftest.py` (root) — shared fixtures (DI reset, library reload helpers).
- `tests/core/test_settings/conftest.py` — settings-suite fixtures; check before adding a settings/promotion test.
- A representative test for the area you're changing — pattern-match its setup, especially `force_immediate_validation()` and ordering of imports.
- When touching settings/promotion: skim `tests/core/test_settings/test_single_cell.py` and `tests/core/node/test_promotion_single_cell.py` first — these are the canonical characterization suites for the current (post-ADR-0011–0017) model.

### On-demand

- `tests/integration/` — only when running full-stack flows; these are marked `@pytest.mark.integration`.
- `tests/ui/test_canvas_handlers/` — canvas drag/connect handler tests, heavy on event simulation.
- `tests/barn/builtin/` — only when changing the builtin haybale library's adapters/widgets/types.

## 4. Rules & Boundaries

- Run the full suite (`uv run pytest`) after any refactor or multi-file change before claiming completion.
- In test files, `import haywire.core.graph.editor` **before** any other haywire module (circular import).
- Call `force_immediate_validation()` after node setup before asserting.
- Do not top-import barn classes — they go stale across `importlib.reload`. Use `importlib.import_module` + `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- Two parallel `core/` sub-dir naming schemes currently coexist (see ⚠️ note above) — when adding a settings/node/graph/types test, check both the legacy `test_X/` and new `X/` dir before picking a home; ⚠️ TODO: confirm with the team which is the long-term convention.
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
| Settings single-cell model | `tests/core/test_settings/test_single_cell.py` | ADR 0013 characterization suite |
| Settings tier collapse | `tests/core/test_settings/test_tier_collapse.py` | ADR 0011 |
| Settings JSON persistence | `tests/core/test_settings/test_json_persistence.py` | ADR 0012 |
| Cell-authoritative settings reads | `tests/core/test_settings/test_cell_authoritative_read.py`, `test_mirror_cell_authoritative.py` | ADR 0013 (former-0016 amendment) |
| Promotion-as-direction / single-cell promotion | `tests/core/node/test_promotion_single_cell.py`, `test_promote_demote.py`, `test_promotion_e2e.py` | ADR 0014 |
| Promoted-port cell sharing | `tests/core/settings/test_promoted_shared_cell.py` | supersedes old read-tier bridge test |
| Storage-key id scheme | `tests/core/node/test_promotion_storage_key.py`, `test_canonical_key.py` | ADR 0014 (former-0015 amendment) |
| Widget-selection port contract | `tests/core/test_settings/test_widget_stamping.py`, `tests/ui/widget/test_select_widget_options.py` | |
| Promote/demote UI | `tests/ui/menu/test_promote_demote_menu.py`, `tests/ui/panel/test_promoted_row_state.py` | |

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
