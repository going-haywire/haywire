# Module: haybale-graph-editor

> Visual graph editor plugin: the `GraphContainer` protocol, the `GraphAppState` registry, the `GraphEditor` surface and canvas (nodes, edges, selection, promote/demote, arrange, history), plus the graph-level panels and skins.

**Path:** `barn/haybale-graph-editor/haybale_graph_editor/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `dae828f6da44fd3c28b493432e5ce193fafc70f6`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-graph-editor` renders and edits a graph. It takes a container from any source library via the `GraphContainer` protocol and holds no knowledge of which library produced it. It owns the canvas (`editors/graph_canvas/`), the graph editor and its save-as, load and history editors, the add-node and promote-setting flows, the selection and graph toolbars, and the surfaces and skins that draw nodes, edges, pins, ports and insets. It depends on [haywire-core-ui](haywire-core-ui.md) for flyouts and editor bases. [haybale-haystack](haybale-haystack.md) registers the containers it displays. If this library were removed, graphs could still run but could not be edited in the studio.

## 2. Folder Architecture

```
haybale_graph_editor/
├── __init__.py          ← `Library`; re-exports GraphContainer, GraphAppState, GraphEditor
├── protocols.py         ← GraphContainer protocol (binding_id, editor, path, unsaved, display_name, save)
├── access.py            ← access rules for the editor
├── notices.py           ← user-facing notices
├── states/
│   ├── graph_app_state.py ← GraphAppState registry (binding_id → container)
│   └── edit_state.py      ← EditState: selection + active node/port/graph
├── editors/
│   ├── graph_editor.py    ← GraphEditor surface (opens='on_payload')
│   ├── graph_save_as.py, history_editor.py
│   └── graph_canvas/
│       ├── graph_canvas_manager.py, graph_load_modal.py, event_handlers.py
│       ├── inset_view.py, ui_node.py, ui_edge.py
│       └── handlers/      ← context_menu, interaction, selection, selection_toolbar, visual_layer
├── panels/
│   ├── node_menu_builder.py ← add-node menu (consumes haywire.ui.elements.flyout)
│   ├── _gating.py, _previous_setup.py, _selection_forms.py
│   ├── graph/
│   │   ├── menu/          ← component_rows; edge/, graph/ (context), port/, selection/ (arrange, layout, rebuild, stage, selection)
│   │   └── toolbar/       ← appearance, selection, style
│   └── properties/
│       ├── introspect/    ← edge, graph, node, node_ports, port_edit_dialog
│       └── setting/       ← graph, metadata, node, skin
├── _new_node_flow/      ← New Node wizard stepper (_state, chrome, copy, panels)
├── _promote_flow/       ← Promote Setting flyout flow (_state, chrome, copy, panels)
├── surfaces/            ← edge, graph, graph_context, node, pin, ports, selection, toolbar
├── skins/               ← node_skin, error_skin, inset_skin, split_skin, stacked_skin
├── settings/            ← node_skin_settings.py
├── farmhands/           ← editor_tools.py (Farmhand tools)
└── haybale.toml         ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `protocols.py` — `GraphContainer`, the contract every source library satisfies.
- `states/graph_app_state.py` — `GraphAppState`: `register` / `unregister` / `rekey`.
- `states/edit_state.py` — `EditState`: selection and active node/port/graph, read by most panels and handlers.
- `__init__.py` — `Library` and `register_components()`.

### On-demand

- `editors/graph_editor.py` — editor UI, save flow, canvas wiring.
- `editors/graph_canvas/handlers/` — selection (`selection.py`), rendering states (`visual_layer.py`), right-click actions (`context_menu.py`), toolbar (`selection_toolbar.py`).
- `editors/graph_canvas/graph_canvas_manager.py` — canvas lifecycle.
- `_promote_flow/` and `panels/graph/menu/` — the Promote Setting and port/edge/selection context panels. `DetachSettingMenuPanel` lives in `panels/graph/menu/port/port.py` and is shown only on `port.promoted`.
- `_new_node_flow/` — New Node wizard.
- `panels/properties/introspect/node_ports.py` — ports panel with live editable widgets (ADR 0008, `PortFocus` scope).
- `panels/graph/menu/selection/arrange.py`, `layout.py` — arrange verbs (ADR for node arrange).
- `surfaces/` and `skins/` — node, edge, pin and inset drawing.

## 4. Rules & Boundaries

- `GraphAppState` holds references only. Owning libraries control container lifecycle.
- `binding_id` is the persistent identifier and is workspace-serialisable. The container is a runtime cache and must not be persisted on its behalf.
- This library must not know which source produced a container. Never special-case `GraphEntry` here.
- Register through `Library.register_components()`. Entry point: `graph_editor = "haybale_graph_editor:Library"` in `barn/haybale-graph-editor/pyproject.toml`.
- Nested hover-flyout menus go through `haywire.ui.elements.flyout` (`FlyoutSiblings`, `flyout_category`, `hui.FLYOUT_PROPS`, `hui.FLYOUT_Z`). Do not re-implement hover-open or sibling-close logic. See `.insights/feedback_nicegui_nested_menu_flyouts.md`.
- Promotion eligibility is decided in `haywire.core.node.promotion`, not here. Read-only (`watch()`) fields are outlet-only; writable fields are inlet or outlet. `promote` flow reads `desc._read_only` only to branch.
- Promote and demote delegate to `haywire.core.node.promotion.{promote_setting,demote_setting}`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Container protocol | `protocols.py` | `binding_id`, `editor`, `path`, `unsaved`, `display_name`, `save()` |
| App-wide registry | `states/graph_app_state.py` | Keyed by `binding_id` |
| Editor surface | `editors/graph_editor.py` | `GraphEditor` |
| Library entry | `__init__.py` | `graph_editor` entry point |
| Promote/demote actions | `editors/graph_canvas/handlers/context_menu.py` | Delegates to core promotion |
| Promote flyout | `_promote_flow/` | Bag ▸ field ▸ direction |
| Detach-setting panel | `panels/graph/menu/port/port.py` | `DetachSettingMenuPanel` |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — graph model, promotion, session context, `AppState`, signals.
- [haywire-core-ui](haywire-core-ui.md) — `BaseEditor`, flyout mechanics (`haywire.ui.elements.flyout`).
- [haybale-studio](haybale-studio.md) — `EditState` consumers, `GraphCanvasManager` shared pieces, file surface.

### Depended on by

- [haybale-haystack](haybale-haystack.md) — registers `GraphEntry` containers and reveals `GraphEditor`.
- [haybale-models](haybale-models.md) — imports `haybale_graph_editor` in 5 files (editors, farmhands, state, needs).

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `graph_editor` entry point |
| Container protocol | `protocols.py:GraphContainer` | Structural contract for graph hosts |
| App registry | `states/graph_app_state.py:GraphAppState` | `binding_id` → container |
| Editor | `editors/graph_editor.py:GraphEditor` | Graph editor surface |
| Canvas manager | `editors/graph_canvas/graph_canvas_manager.py` | Canvas lifecycle |
| Promote-setting flow | `_promote_flow/` | Hierarchical flyout |
