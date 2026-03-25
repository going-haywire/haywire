# Module: haywire-core / UI

**Path:** `packages/haywire-core/src/haywire/ui/`
**Import as:** `haywire.ui.*`

---

## Scope & Purpose

The core UI framework layer. Provides the base classes, registries, and machinery for the
multi-editor workspace system — but does **not** contribute any concrete editors or panels
(those live in haybale-studio). Also owns the graph canvas (Vue/NiceGUI hybrid), widget
system, theme/skin registries, session management, and the app shell layout.

---

## Folder Architecture

```
haywire/ui/
├── app_shell.py            # AppShell — TopBar+ActivityBar+Left/Middle/Right/Bottom areas
├── context.py              # SessionContext, InteractionMode
├── context_events.py       # ContextChangedEvent, ContextChangeType enum
├── session.py              # Session — per-browser-connection state
├── session_manager.py      # SessionManager — tracks all sessions, broadcast_data_mutation
├── console_bridge.py       # Console output bridge to UI
├── protocols.py            # UI protocol interfaces
├── utils.py                # Shared UI helpers
│
├── editor/                 # Editor framework (base + registry)
│   ├── base.py             # BaseEditor — abstract, render(context) contract
│   ├── decorator.py        # @editor(registry_id=...) decorator
│   ├── registry.py         # EditorTypeRegistry — get_by_key() / get_by_id()
│   └── identity.py         # EditorIdentity
│
├── panel/                  # Panel framework
│   ├── base.py             # BasePanel — abstract, render(context) contract
│   ├── decorator.py        # @panel(editor=..., scope=...) decorator
│   ├── registry.py         # PanelRegistry — get_panels(editor_key, context_str)
│   ├── scope.py            # ScopeDescriptor — scope tab metadata
│   └── identity.py         # PanelIdentity
│
├── workspace/              # Workspace layout persistence
│   ├── workspace_state.py  # WorkspaceState, area state constants (_K_* keys)
│   └── manager.py          # WorkspaceManager — JSON persistence in .haywire/workspaces.json
│
├── graph_canvas/           # Vue-based graph canvas (node + edge rendering)
│   ├── graph_canvas_manager.py    # GraphCanvasManager — main canvas controller
│   ├── graph_canvas_vue.py        # Vue component bridge
│   ├── event_definitions.py       # Canvas event type definitions
│   ├── event_generators.py        # Converts graph changes → canvas events
│   ├── event_handlers.py          # Handles incoming canvas events → graph mutations
│   ├── node_menu_builder.py       # Right-click node menu construction
│   ├── popup.py                   # Popup base
│   ├── popup_context_menu.py      # Context menu popup
│   └── connection_info_popup.py   # Edge/connection detail popup
│
├── pan_zoom/               # Pan+zoom viewport
│   ├── zoom_pan_vue.py     # Vue zoom-pan component
│   ├── mini_map_vue.py     # Minimap Vue component
│   ├── minimap.py          # Minimap controller
│   └── zoom_pan_test.py    # Zoom-pan playground
│
├── themes/                 # Theme system
│   ├── workbench.py        # WorkbenchTheme — CSS token palette
│   ├── node_theme.py       # NodeTheme — per-node-type colouring
│   ├── registry.py         # ThemeRegistry
│   ├── decorator.py        # @workbench_theme / @node_theme decorators
│   ├── icons.py            # Icon constants
│   └── data/               # TOML palette data files
│
├── skin/                   # Node skin (visual shape/renderer per node)
│   ├── base.py             # BaseSkin
│   ├── decorator.py        # @skin decorator
│   ├── factory.py          # SkinFactory
│   ├── interface.py        # ISkin protocol
│   └── registry.py         # SkinRegistry (skins)
│
├── widget/                 # Port widget system (inline port controls)
│   ├── base.py             # BaseWidget
│   ├── simple.py           # Built-in simple widgets (text, number, toggle, etc.)
│   ├── binding.py          # Widget ↔ port value binding
│   ├── converters.py       # Value converters for widgets
│   ├── decorator.py        # @widget decorator
│   ├── factory.py          # WidgetFactory
│   ├── factory_interface.py
│   ├── globals.py          # Widget globals/config
│   ├── identity.py         # WidgetIdentity
│   ├── interface.py        # IWidget protocol
│   └── registry.py         # WidgetRegistry
│
├── components/             # Reusable NiceGUI UI components
│   └── number_drag.py      # NumberDrag — drag-to-change number input widget
│
├── prefs/                  # UI preference settings (use settings system)
│   ├── canvas.py           # Canvas prefs
│   ├── debug.py            # Debug prefs
│   ├── edge_ui.py          # Edge rendering prefs
│   ├── editor.py           # Editor prefs
│   ├── execution.py        # Execution prefs
│   ├── minimap.py          # Minimap prefs
│   ├── node_ui.py          # Node rendering prefs
│   └── workbench.py        # Workbench prefs
│
├── errors/                 # UI error display
│   ├── error_info.py       # ErrorInfo dataclass
│   └── haywire_exception.py # UI exception types
│
├── ui_node.py              # UINode — NiceGUI node card renderer
├── ui_edge.py              # UIEdge — NiceGUI edge renderer
└── ui_nodecard.py          # NodeCard widget
```

---

## Always-load vs On-demand

**Always-load** (for any UI work):
- `context.py` — SessionContext is passed everywhere; understand its fields first
- `context_events.py` — how context changes propagate between editors
- `editor/base.py` + `editor/registry.py` — editor base contract and lookup
- `panel/base.py` + `panel/registry.py` — panel base contract and lookup
- `panel/scope.py` — scope tab system (replaces old `context=` string)
- `app_shell.py` — overall layout and area rendering

**On-demand**:
- `graph_canvas/` — only when working on the canvas or node/edge rendering
- `workspace/` — only when working on workspace persistence
- `themes/` + `skin/` — only when working on visual appearance
- `widget/` — only when working on port inline controls
- `prefs/` — only when working on UI settings

---

## Rules & Boundaries

- **editor_key vs registry_key**: All area state values use the FULL registry key
  (`__system__:editor:<id>`), NOT short IDs. Constants are in `workspace/workspace_state.py`
  as `_K_*` module-level constants. `EditorTypeRegistry.get_by_key(full_key)` is primary lookup.
- **Panel lookup**: `panel_registry.get_panels(editor_key, context_str)` — `editor_key` is the
  short `registry_id`, not the full `registry_key`.
- **NiceGUI async rule**: Return coroutines from `on_click` lambdas directly — do NOT wrap in
  `asyncio.ensure_future()`. NiceGUI detects the returned Awaitable and wraps with slot context.
  Background tasks creating new UI must enter the container first: `with self._my_container:`.
- **Multi-scope panels**: `@panel(scope=['node', 'graph'])` registers under both tabs.
- **Active theme**: session-scoped in `SessionContext.active_workbench_theme_id` — resets to
  settings default on reconnect.
- **No graph mutation** from within panel/editor render methods — use context events.

---

## Source of Truth

| Concern | File |
|---------|------|
| Session state | `context.py` — `SessionContext` |
| Context change events | `context_events.py` — `ContextChangeType` |
| Editor registry lookup | `editor/registry.py` — `get_by_key()` |
| Panel scope system | `panel/scope.py` — `ScopeDescriptor` |
| Workspace area keys | `workspace/workspace_state.py` — `_K_*` constants |
| App layout | `app_shell.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — imports graph, node, edge, type, settings, DI APIs

## Depended on by

- [haywire-studio.md](haywire-studio.md) — wires app shell and session management
- [haybale-studio.md](haybale-studio.md) — contributes concrete editors and panels
