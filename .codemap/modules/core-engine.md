# Module: haywire-core / Engine

**Path:** `packages/haywire-core/src/haywire/core/`
**Import as:** `haywire.core.*`

---

## Scope & Purpose

The runtime heart of Haywire. Owns the graph model, all port/edge mechanics, the type system,
the execution pipeline (assembly → VM), the DI container, the settings system, and undo/redo.
Nothing in this module should depend on UI or NiceGUI — it is headless and testable in isolation.

---

## Folder Architecture

```
haywire/core/
├── __init__.py
├── utils.py                    # shared helpers
│
├── di/                         # Dependency injection
│   ├── config.py               # HaywireModule — main injector, all singletons
│   ├── test_config.py          # TestHaywireModule — test-safe injector
│   └── context.py              # DI context helpers
│
├── graph/                      # Graph model (thin coordinator)
│   ├── base.py                 # Graph class — add/remove nodes & edges
│   ├── editor.py               # GraphEditor — higher-level edit operations
│   ├── types.py                # Graph-related dataclasses/enums
│   └── validation.py           # Graph-level structural checks
│
├── node/                       # Node class hierarchy
│   ├── base.py                 # BaseNode — port declaration, rejig, worker
│   ├── node_wrapper.py         # NodeWrapper — live runtime node instance
│   ├── factory.py              # NodeFactory — instantiates nodes from registry
│   ├── decorator.py            # @node decorator
│   ├── registry.py             # NodeRegistry
│   ├── behavior.py             # NodeBehavior enum (DATA, CONTROL, EVENT, OUTPUT, LOOPBACK)
│   ├── dataclasses.py          # NodeData, PortData transfer objects
│   ├── identity.py             # NodeIdentity
│   ├── properties.py           # Node UI properties (position, label, etc.)
│   └── user_data.py            # Arbitrary per-node user data
│
├── edge/                       # Edge lifecycle
│   ├── edge.py                 # Edge — link/unlink/detach, three-tier lifecycle
│   └── edge_wrapper.py         # EdgeWrapper — runtime edge with lazy flag
│
├── types/                      # Port type system
│   ├── base.py                 # PrimitiveType, BaseType, CompoundType base classes
│   ├── port.py                 # DataPort — the port descriptor (DataPort.__post_init__ rules)
│   ├── pipe.py                 # Pipe — eager push / lazy pull_lazy transport
│   ├── interface.py            # TypeInterface protocol
│   ├── registry.py             # TypeRegistry
│   ├── decorator.py            # @type_def decorator
│   ├── enums.py                # FlowType (DATA, CONTROL, CALLBACK, NONE)
│   ├── fields.py               # Port field helpers
│   ├── identity.py             # TypeIdentity
│   ├── event.py                # Port event definitions
│   └── utils.py                # Adapter chain BFS resolution
│
├── adapter/                    # Type adapters (cross-type conversion)
│   ├── base.py                 # BaseAdapter
│   ├── factory.py              # AdapterFactory
│   └── registry.py             # AdapterRegistry
│
├── assembly/                   # Graph → executable flow
│   ├── flow_assembly_manager.py # FlowAssemblyManager — orchestrates assembly
│   ├── control_flow_builder.py # Builds control flow DAG from graph
│   └── data_flow_builder.py    # Builds per-control-node data dependency DAG
│
├── execution/                  # VM and scheduling
│   ├── vm.py                   # VM — two-stack interpreter (done-stack + loopback-stack)
│   ├── interpreter.py          # Interpreter — drives the VM
│   ├── interpreter_loop_manager.py # Loop management for sequences/LOOPBACK nodes
│   ├── flow.py                 # LocalizedDataFlow — data flow for one control node
│   ├── execution_context.py    # ExecutionContext passed to worker()
│   ├── scheduler.py            # Async execution scheduler
│   ├── callback_manager.py     # CALLBACK port management
│   └── event_source.py         # EVENT node source registry
│
├── validation/                 # Structural validation
│   ├── interface.py            # IValidator protocol
│   └── structural_validator.py # NodeWrapper dirty-queue validator
│
├── settings/                   # Settings system
│   ├── schema.py               # NodeSettings / LibrarySettings base + setting() descriptor
│   ├── descriptors.py          # field() / shadow() / watch() descriptors
│   ├── settings.py             # Settings — live instance
│   ├── registry.py             # SettingsRegistry
│   ├── chain.py                # Three-tier TOML chain resolution
│   ├── enums.py                # SettingMode, SettingScope
│   ├── types.py                # Color, Icon type aliases
│   ├── value.py                # SettingValue container
│   └── decorator.py            # @library_settings decorator
│
├── library/                    # Plugin library system
│   ├── base.py                 # BaseLibrary — register_components() contract
│   ├── decorator.py            # @library decorator
│   ├── discovery.py            # entry_points discovery
│   ├── registry.py             # LibraryRegistry
│   ├── file_watcher.py         # Hot-reload file watcher
│   ├── identity.py             # LibraryIdentity
│   └── utils.py                # Library helpers
│
├── registry/                   # Generic registry base
│   ├── base.py                 # BaseRegistry[T]
│   ├── folder_scan.py          # Folder scanning to auto-register components
│   ├── identity.py             # RegistryIdentity base
│   ├── lifecycle_event.py      # Registry lifecycle events
│   └── dependency_graph.py     # Dependency ordering for registries
│
├── property/                   # Node property bag
│   ├── base.py                 # PropertyBase
│   ├── bag.py                  # PropertyBag — stores node UI properties
│   └── descriptor.py           # Property descriptor
│
└── undo/                       # Undo/redo
    ├── history_manager.py      # HistoryManager
    ├── interfaces.py           # IHistoryManager protocol
    ├── base_action.py          # BaseAction
    ├── no_op_history_manager.py
    ├── config.py               # Undo DI config
    └── actions/                # Concrete action implementations
```

---

## Always-load vs On-demand

**Always-load** (understand these first for any engine work):
- `di/config.py` — what singletons exist and how they wire together
- `node/base.py` — how nodes declare ports and workers
- `node/node_wrapper.py` — how nodes live at runtime
- `edge/edge.py` — three-tier lifecycle (link → unlink → detach)
- `types/port.py` — DataPort and the hardcoded port rules
- `types/pipe.py` — how data actually flows (eager push / lazy pull)

**On-demand**:
- `assembly/` — only when working on graph-to-execution pipeline
- `execution/vm.py` — only when debugging execution behaviour
- `settings/` — only when working on the settings system
- `undo/` — only when working on undo/redo
- `adapter/` — only when working on cross-type conversions

---

## Rules & Boundaries

- **No UI imports** — this package must remain headless; no NiceGUI, no haywire.ui imports.
- **Port rules are hardcoded** in `DataPort.__post_init__` — never set `allow_multiple` manually
  for DATA or EXEC ports; only CALLBACK ports are freely configurable.
- **Worker parameter names must exactly match inlet port IDs.**
- **Pooled inlets** return `dict[upstream_node_id, value]` to worker, not a single value.
- **Dirty queue ordering**: `NODE_ADDED` (priority 90) is enqueued by `create_node_wrapper()`.
  Tests must call `force_immediate_validation()` to flush before asserting anything.
- **Displacement is asymmetric**: inlet informs outlet on displacement; outlet does NOT inform inlet.
- **`is_lazy` is per-edge**, not per-port. Pipes own transport; lazy = `pull_lazy()` always-latest.
- **Adapter chain** is resolved at connection time with sample data; connection is rejected if chain fails.

---

## Source of Truth

| Concern | File |
|---------|------|
| All DI singletons | `di/config.py` — `HaywireModule` |
| Port rules | `types/port.py` — `DataPort.__post_init__` |
| Node type determination | `node/behavior.py` — `NodeBehavior` |
| FlowType enum | `types/enums.py` |
| Edge lifecycle | `edge/edge.py` |
| Assembly pipeline | `assembly/flow_assembly_manager.py` |
| VM execution | `execution/vm.py` |
| Settings schema | `settings/schema.py` |

---

## Depends on

Nothing external outside the Python stdlib and `injector`. Self-contained.

## Depended on by

- [core-ui.md](core-ui.md) — UI layer imports core for graph, nodes, types, settings
- [haywire-studio.md](haywire-studio.md) — app wires DI and uses graph/library APIs
- [haybale-studio.md](haybale-studio.md) — studio plugin extends core registry types
- [haybale-core.md](haybale-core.md) — node library uses `haywire.core` node/type APIs
- [tests.md](tests.md) — tests use `di/test_config.py` and core APIs directly
