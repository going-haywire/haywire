# Module: tests

**Path:** `tests/`
**Run with:** `uv run pytest`

---

## Scope & Purpose

The full test suite covering core engine, settings, graph/edge mechanics, execution, UI layer,
canvas handlers, panel rendering, and integration smoke tests. Split into `tests/core/` (headless,
fast) and `tests/ui/` (NiceGUI, Playwright, slower).

Major changes since last map:
- `tests/ui/harness/` added — full NiceGUI test harness (routes, conftest, Playwright fixtures)
- `tests/ui/test_canvas_handlers/` added — handler unit tests for all 4 handler subpackages
- `tests/core/test_debug/` added — logging configurator tests
- `tests/core/test_graph/test_canvas_expansion.py` added
- `tests/core/test_settings/` heavily restructured: removed `test_chain.py`, `test_descriptors.py`,
  `test_holder_cache.py`, `test_namespace_sub.py`, `test_schema.py`, `test_sub_holders.py`;
  added `test_schema_rebasing.py`; `test_settings.py` massively expanded (+500 lines)

---

## Folder Architecture

```
tests/
├── conftest.py                         # Global pytest fixtures (DI setup)
├── test_init_scaffolding.py            # CLI `haywire init` integration test
├── test_smoke.py                       # Smoke test (app starts, basic graph runs)
│
├── core/                               # Headless core tests
│   ├── conftest.py                     # Core-level fixtures
│   ├── test_reactive.py                # Reactive property descriptor tests
│   ├── test_debug/
│   │   └── test_logging_configurator.py # LoggingConfigurator tests
│   ├── test_execution/
│   │   └── test_interpreter.py         # VM / interpreter tests
│   ├── test_graph/
│   │   ├── test_base.py                # Graph add/remove node/edge
│   │   ├── test_canvas_expansion.py    # Canvas bounds/expansion tests (new)
│   │   └── test_edges.py               # Edge lifecycle, lazy, adapter chain
│   ├── test_libraries/
│   │   └── test_registries.py          # Library/node/type registry tests
│   ├── test_node/
│   │   ├── test_base.py                # BaseNode port declarations
│   │   ├── test_decorator.py           # @node decorator
│   │   └── test_factory.py             # NodeFactory
│   └── test_settings/
│       ├── test_hot_reload.py          # Settings hot-reload
│       ├── test_schema_rebasing.py     # Schema rebasing (new)
│       └── test_settings.py            # Main settings system tests (large, ~600+ lines)
│
├── ui/                                 # NiceGUI UI tests
│   ├── harness/                        # Full NiceGUI test harness
│   │   ├── app.py                      # Test app factory
│   │   ├── conftest.py                 # Playwright fixtures
│   │   ├── routes.py                   # Test routes / page definitions
│   │   ├── test_graph_context_menu.py  # Context menu integration tests
│   │   ├── test_interaction.py         # Canvas interaction integration tests
│   │   ├── test_mirror.py              # Settings mirror tests
│   │   ├── test_structural.py          # Structural/DOM tests
│   │   ├── test_validation.py          # Validation UI tests
│   │   └── test_widgets.py             # Widget rendering tests
│   ├── test_canvas_handlers/           # Handler unit tests
│   │   ├── test_context_menu_handlers.py
│   │   ├── test_create_node_panel.py
│   │   ├── test_event_routing.py
│   │   ├── test_haybale_context_menu_panels.py
│   │   ├── test_interaction_handlers.py
│   │   ├── test_selection_handlers.py
│   │   ├── test_session_context_menu_provider.py
│   │   └── test_visual_layer_handlers.py
│   ├── test_app_shell.py               # AppShell layout tests
│   ├── test_console_bridge.py
│   ├── test_editor_registry.py
│   ├── test_node_theme.py
│   ├── test_panel_registry.py
│   ├── test_session_context.py
│   ├── test_theme_registry.py
│   ├── test_workbench_theme.py
│   ├── test_workspace_defaults.py      # WorkspaceDefaults tests (new)
│   └── test_workspace_state.py
│
└── libraries/                          # Library-level tests (if any)
```

---

## Always-load vs On-demand

**Always-load**:
- `conftest.py` — global DI fixture setup pattern
- `core/conftest.py` — how to get a test graph/DI container

**On-demand**:
- `core/test_settings/test_settings.py` — large, load only for settings work
- `ui/harness/` — load only when working on NiceGUI integration tests
- `ui/test_canvas_handlers/` — load only when working on canvas handler logic
- Individual test files for the subsystem you're currently working on

---

## Rules & Boundaries

- **Import order**: always `import haywire.core.graph.editor` before other haywire modules
  in test files to avoid circular import errors.
- **`force_immediate_validation()`** must be called after node setup in tests to flush the
  dirty queue before any assertions on node/edge state.
- **Unit tests** (`-m unit`) are fast, headless. **Integration tests** (`-m integration`) load
  the full library system and are slow.
- `tests/ui/harness/` requires Playwright — run with `uv run pytest tests/ui/harness/`.
- **Coverage target**: 100% — run `uv run pytest --cov` to verify before claiming completion.
- Do not add mocks for the database/graph engine — integration tests must use real instances
  (see `feedback_check_docs_first.md` for the rationale).

---

## Source of Truth

| Concern | File |
|---------|------|
| DI test setup | `conftest.py` + `core/conftest.py` |
| Settings system tests | `core/test_settings/test_settings.py` |
| Edge lifecycle tests | `core/test_graph/test_edges.py` |
| NiceGUI harness entry | `ui/harness/app.py` + `ui/harness/conftest.py` |
| Canvas handler tests | `ui/test_canvas_handlers/` |

---

## Depends on

- [core-engine.md](core-engine.md) — tests import core DI, graph, node, settings APIs
- [core-ui.md](core-ui.md) — UI tests use NiceGUI components
- [haybale-core.md](haybale-core.md) — canvas handler tests use haybale-core panels
- [barn-other.md](barn-other.md) — integration tests load haybale-testing fixture nodes

## Depended on by

Nothing — tests are a leaf in the dependency graph.
