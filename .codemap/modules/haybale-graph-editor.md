# Module: haybale-graph-editor

> Provides the visual graph editor surface (`GraphEditor`) decoupled from any specific graph source. Defines the `GraphContainer` protocol that source libraries implement, and the `GraphAppState` registry that maps `binding_id` → `GraphContainer` so the editor can resolve its tab to a live container.

**Path:** `barn/haybale-graph-editor/haybale_graph_editor/`
**Language:** Python 3.10+
**Owner:** Haywire studio team (bundled plugin)
**Tree hash:** `4e89edbaafbda81088f411c9e9768a6f5d788393`
**Mapped at:** 19bda1e (2026-07-05)

---

## 1. Scope & Purpose

`haybale-graph-editor` is the visual graph editor as a standalone plugin. It owns the `GraphEditor` surface (canvas + chrome + save-as dialog) and exposes a *source-agnostic* contract: any library can host a graph in `GraphEditor` by (a) implementing the `GraphContainer` protocol structurally and (b) registering its open containers into `GraphAppState`. `haybale-haystack`'s `GraphEntry` is the reference implementation, but cloud-graph or alternative storage libraries can register their own containers without touching this library.

Use it when working on the graph editor UI itself, the container/registry contract, right-click context-menu panels (including setting promotion), or when adding a new source library that needs to drive `GraphEditor`.

## 2. Folder Architecture

```
haybale_graph_editor/
├── __init__.py              ← Library entry, public re-exports
├── protocols.py             ← GraphContainer Protocol
├── focuses.py               ← PortFocus / PinFocus / SelectionFocus focus management
├── editors/
│   ├── graph_editor.py      ← GraphEditor surface (canvas + tab chrome)
│   ├── graph_save_as.py     ← save-as dialog logic
│   └── graph_canvas/
│       ├── graph_canvas_manager.py
│       ├── event_handlers.py, connection_info_popup.py, ui_node.py, ui_edge.py
│       ├── node_menu_builder.py   ← (rewritten) add-node menu; now built on shared
│       │                            `hui.elements.flyout` (FlyoutSiblings/flyout_category)
│       │                            instead of its own hover/z-index/close logic
│       └── handlers/
│           ├── context_menu.py         ← (extended) + promote_setting/demote_setting actions
│           ├── context_menu_actions.py ← (extended) SelectionContextActions/PortContextActions Protocols
│           ├── selection.py, selection_toolbar.py, visual_layer.py, interaction.py
├── panels/
│   ├── graph/
│   │   ├── menu/                    ← right-click context-menu panels, one dir per focus target
│   │   │   ├── node/promote.py      ← (new) "Promote Setting" hierarchical flyout panel
│   │   │   ├── port/port.py         ← (extended) + "Detach from setting" panel (demotes a promoted inlet)
│   │   │   ├── canvas/canvas.py, edge/edge.py, selection/selection.py
│   │   └── toolbar/selection.py
│   └── properties/
│       ├── introspect/{node,edge,graph,node_ports}.py  ← read-only inspector panels
│       └── setting/node.py          ← node settings panel
└── state/
    ├── graph_app_state.py   ← GraphAppState registry (binding_id → container)
    └── edit_state.py        ← EditState (selection, active node/port/graph)
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`; public re-exports of `GraphContainer`, `GraphAppState`, `GraphEditor`.
- `protocols.py` — `GraphContainer` Protocol; the contract every source library must satisfy.
- `state/graph_app_state.py` — `GraphAppState` registry; `register` / `unregister` / `rekey`.
- `state/edit_state.py` — `EditState`; selection + active node/port/graph, read by nearly every panel and handler.

### On-demand

- `editors/graph_editor.py` — when changing the editor UI, save flow, or canvas wiring.
- `editors/graph_canvas/handlers/selection.py` / `visual_layer.py` — node/edge selection and rendering (selected/highlighted/error states).
- `editors/graph_canvas/handlers/context_menu.py` + `context_menu_actions.py` — right-click action wiring; `promote_setting`/`demote_setting` live here and delegate to `haywire.core.node.promotion`.
- `editors/graph_canvas/node_menu_builder.py` — add-node right-click menu; now a thin consumer of `haywire.ui.elements.flyout` (`FlyoutSiblings`, `flyout_category`) rather than owning hover/close mechanics itself.
- `panels/graph/menu/node/promote.py` — "Promote Setting" panel; renders one flyout per settings-bag, grouping promotable `setting()` fields by eligible `PortType` direction (`watch()` → outlet-only, else inlet+outlet).
- `panels/graph/menu/port/port.py` — port-context panels; `DetachSettingMenuPanel` demotes a promoted inlet back to a plain setting.
- `panels/properties/introspect/node_ports.py` — ports panel rendering live editable widgets (ADR 0008, `PortFocus` scope).
- `focuses.py` — focus management (`PortFocus` for ports panel, `PinFocus` for pin detail, `SelectionFocus` for node/edge selection panels).

## 4. Rules & Boundaries

- `GraphAppState` holds *references* only — owning libraries control container lifecycle (create / discard).
- `binding_id` is the persistent identifier (workspace-serializable); the container is the runtime cache and must not be persisted on its behalf.
- This library does not know which source produced any given container — never special-case `GraphEntry` here.
- Must register through `Library.register_components()`; entry point declared in `barn/haybale-graph-editor/pyproject.toml`.
- Nested hover-flyout menus (add-node menu, promote-setting menu) must go through `haywire.ui.elements.flyout` (`FlyoutSiblings`/`flyout_category`/`hui.FLYOUT_PROPS`/`hui.FLYOUT_Z`) rather than reimplementing hover-open/sibling-close/z-index logic locally — see `.insights/feedback_nicegui_nested_menu_flyouts.md`.
- Promotion eligibility is a two-flag rule owned by `haywire.core.node.promotion`, not re-derived here: read-only (`watch()`) fields are outlet-only; writable fields (plain/`shadow()`) are inlet-or-outlet. `promote.py:promotable_fields()` just reads `desc._read_only` to branch.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Container protocol | `protocols.py` | `binding_id`, `editor`, `path`, `unsaved`, `display_name`, `save()` |
| App-wide registry | `state/graph_app_state.py` | `app_data[GraphAppState]`; keyed by `binding_id` |
| Editor surface | `editors/graph_editor.py` | `GraphEditor` (`opens='on_payload'`) |
| Library entry | `__init__.py` | `graph_editor = "haybale_graph_editor:Library"` |
| Promote/demote actions | `editors/graph_canvas/handlers/context_menu.py` | Delegates to `haywire.core.node.promotion.{promote_setting,demote_setting}` |
| Promote-setting menu | `panels/graph/menu/node/promote.py` | Hierarchical flyout: bag ▸ field ▸ direction |
| Detach-setting panel | `panels/graph/menu/port/port.py` | `DetachSettingMenuPanel`, shown only on `port.promoted` |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md), [haywire-core-ui](haywire-core-ui.md) — `BaseEditor`, `AppState`, `Reveal`/`Close` signals, session context, `haywire.ui.elements.flyout` (shared flyout mechanics), `haywire.core.node.promotion` (promote/demote logic).
- [haywire-studio](haywire-studio.md) — workspace metadata for save paths.
- [haybale-studio](haybale-studio.md) — `GraphCanvasManager`, `EditState`.

### Depended on by

- [haybale-haystack](haybale-haystack.md) — registers `GraphEntry` containers; reveals `GraphEditor` for haystack graphs.
- Future graph-management libraries by the same pattern.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point named `graph_editor` |
| Container protocol | `protocols.py:GraphContainer` | Structural contract for graph hosts |
| App registry | `state/graph_app_state.py:GraphAppState` | `binding_id` → `GraphContainer` map |
| Editor | `editors/graph_editor.py:GraphEditor` | The graph editor surface |
| Promote-setting panel | `panels/graph/menu/node/promote.py:PromoteSettingMenuPanel` | Node right-click "Promote Setting" flyout |
| Detach-setting panel | `panels/graph/menu/port/port.py:DetachSettingMenuPanel` | Pin right-click "Detach from setting" |
