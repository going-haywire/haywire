# Module: haybale-studio

**Path:** `barn/haybale-studio/haybale_studio/`
**Import as:** `haybale_studio`
**Plugin group:** `haywire.libraries`

---

## Scope & Purpose

The official "studio" haybale library. Contributes all concrete UI — editors, panels, and
scopes — that make up the Haywire workbench. Also provides all library settings (canvas,
execution, debug, etc.). This is the UI counterpart to `haywire-core/ui`, which only provides
the base framework machinery.

---

## Folder Architecture

```
haybale_studio/
├── __init__.py             # BaseLibrary subclass + register_components()
│                           # Registers PROPERTIES_SCOPES before scanning panels folder
│
├── editors/                # Concrete editor implementations
│   ├── scopes.py           # PROPERTIES_SCOPES list: app(10), execution(20),
│   │                       #   canvas(30), debug(40), graph(50), node(60), edge(70)
│   ├── properties_editor.py # PropertiesEditor — left 36px scope toolbar + content area
│   │                       #   scope state in context.metadata['properties_scope']
│   │                       #   auto-falls-back to first available scope
│   ├── graph_editor.py     # GraphEditor — wraps GraphCanvasManager, handles
│   │                       #   ACTIVE_GRAPH_CHANGED by swapping canvas (_swap_canvas())
│   ├── console_editor.py   # ConsoleEditor — log/output viewer
│   ├── file_browser.py     # FileBrowserEditor — opens .haywire graph files
│   ├── file_viewer.py      # FileViewerEditor — raw file content viewer
│   ├── graph_manager_editor.py     # GraphManagerEditor — open graphs overview
│   ├── library_browser_editor.py   # LibraryBrowserEditor — installed libraries list
│   ├── library_component_editor.py # LibraryComponentEditor — individual component detail
│   └── library_overview_editor.py  # LibraryOverviewEditor — library detail view
│
├── panels/                 # Concrete panel implementations
│   ├── _settings_panel_base.py     # SettingsPanelBase — shared settings panel scaffold
│   ├── node_properties_panel.py    # Node position/label/color properties
│   ├── node_ports_panel.py         # Node port listing + connection info
│   ├── node_settings_panel.py      # Node settings (from NodeSettings schema)
│   ├── edge_info_panel.py          # Selected edge details
│   ├── graph_info_panel.py         # Graph-level info
│   ├── settings_app_panels.py      # App-scope settings panels
│   ├── settings_canvas_panels.py   # Canvas-scope settings panels
│   ├── settings_debug_panel.py     # Debug-scope settings panel
│   └── settings_execution_panel.py # Execution-scope settings panel
│
├── settings/               # Library settings schema definitions
│   ├── debug.py            # DebugSettings
│   ├── editor.py           # EditorSettings
│   ├── execution.py        # ExecutionSettings
│   ├── ui_canvas.py        # CanvasUISettings
│   ├── ui_edge.py          # EdgeUISettings
│   ├── ui_minimap.py       # MinimapUISettings
│   ├── ui_node.py          # NodeUISettings
│   └── workbench.py        # WorkbenchSettings
│
├── themes/                 # Studio theme contributions
├── skins/                  # Studio skin contributions
├── types/                  # Studio type contributions (currently empty)
├── widgets/                # Studio widget contributions (currently empty)
├── adapters/               # Studio adapter contributions (currently empty)
└── nodes/                  # Studio node contributions (currently empty)
```

---

## Always-load vs On-demand

**Always-load** (for any workbench UI work):
- `__init__.py` — how scopes and components are registered; order matters
- `editors/scopes.py` — the 7 scope IDs and their order weights
- `editors/properties_editor.py` — how the Properties editor renders scope tabs
- `editors/graph_editor.py` — how graphs are displayed and swapped

**On-demand**:
- `panels/` — load only the specific panel you're modifying
- `settings/` — load only when modifying specific settings categories
- `themes/`, `skins/` — load when modifying visual appearance

---

## Rules & Boundaries

- **Scope registration must happen before folder scan** in `register_components()`. The
  `__init__.py` registers `PROPERTIES_SCOPES` into `PanelRegistry` before scanning the
  panels folder — do not reorder.
- **Scope IDs** (from `editors/scopes.py`): `app`, `execution`, `canvas`, `debug`,
  `graph`, `node`, `edge`. These are the valid `scope=` values for `@panel` in this library.
- **Panel `@panel(editor=..., scope=...)`**: `editor` is the short `registry_id`
  (e.g. `'properties'`), not the full registry key.
- **`properties_scope` state** is stored in `context.metadata['properties_scope']`; the
  PropertiesEditor reads this to know which scope to render.
- **Settings are library-scoped** — use `@library_settings` on each settings class and
  register via `register_components()`.

---

## Source of Truth

| Concern | File |
|---------|------|
| Scope definitions | `editors/scopes.py` — `PROPERTIES_SCOPES` |
| Properties editor rendering | `editors/properties_editor.py` |
| Graph display / swap | `editors/graph_editor.py` |
| Settings schemas | `settings/*.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — node, graph, settings APIs
- [core-ui.md](core-ui.md) — BaseEditor, BasePanel, PanelRegistry, ScopeDescriptor

## Depended on by

- [haywire-studio.md](haywire-studio.md) — discovers this library via entry points at startup
