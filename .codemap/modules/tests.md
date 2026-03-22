# Module: tests

**Path:** `tests/`
**Run with:** `uv run pytest`

---

## Scope & Purpose

The integration and unit test suite for the Haywire framework. Tests cover the graph engine,
execution pipeline, node system, settings, and UI. All tests use the headless DI configuration
from `haywire.core.di.test_config`.

---

## Folder Architecture

```
tests/
├── conftest.py                     # Shared fixtures, DI injector setup
├── __init__.py
├── test_smoke.py                   # Quick smoke tests (import, startup)
├── test_init_scaffolding.py        # `haywire init` CLI scaffolding tests
├── README.md                       # Test architecture notes
│
├── core/                           # Core framework tests
│   ├── test_graph/
│   │   ├── test_edge_connections.py # 60+ edge lifecycle integration tests
│   │   └── test_edge_connections.md # Architecture reference doc for edge tests
│   ├── test_execution/             # VM, assembly, scheduler tests
│   ├── test_node/                  # Node creation, port rules, worker tests
│   ├── test_settings/              # Settings system tests
│   └── test_libraries/             # Library discovery, registration tests
│
├── libraries/                      # Library-specific tests
│   └── (per-library test files)
│
└── ui/                             # UI system tests
    └── (editor, panel, workspace tests)
```

---

## Always-load vs On-demand

**Always-load** (before writing any new tests):
- `conftest.py` — understand fixture setup, especially how the DI injector is configured
- `core/test_graph/test_edge_connections.py` — canonical example of integration test structure

**On-demand**:
- Load only the test file for the area you're working on

---

## Rules & Boundaries

- **CRITICAL gotcha**: `create_node_wrapper()` leaves a pending `NODE_ADDED` event (priority 90)
  in the dirty queue. Tests MUST call `force_immediate_validation()` after setup to flush the
  queue before asserting — otherwise lower-priority marks (e.g. `NODE_HOT_RELOADED` at 80)
  are silently dropped.
- **DI in tests**: Use `TestHaywireModule` from `haywire.core.di.test_config`. Library paths
  default to `[]` — explicitly provide test library paths if you need node registration.
- **No NiceGUI**: UI tests must use headless mode; never start the NiceGUI server in tests.
- **haybale-testing nodes** (`EdgeLinkTestNode`, `DynamicPortTestNode`) are the canonical
  test nodes — use them for edge lifecycle and dynamic port tests.
- **Line length**: 109 (same as production code); ruff enforced.
- **Test naming convention**: `test_<thing>_<scenario>` — be specific about what is tested.
- **Do NOT mock the database or graph** — integration tests should use real graph instances.

---

## Source of Truth

| Concern | File |
|---------|------|
| Test DI config | `haywire/core/di/test_config.py` (in core-engine) |
| Edge lifecycle tests | `core/test_graph/test_edge_connections.py` |
| Edge architecture docs | `core/test_graph/test_edge_connections.md` |
| Test fixtures | `tests/conftest.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — all framework APIs under test
- [barn-other.md](barn-other.md) — haybale-testing nodes used in integration tests

## Depended on by

Nothing — tests are the leaf of the dependency graph.
