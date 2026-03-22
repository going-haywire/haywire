
# Module: barn / Other Libraries

**Path:** `barn/` (haybale-example, haybale-testing, haybale-visiongraph, haybale-TEST_A)

---

## Scope & Purpose

Additional plugin libraries beyond the core+studio pair. Each follows the same haybale
library structure (`__init__.py` with `@library` + `register_components()`).

---

## Libraries

### haybale-example (`barn/haybale-example/haybale_example/`)

A reference/example library demonstrating how to create a haybale plugin. Contains:
- `nodes/` — example node definitions
- `types/` — example custom types
- `adapters/` — example adapters
- `skins/` — example skin
- `widgets/` — example widget

**Use for:** Learning the library plugin pattern; copy-paste starting point for new libraries.

---

### haybale-testing (`barn/haybale-testing/haybale_testing/`)

Test infrastructure nodes used in the integration test suite.

Key files:
- `nodes/testbed/edge_link_test.py` — `EdgeLinkTestNode` — main integration test node;
  exercises the full edge link/unlink/detach lifecycle
- `nodes/testbed/dynamic_port_test.py` — `DynamicPortTestNode` — push/pop dynamic port tests
- `themes/` — test-specific theme overrides

**Use for:** Writing or debugging edge lifecycle and dynamic port integration tests.
Do NOT use in production graphs.

---

### haybale-visiongraph (`barn/haybale-visiongraph/haybale_visiongraph/`)

Vision/camera nodes for image processing pipelines.

Structure:
- `nodes/` — camera capture, frame processing nodes
- `types/` — `FRAME` type and related
- `adapters/` — frame format adapters
- `skins/` — vision node skins
- `widgets/` — vision-specific widgets
- `docs/` + `help/` — library-specific documentation

**Use for:** Video/camera/image processing use cases.

---

### haybale-TEST_A (`barn/haybale-TEST_A/haybale_test_a/`)

A minimal test library scaffold (similar structure to haybale-example).
Used during development for isolated feature testing.

**Use for:** Scratch/experimental library work. Not intended for production.

---

## Shared Library Structure (all haybale libraries)

```
haybale_<name>/
├── __init__.py         # @library decorator + register_components()
├── nodes/              # Node class definitions
├── types/              # Custom type definitions
├── adapters/           # Type adapters
├── skins/              # Node skin renderers
├── widgets/            # Port widgets
└── themes/             # Theme contributions (optional)
```

---

## Rules & Boundaries

- Each library is independently installable as a uv package with its own `pyproject.toml`.
- Library discovery is via `importlib.metadata.entry_points(group='haywire.libraries')`.
- Hot-reload works for editable installs via `file_watcher=True` on `@library`.
- Libraries must NOT import from each other except through the core type registry.
- `haybale-testing` nodes must never be registered in a production DI context.

---

## Depends on

- [core-engine.md](core-engine.md) — BaseLibrary, BaseNode, port types
- [haybale-core.md](haybale-core.md) — primitive types referenced by most libraries

## Depended on by

- [tests.md](tests.md) — test suite uses haybale-testing nodes
