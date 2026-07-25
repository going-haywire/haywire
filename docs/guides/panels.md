---
status: draft
doc_template: guide
scope: One panel type per section — folder structure, naming convention, and a live code example for each.
see-also:
  - ../components/panels/panel-canon.md
  - ../reference/glossary.md
---

# Panel types — worked examples

The panel authoring API — the `@panel` decorator, `BasePanel`, `poll()`, `draw()`, focus objects, action protocols — is documented in [components/panels/panel-canon](../components/panels/panel-canon.md). This guide shows what's distinctive about each **panel type**: where it lives in the folder hierarchy, what suffix it carries, and a minimal live example.

## Folder structure and naming logic

Panels sit under `panels/` in each library. The folder structure is **advisory only** — it helps humans navigate the codebase, but does not affect where panels appear. What's load-bearing is the `@panel` decorator (specifically `actions=` and the focus protocol), plus the `poll()` method to gate visibility.

Panels follow a three-level naming convention for organization:

```
panels/
  <editor>/          # which editor surface (properties, graph, file_browser)
    <surface>/       # how the panel is triggered (introspect, setting, menu, toolbar)
      <subject>/     # what data it operates on
```

Suffix rules:
- `*Panel` — display panel shown in the PropertiesEditor sidebar (read-only or settings).
- `*MenuPanel` — action panel shown in a context menu (canvas, node, edge, selection, port, file).
- `*ToolbarPanel` — action panel shown in the floating toolbar.

The suffix helps you recognize panel type at a glance, but the **actual placement** depends on the focus and actions you register with `@panel`.


```
panels/
  properties/
    introspect/     ← organize read-only identity, status, runtime info, errors here
    setting/        ← organize editable settings (app, canvas, node user-settings) here

  graph/
    toolbar/        ← organize floating toolbar panels (ToolbarFocus) here
    menu/
      canvas/       ← organize right-click empty canvas panels (CanvasFocus) here
      selection/    ← organize right-click node or multi-selection panels (SelectionFocus) here
      node/         ← reserved for future node-scoped panels; currently empty in production
      edge/         ← organize right-click edge panels (EdgeFocus) here
      port/         ← organize right-click pin panels (PinFocus) here
      skin/         ← organize right-click custom menu panels (custom Focus) here

  file_browser/
    menu/           ← organize file browser right-click panels (FileFocus) here
```

**Important:** The folder labels above indicate the *focus type* and *context*. The folder location itself does not determine appearance — the `@panel` decorator's `actions=` parameter and `poll()` method are what actually wire the panel to the right place.

## Properties / introspect panel

Introspect panels register against focus objects (e.g. `NodeFocus`, `EdgeFocus`) and render read-only identity or state information in the PropertiesEditor.

Source: [`graph_editor:panel:NodeInfoPanel`](../../barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node.py)

`NodeInfoPanel` shows the selected node's label, class name, and node ID:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node.py:node_info_panel"
```

**Type-specific:** no `actions=` on `@panel` — introspect panels are display-only. `poll()` gates on `ctx.data[EditState].active_node`, so the panel appears only while a node is selected. `with layout:` places all rows inside the panel's container.

## Properties / settings panel

Settings panels register against settings-scope focuses (`CanvasFocus`, `AppFocus`, `ExecutionFocus`) and render a schema using `render_schema()` in the PropertiesEditor.

Source: [`studio:panel:CanvasSettingsPanel`](../../barn/haybale-studio/haybale_studio/panels/properties/setting/canvas.py)

`CanvasSettingsPanel` renders the entire `CanvasSettings` schema into the panel:

```python
--8<-- "barn/haybale-studio/haybale_studio/panels/properties/setting/canvas.py:canvas_settings_panel"
```

**Type-specific:** no `actions=`, no `poll()` override — settings panels are always visible for their focus. `render_schema(SettingsClass, registry)` renders every field in the schema as a labelled input widget.

## Graph menu / canvas panel

Canvas menu panels register against `CanvasFocus` with `actions=CanvasContextActions` and surface on right-click on empty canvas space.

Source: [`graph_editor:panel:CreateNodeMenuPanel`](../../barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/canvas/canvas.py)

`CreateNodeMenuPanel` renders the full node-creation menu with search:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/canvas/canvas.py:create_node_menu_panel"
```

**Type-specific:** `actions=CanvasContextActions` wires the panel to the canvas action protocol. `poll()` returns `True` unconditionally — the canvas menu always has at least "Create Node". `self.actions.create_node_at_click(registry_key)` dispatches via the action protocol; the host resolves the concrete implementation.

## Graph menu / selection panel

Selection menu panels register against `SelectionFocus` and surface when one or more nodes or edges are selected.

Source: [`graph_editor:panel:DeleteSelectionMenuPanel`](../../barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py)

`DeleteSelectionMenuPanel` deletes every selected node and edge in one undo step:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py:delete_selection_menu_panel"
```

**Type-specific:** `poll()` gates on `edit.selected_nodes or edit.selected_edges` — the panel is hidden when nothing is selected. `selection_label()` (a helper in the same file) generates a count-aware button label ("Delete 3 Nodes", "Delete Edge", "Delete Selection").

## Graph toolbar panel

Toolbar panels register against `ToolbarFocus` and contribute a single icon button to the floating toolbar that appears over a canvas selection.

Source: [`graph_editor:panel:CopyToolbarPanel`](../../barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/selection.py)

`CopyToolbarPanel` renders a single copy icon:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/selection.py:copy_toolbar_panel"
```

**Type-specific:** `draw()` renders exactly one `hui.icon_action(...)`. The toolbar host owns the `ui.row` container; each panel just drops a single icon button into it. The panel has no label — only the icon and a tooltip.

## Graph menu / skin panel

A skin panel is a `*MenuPanel` registered against a custom focus set by the skin layer via DOM attributes. Two attributes control which focus the context menu fires:

- `data-hw-custom-menu-focus-id` — fires when the user right-clicks a node (node-level custom menu).
- `data-hw-port-menu-focus-id` — fires when the user right-clicks a port pin (port-level custom menu).

The skin writes these attributes on the rendered node card or pin element. The framework reads them on right-click and fires the focus object named by the attribute value. Panels registering against that focus appear in the context menu.

`NodeContextActions` (an empty marker protocol in `context_menu_actions.py`) is the skin extension point for `data-hw-custom-menu-focus-id`. `PortContextActions` is the equivalent for `data-hw-port-menu-focus-id`.

Source: [`graph_editor:panel:PortInfoMenuPanel`](../../barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py)

`PortInfoMenuPanel` shows port metadata (id, description, flow type, data type) in the port context menu:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py:port_info_menu_panel"
```

**Type-specific:** `actions=PortContextActions` is an empty marker — there are no methods to dispatch; the panel only reads `ctx.data[EditState].active_port`. `layout.container` (not `with layout:`) is used here to render directly into the bare container without an extra wrapper.

## File browser menu panel

File browser menu panels register against `FileFocus` (from haybale-studio) and surface in the FileBrowser's right-click menu.

Source: [`haystack:panel:OpenInHaystackMenuPanel`](../../barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py)

`OpenInHaystackMenuPanel` opens a `.haywire` graph file in the GraphEditor:

```python
--8<-- "barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py:open_in_haystack_menu_panel"
```

**Type-specific:** `poll()` checks the file extension via `ctx.data[FileBrowserState].right_clicked_file`. `self.actions.reveal(EditorClass, binding_id, label)` tells the studio to open or focus the named editor bound to that file. The panel lives in haybale-haystack (not haybale-studio) because it depends on `HaystackState`, which is owned by that library.
