# Module: haybale-studio

**Path:** `barn/haybale-studio/haybale_studio/`
**Import as:** `haybale_studio`
**Plugin group:** `haywire.libraries`

---

## Scope & Purpose

The default studio UI plugin library. Contributes all of the workbench's editors, panels,
skins, and theme definitions. Loaded at runtime as a `haywire.libraries` entry point.

Major changes since last map:
- `panels/_settings_panel_base.py` removed — functionality moved to `haywire.ui.panel.render_utils`
- `panels/settings_app_panels.py`, `panels/settings_canvas_panels.py`, `panels/edge_info_panel.py` removed
- New panel structure: `app_panels.py`, `debug_panel.py`, `execution_panel.py`
- `settings/` drastically slimmed — removed `debug.py`, `editor.py`, `execution.py`,
  `ui_canvas.py`, `ui_edge.py`, `ui_minimap.py`, `ui_node.py`, `workbench.py`
- New `settings/theme_settings.py` added
- `themes/` added: `node.py`, `workbench.py` (moved from `haybale-core/themes/`)

---

## Folder Architecture

```
haybale_studio/
├── __init__.py                 # BaseLibrary subclass, register_components()
│
├── editors/                    # All workbench editor contributions
│   ├── console_editor.py       # Console output editor
│   ├── file_browser.py         # File browser editor
│   ├── file_viewer.py          # File viewer editor
│   ├── graph_editor.py         # Graph canvas editor (main editor)
│   ├── graph_manager_editor.py # Graph manager/open files editor
│   ├── library_browser_editor.py      # Library browser
│   ├── library_component_editor.py    # Library component detail editor
│   ├── library_overview_editor.py     # Library overview editor
│   ├── properties_editor.py    # Node properties editor
│   └── scopes.py               # Editor scope definitions
│
├── panels/                     # Workbench panel contributions
│   ├── app_panels.py           # Application-level panels (replaces settings_app_panels)
│   ├── debug_panel.py          # Debug panel (was settings_debug_panel.py)
│   └── execution_panel.py      # Execution panel (was settings_execution_panel.py)
│
├── settings/                   # haybale-studio settings
│   └── theme_settings.py       # ThemeSettings — theme selection settings
│
├── themes/                     # Theme contributions (moved from haybale-core)
│   ├── node.py                 # Default NodeTheme implementation
│   └── workbench.py            # Default WorkbenchTheme implementation
│
├── skins/                      # Skin contributions (if any)
│
├── adapters/                   # Type adapter contributions
│
├── nodes/                      # Any studio-specific utility nodes
│
├── types/                      # Type contributions
│
└── widgets/                    # Widget contributions
```

---

## Always-load vs On-demand

**Always-load**:
- `__init__.py` — registration path, what gets registered and when
- `editors/graph_editor.py` — main graph canvas editor, most important contribution
- `themes/workbench.py` + `themes/node.py` — default theme definitions

**On-demand**:
- Individual editors in `editors/` — only when modifying that editor
- `panels/` — only when working on app/debug/execution panels
- `settings/theme_settings.py` — only when working on theme selection UI

---

## Rules & Boundaries

- **`_settings_panel_base.py` is deleted** — use `haywire.ui.panel.render_utils` instead.
- **Themes moved here from haybale-core** — `haybale_core/themes/` is now empty; default
  `NodeTheme` and `WorkbenchTheme` implementations live in `haybale_studio/themes/`.
- Settings slimmed: most per-subsystem settings (canvas, edge, node UI, minimap, workbench)
  were removed from `settings/` here — these moved to the core settings system.
- Follow the `@editor` / `@panel` decorator patterns from `haywire.ui`.
- All components must be registered in `register_components()` in `__init__.py`.

---

## Source of Truth

| Concern | File |
|---------|------|
| Library registration | `__init__.py` |
| Main graph editor | `editors/graph_editor.py` |
| Default themes | `themes/workbench.py`, `themes/node.py` |
| Theme settings | `settings/theme_settings.py` |

---

## Depends on

- [core-engine.md](core-engine.md) — node/type/settings APIs
- [core-ui.md](core-ui.md) — BaseEditor, BasePanel, theme base classes, render_utils

## Depended on by

- [tests.md](tests.md) — UI tests test studio editors/panels via the harness
