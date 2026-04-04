
# Module: barn / Other Libraries

**Path:** `barn/` (haybale-example, haybale-testing, haybale-visiongraph, haybale-TEST_A)

---

## Scope & Purpose

Additional plugin libraries bundled in the monorepo for examples, integration testing,
domain-specific use cases, and development scaffolding. Each is a `haywire.libraries`
entry-point plugin.

---

## Folder Architecture

```
barn/
├── haybale-example/haybale_example/    # Example library (tutorial/reference nodes)
│   ├── __init__.py
│   ├── nodes/                          # Example nodes (e.g. MathOp)
│   ├── skins/                          # Example skins
│   ├── types/                          # Example types (math.py, specs.py)
│   └── widgets/                        # Example widgets
│
├── haybale-testing/haybale_testing/    # Integration test harness library
│   ├── __init__.py
│   ├── nodes/
│   │   ├── testbed/                    # Testbed node implementations
│   │   │   ├── begin_play_node.py
│   │   │   ├── custom_callback_node.py
│   │   │   ├── display_node.py
│   │   │   ├── dynamic_port_test.py
│   │   │   ├── edge_link_test.py
│   │   │   ├── emit_callback_node.py
│   │   │   ├── math_op_node.py
│   │   │   ├── settings_node.py        # Settings-heavy test node
│   │   │   └── test_performance.py
│   │   └── utils/                      # Node test utilities
│   ├── panels/                         # Panel tests
│   │   ├── test_create_node_panel.py
│   │   ├── test_edge_panels.py
│   │   ├── test_node_panels.py
│   │   └── test_selection_panels.py
│   ├── settings/
│   │   └── testing.py                  # TestingSettings
│   ├── adapters/                       # Test adapters
│   ├── skins/                          # Test skins
│   ├── themes/                         # Test themes (node.py, workbench.py)
│   ├── types/                          # Test types
│   └── widgets/                        # Test widgets
│
├── haybale-visiongraph/haybale_visiongraph/  # OpenCV/webcam vision nodes
│   ├── __init__.py
│   ├── nodes/                          # Webcam, frame, stream nodes
│   ├── types/                          # Frame type
│   └── widgets/                        # Streaming viewer widget
│
└── haybale-TEST_A/haybale_test_a/      # Scratch/test library (not for production)
    ├── __init__.py
    ├── adapters/
    └── types/
```

---

## Always-load vs On-demand

**Always-load**:
- `haybale-testing/__init__.py` — understand what test nodes/types are available for tests

**On-demand**:
- `haybale-testing/nodes/testbed/settings_node.py` — reference for settings-heavy nodes
- `haybale-testing/nodes/testbed/edge_link_test.py` — reference for complex edge scenarios
- `haybale-example/` — when adding example nodes or as reference for new node authors
- `haybale-visiongraph/` — only when working on webcam/vision features
- `haybale-TEST_A/` — scratch space, ignore unless specifically directed

---

## Rules & Boundaries

- **haybale-testing** is the integration test fixture library — its nodes/types are loaded
  by the integration test suite. Do not use in production code paths.
- **haybale-TEST_A** is scratch — not a stable API.
- **haybale-visiongraph** requires opencv as an optional dependency — guard imports.
- All libraries follow the `BaseLibrary` + `register_components()` contract.

---

## Source of Truth

| Concern | File |
|---------|------|
| Test fixture nodes | `haybale-testing/nodes/testbed/` |
| Test settings reference | `haybale-testing/settings/testing.py` |
| Example node reference | `haybale-example/nodes/` |
| Vision/webcam nodes | `haybale-visiongraph/nodes/` |

---

## Depends on

- [core-engine.md](core-engine.md) — BaseNode, types, settings APIs
- [core-ui.md](core-ui.md) — BasePanel, BaseSkin, widget APIs (haybale-testing panels)

## Depended on by

- [tests.md](tests.md) — integration tests load haybale-testing nodes/types
