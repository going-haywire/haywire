# Module: haywire-core / UI

**Path:** `packages/haywire-core/src/haywire/ui/`
**Import as:** `haywire.ui.*`

---

## Scope & Purpose

The NiceGUI-based UI framework layer. Owns the app shell, workspace/session model, graph canvas,
editor/panel/widget registries, themes, skins, and all Vue/Quasar components. Depends on
`haywire.core` but must not be depended on by core.

Major structural changes since last map:
- `app_shell.py` split into `app/shell.py` (825-line refactor)
- `pan_zoom/` module removed; replaced by `components/zoom/` and `components/minimap/`
- `graph_canvas/` handlers extracted into `handlers/` subpackage
- `popup_context_menu.py` collapsed into `popup.py`
- `elements.py` added (~670 lines of shared UI element builders)
- `panel/render_utils.py` added for panel rendering helpers
- `ui/prefs/` slimmed (removed debug.py, execution.py, minimap.py, node_ui.py, workbench.py)

---

## Folder Architecture

```
haywire/ui/
├── __init__.py
├── elements.py                 # Shared NiceGUI element builders (~670 lines)
├── utils.py                    # UI utilities
├── protocols.py                # UI protocol interfaces
├── context.py                  # UIContext — per-session context container
├── context_events.py           # UIContext event definitions
├── console_bridge.py           # Console output bridge to UI
├── session.py                  # Session model
├── session_manager.py          # SessionManager — create/destroy sessions
├── ui_edge.py                  # UIEdge — visual edge representation
├── ui_node.py                  # UINode — visual node representation
├── ui_nodecard.py              # UINodeCard — node card widget
│
├── app/                        # App shell (was app_shell.py)
│   └── shell.py                # HaywireAppShell — top-level layout (825 lines)
│
├── components/                 # Reusable Vue/NiceGUI components
│   ├── graph/                  # Graph canvas Vue component
│   │   ├── canvas.py           # Python wrapper
│   │   ├── canvas.vue          # Vue component
│   │   └── generators.py       # JS event/handler generators
│   ├── minimap/                # Minimap component (replaced pan_zoom/minimap)
│   │   ├── minimap.py          # MinimapCanvas Python class
│   │   ├── minimap.vue         # Vue component
│   │   └── settings.py         # MinimapSettings
│   ├── zoom/                   # Zoom/pan container (replaced pan_zoom/zoom_pan)
│   │   ├── pan.py              # ZoomPanContainer Python class
│   │   ├── pan.vue             # Vue component
│   │   └── settings.py         # ZoomPanSettings
│   └── number/                 # Number drag widget
│       ├── drag.py
│       └── drag.vue
│
├── graph_canvas/               # Graph canvas manager and interaction
│   ├── graph_canvas_manager.py # GraphCanvasManager — orchestrates canvas
│   ├── event_definitions.py    # Canvas event type definitions
│   ├── event_handlers.py       # Base event handler routing
│   ├── popup.py                # Connection info popup (merged popup_context_menu)
│   ├── connection_info_popup.py # Edge/connection info popup
│   ├── node_menu_builder.py    # Node context menu builder
│   └── handlers/               # Extracted handler subpackage
│       ├── context_menu.py     # Context menu handler
│       ├── interaction.py      # Mouse/keyboard interaction handler
│       ├── selection.py        # Node selection handler
│       └── visual_layer.py     # Visual layer (rendering, node/edge draw) handler
│
├── editor/                     # Editor registry
│   ├── base.py                 # BaseEditor
│   ├── decorator.py            # @editor decorator
│   ├── identity.py             # EditorIdentity
│   └── registry.py             # EditorRegistry
│
├── panel/                      # Panel registry
│   ├── base.py                 # BasePanel
│   ├── decorator.py            # @panel decorator
│   ├── identity.py             # PanelIdentity
│   ├── registry.py             # PanelRegistry
│   ├── render_utils.py         # Panel rendering utilities (~500 lines)
│   └── scope.py                # Panel scope enum
│
├── widget/                     # Widget registry
│   ├── base.py                 # BaseWidget
│   ├── binding.py              # Widget data binding
│   ├── converters.py           # Value converters
│   ├── decorator.py            # @widget decorator
│   ├── factory.py              # WidgetFactory
│   ├── factory_interface.py    # IWidgetFactory protocol
│   ├── globals.py              # Global widget state
│   ├── identity.py             # WidgetIdentity
│   ├── interface.py            # IWidget protocol
│   ├── registry.py             # WidgetRegistry
│   └── simple.py               # SimpleWidget base
│
├── skin/                       # Node skin system
│   ├── base.py                 # BaseSkin
│   ├── decorator.py            # @skin decorator
│   ├── factory.py              # SkinFactory
│   ├── interface.py            # ISkin protocol
│   ├── registry.py             # SkinRegistry
│   └── settings.py             # SkinSettings
│
├── themes/                     # Theme system
│   ├── __init__.py
│   ├── decorator.py            # @theme decorator
│   ├── icons.py                # Icon constants
│   ├── node_theme.py           # NodeTheme base
│   ├── registry.py             # ThemeRegistry
│   └── workbench.py            # WorkbenchTheme base
│
├── prefs/                      # UI preferences (settings wrappers for UI state)
│   ├── canvas.py               # Canvas prefs
│   ├── edge_ui.py              # Edge rendering prefs
│   ├── editor.py               # Editor prefs
│   └── __init__.py
│
├── errors/                     # UI error handling
│   ├── error_info.py
│   └── haywire_exception.py
│
└── workspace/                  # Workspace state
    ├── __init__.py
    ├── manager.py              # WorkspaceManager
    └── workspace_state.py      # WorkspaceState
```

---

## Always-load vs On-demand

**Always-load** (understand these first for any UI work):
- `app/shell.py` — top-level layout, understand how editors/panels mount
- `context.py` — UIContext, the per-session dependency container
- `graph_canvas/graph_canvas_manager.py` — how the canvas manages nodes/edges
- `panel/base.py` + `panel/registry.py` — panel system contract
- `editor/base.py` + `editor/registry.py` — editor system contract
- `themes/workbench.py` + `themes/node_theme.py` — theme base classes

**On-demand**:
- `graph_canvas/handlers/` — only when debugging canvas interaction behaviour
- `components/zoom/` + `components/minimap/` — only when working on canvas pan/zoom/minimap
- `widget/` — only when adding new port type widgets
- `skin/` — only when adding new node skins
- `panel/render_utils.py` — only when building or debugging complex panel layouts
- `elements.py` — when adding shared NiceGUI element patterns

---

## Rules & Boundaries

- **NiceGUI slot stack rule**: never create NiceGUI elements outside the active slot context.
  See `feedback_nicegui_async.md` for the 3 safe async patterns.
- **`pan_zoom/` is deleted** — use `components/zoom/pan.py` (ZoomPanContainer) and
  `components/minimap/minimap.py` (MinimapCanvas) instead.
- **`app_shell.py` is deleted** — use `app/shell.py` (HaywireAppShell).
- **`popup_context_menu.py` is deleted** — merged into `popup.py`.
- **`prefs/` modules removed**: `debug.py`, `execution.py`, `minimap.py`, `node_ui.py`,
  `workbench.py` — these settings moved to settings system in core/haybale-studio.
- **compact-fields CSS class** available for tight panel layouts — see `feedback_nicegui_compact_panels.md`.
- Panels use `@panel` decorator + `BasePanel`; editors use `@editor` decorator + `BaseEditor`.
- `@editor` / `EditorIdentity` kwargs of note:
  - `opens` (enum `OpenBehavior`): instance-creation behavior. `required`
    auto-populates and is uncloseable; `on_context` is a singleton tab
    opened on demand (content mirrors session context); `on_payload` is
    one tab per distinct payload, opened on demand (payload drives content).
  - `context_field` (optional): `SessionContext` attribute the shell
    mirrors `binding.payload` into when the active main tab changes.
- Only `opens='required'` main editors auto-populate; `on_context` and
  `on_payload` editors start with zero tabs.
- All Vue components in `components/` should have matching `.py` wrapper and `.vue` file.

---

## Source of Truth

| Concern | File |
|---------|------|
| App shell layout | `app/shell.py` |
| Canvas orchestration | `graph_canvas/graph_canvas_manager.py` |
| Panel registry | `panel/registry.py` |
| Editor registry | `editor/registry.py` |
| Theme registry | `themes/registry.py` |
| ZoomPan component | `components/zoom/pan.py` |
| Minimap component | `components/minimap/minimap.py` |
| Shared UI elements | `elements.py` |
| Panel render helpers | `panel/render_utils.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — imports graph, node, types, settings, execution APIs

## Depended on by

- [haywire-studio.md](haywire-studio.md) — app mounts editors/panels via UI registries
- [haybale-studio.md](haybale-studio.md) — contributes editors, panels, skins to UI registries
- [haybale-core.md](haybale-core.md) — contributes panels and widgets
- [tests.md](tests.md) — UI tests use harness that instantiates the app shell
