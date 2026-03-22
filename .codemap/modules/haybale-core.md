# Module: haybale-core

**Path:** `barn/haybale-core/haybale_core/`
**Import as:** `haybale_core`
**Plugin group:** `haywire.libraries`

---

## Scope & Purpose

The standard built-in node library. Provides fundamental control-flow and utility nodes
(Tick, BeginPlay, ForLoop, Switch, Print, etc.), the built-in compound types (Array, Pooled),
type adapters for primitives, the default node skin and themes, and basic port widgets.

---

## Folder Architecture

```
haybale_core/
├── __init__.py             # BaseLibrary subclass + register_components()
│
├── nodes/                  # Built-in node definitions
│   ├── tick.py             # TickNode — recurring timer event
│   ├── begin_play.py       # BeginPlayNode — fires once at startup
│   ├── shutdown.py         # ShutdownNode — app shutdown trigger
│   ├── for_loop.py         # ForLoopNode — LOOPBACK loop node
│   ├── switch.py           # SwitchNode — conditional branching
│   ├── print_node.py       # PrintNode — console output
│   ├── custom_callback.py  # CustomCallbackNode — user-defined callback
│   ├── emit_callback.py    # EmitCallbackNode — fires a callback port
│   └── merge_callback.py   # MergeCallbackNode — merges multiple callbacks
│
├── types/                  # Built-in compound types
│   ├── specs.py            # Primitive type specs (FLOAT, INT, BOOL, STRING, etc.)
│   ├── array_type.py       # ArrayType[T] — typed array
│   └── pooled_type.py      # PooledType[T] — pooled multi-inlet collection
│
├── adapters/               # Type adapters
│   ├── basic_adapters.py   # Primitive-to-primitive adapters (e.g. INT→FLOAT)
│   └── compound_adapters.py # Compound type adapters
│
├── skins/                  # Node visual renderers
│   ├── default_skin.py     # DefaultSkin — standard node card renderer
│   ├── error_skin.py       # ErrorSkin — placeholder/error node renderer
│   └── node_skin.py        # NodeSkin base for this library
│
├── themes/                 # Theme contributions
│   ├── workbench.py        # Default WorkbenchTheme (haywire-light, haywire-dark)
│   └── node.py             # Default NodeTheme mappings
│
└── widgets/
    └── basic_widgets.py    # Basic port widgets (text input, number, toggle, dropdown)
```

---

## Always-load vs On-demand

**Always-load** (when working with node types or adapters):
- `types/specs.py` — the canonical primitive type definitions (FLOAT, INT, BOOL, etc.)
- `__init__.py` — registration order for nodes, types, adapters, skins, themes, widgets

**On-demand**:
- Individual `nodes/*.py` — load only the node you're modifying
- `adapters/` — load when working on type conversion
- `skins/` — load when working on node visual appearance
- `themes/` — load when working on default theme colours

---

## Rules & Boundaries

- **ForLoopNode is a LOOPBACK node** — uses the VM loopback-stack mechanism; do not
  treat it like a simple DATA node.
- **error_node.py** renders placeholder/error nodes when a library is missing; it must
  remain loadable even when other libraries are absent.
- **Primitive types** (`FLOAT`, `INT`, `BOOL`, `STRING`, etc.) defined in `types/specs.py`
  are the canonical type instances — all other libraries reference these, not re-define them.
- Child → parent type connection is a passthrough (no adapter); parent → child requires
  an explicit adapter registered here or in the consuming library.

---

## Source of Truth

| Concern | File |
|---------|------|
| Primitive types | `types/specs.py` |
| Array / pooled types | `types/array_type.py`, `types/pooled_type.py` |
| Default skin | `skins/default_skin.py` |
| Default themes | `themes/workbench.py`, `themes/node.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — BaseNode, port types, FlowType, DI

## Depended on by

- [haybale-studio.md](haybale-studio.md) — uses primitive types for settings widgets
- [barn-other.md](barn-other.md) — other libraries build on types defined here
- [tests.md](tests.md) — tests import primitive types from here
