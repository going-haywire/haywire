# Module: haybale-core

**Path:** `barn/haybale-core/haybale_core/`
**Import as:** `haybale_core`
**Plugin group:** `haywire.libraries`

---

## Scope & Purpose

The standard node library. Provides built-in nodes (Tick, ForLoop, Switch, BeginPlay,
EmitCallback, MergeCallback, CustomCallback, Shutdown, PrintNode, ErrorNode), core type
adapters, widgets, skins, and UI panels for the graph canvas. Loaded as a `haywire.libraries`
entry point.

Major changes since last map:
- `themes/` emptied — NodeTheme and WorkbenchTheme implementations moved to `haybale-studio`.
- `panels/` significantly expanded: context menu panels added, edge panels added,
  node settings/skin/status panels added.
- `settings/` added: `node_skin_settings.py` for per-node skin overrides.
- `skins/node_skin.py` heavily refactored (~183 lines changed).

---

## Folder Architecture

```
haybale_core/
├── __init__.py                 # BaseLibrary subclass, register_components()
│
├── nodes/                      # Built-in node implementations
│   ├── begin_play.py           # BeginPlay — graph start trigger
│   ├── custom_callback.py      # CustomCallback — user-defined callback
│   ├── emit_callback.py        # EmitCallback — fires a callback
│   ├── error_node.py           # ErrorNode — error injection
│   ├── for_loop.py             # ForLoop — sequence loop with LOOPBACK
│   ├── merge_callback.py       # MergeCallback — merges multiple callbacks
│   ├── print_node.py           # PrintNode — debug output
│   ├── shutdown.py             # Shutdown — graceful stop
│   ├── switch.py               # Switch — conditional branching
│   └── tick.py                 # Tick — periodic event source
│
├── panels/                     # Canvas panel contributions
│   ├── canvas_settings.py      # Canvas settings panel
│   ├── edge_panels.py          # Edge info/config panels
│   ├── graph_info_panel.py     # Graph info panel
│   ├── node_ports_panel.py     # Node ports panel
│   ├── node_props_panel.py     # Node properties panel
│   ├── node_settings.py        # Node settings panel
│   ├── node_status.py          # Node status panel
│   └── context_menu/           # Context menu panel contributions
│       ├── __init__.py
│       ├── create_node_panel.py   # Create node context menu panel
│       ├── node_actions.py        # Node action items
│       └── selection_actions.py   # Selection action items
│
├── settings/                   # haybale-core settings
│   └── node_skin_settings.py   # NodeSkinSettings — per-node skin config
│
├── skins/                      # Node skin implementations
│   ├── node_skin.py            # NodeSkin — base node skin
│   ├── default_skin.py         # DefaultSkin — standard visual style
│   └── error_skin.py           # ErrorSkin — error state visual style
│
├── themes/                     # Theme stubs (implementations moved to haybale-studio)
│
├── adapters/                   # Type adapter contributions
│   ├── basic_adapters.py       # Primitive-to-primitive adapters
│   └── compound_adapters.py    # Compound type adapters
│
├── types/                      # Type contributions
│   ├── array_type.py           # Array type
│   ├── pooled_type.py          # Pooled type
│   └── specs.py                # Type spec helpers
│
├── widgets/                    # Widget contributions
│   └── basic_widgets.py        # Basic port widgets (bool, int, float, str, etc.)
│
└── editors/                    # Any graph-canvas-adjacent editor contributions
```

---

## Always-load vs On-demand

**Always-load**:
- `__init__.py` — registration path
- `nodes/` directory listing — to know which nodes exist
- `skins/node_skin.py` — base skin contract used by all nodes

**On-demand**:
- Individual node files — only when modifying that node
- `panels/context_menu/` — only when working on canvas context menu
- `panels/edge_panels.py` — only when working on edge panel UI
- `settings/node_skin_settings.py` — only when working on per-node skin overrides
- `adapters/`, `types/`, `widgets/` — only for cross-type conversion or widget work

---

## Rules & Boundaries

- **themes/ is now empty** — do not add theme implementations here; they belong in `haybale-studio`.
- All components registered in `register_components()` in `__init__.py`.
- Node workers must match port ID naming conventions (see core-engine rules).
- Panels contributed here appear in the graph canvas context — follow `@panel` + `BasePanel` pattern.
- Skin settings use the settings system — see `settings/node_skin_settings.py` as reference.

---

## Source of Truth

| Concern | File |
|---------|------|
| Library registration | `__init__.py` |
| Node list | `nodes/` directory |
| Base node skin | `skins/node_skin.py` |
| Per-node skin settings | `settings/node_skin_settings.py` |
| Context menu panels | `panels/context_menu/` |

---

## Depends on

- [core-engine.md](core-engine.md) — BaseNode, types, settings, DI
- [core-ui.md](core-ui.md) — BasePanel, BaseSkin, widget APIs

## Depended on by

- [haybale-studio.md](haybale-studio.md) — studio depends on haybale-core nodes/types
- [tests.md](tests.md) — core node tests and canvas handler tests use haybale-core
