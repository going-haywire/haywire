---
status: draft
doc_template: guide
scope: One panel type per section — folder structure, naming convention, and a live code example for each.
see-also:
  - ../components/panels/panel-canon.md
  - ../reference/glossary.md
---

# Panel types — worked examples

The panel authoring API — the `@panel` decorator, `BasePanel`, `poll()`, `draw()`, Surfaces, `provides` — is documented in [components/panels/panel-canon](../components/panels/panel-canon.md). This guide shows what's distinctive about each **panel type**: where it lives in the folder hierarchy, what suffix it carries, and a minimal live example.

## Folder structure and naming logic

Panels sit under `panels/` in each library. The folder structure is **advisory only** — it helps humans navigate the codebase, but does not affect where panels appear. What's load-bearing is the `@panel` decorator's `surface=` (and `hosts=`, for a panel that nests further Surfaces of its own), plus the `poll()` method to gate visibility.

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

The suffix helps you recognize panel type at a glance, but the **actual placement** depends on the `surface=` you register with `@panel`.


```
panels/
  properties/
    introspect/     ← organize read-only identity, status, runtime info, errors here
    setting/        ← organize editable settings (app, canvas, node user-settings) here

  graph/
    toolbar/        ← organize floating toolbar panels (SelectionToolbar) here
    menu/
      context/      ← organize the canvas right-click menu's panels (GraphContext and its hosted regions) here
      selection/    ← organize right-click node or multi-selection panels (SelectionMenu) here
      node/         ← reserved for future node-scoped panels; currently empty in production
      edge/         ← organize right-click edge panels (EdgeMenu) here
      port/         ← organize right-click pin panels (PinMenu) here
      skin/         ← organize right-click custom menu panels (a library's own Surface, reached via `data-hw-menu-surface-id`) here

  file_browser/
    menu/           ← organize file browser right-click panels (FileMenu) here
```

**Important:** The folder labels above indicate the *Surface* and *context*. The folder location itself does not determine appearance — the `@panel` decorator's `surface=` parameter and `poll()` method are what actually wire the panel to the right place.

## Properties / introspect panel

Introspect panels register against inspector Surfaces (e.g. `NodeInspector`, `EdgeInspector`) and render read-only identity or state information in the PropertiesEditor.

Source: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node.py`

`NodeInfoPanel` shows the selected node's label, class name, and node ID:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node.py:22:56"
```

from: `NodeInfoPanel` — registry_key: `haybale-graph-editor:panel:NodeInfoPanel`

**Type-specific:** no `provides` on `NodeInspector` — introspect panels are display-only and declare no `actions:` annotation. `poll()` gates on `ctx.data[EditState].active_node`, so the panel appears only while a node is selected. `with layout:` places all rows inside the panel's container.

## Properties / settings panel

Settings panels register against inspector Surfaces for settings scopes (`CanvasSettings`, `AppSettings`, `ExecutionInspector`, `DebugSurface`) and render a schema using `render_schema()` in the PropertiesEditor.

Source: `barn/haybale-studio/haybale_studio/panels/properties/setting/canvas.py`

`CanvasSettingsPanel` renders the entire `CanvasSettings` schema into the panel:

```python
--8<-- "barn/haybale-studio/haybale_studio/panels/properties/setting/canvas.py:40:56"
```

from: `CanvasSettingsPanel` — registry_key: `haybale-studio:panel:CanvasSettingsPanel`

**Type-specific:** no `actions:` annotation, no `poll()` override — settings panels are always visible for their Surface. `render_schema(SettingsClass, registry)` renders every field in the schema as a labelled input widget.

## Graph menu / canvas panel

The canvas right-click menu is a small tree of Surfaces, not one flat panel list — it is the primary example of a **hosting panel** with regions. `GraphContext` (`barn/haybale-graph-editor/haybale_graph_editor/surfaces/graph_context.py`) is the root Surface that `on_canvas_context` opens; `GraphContextPanel` is the sole panel registered on it, and it implements none of `GraphActions` itself — `SessionContextMenuProvider` does. `GraphContextPanel` **pipes**: it calls `self.render_surface(S, ctx)` without an `actions=` argument, so each nested Surface receives `self.actions` (the host `GraphContextPanel` itself received) rather than `GraphContextPanel`.

Source: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/context/context.py`

`GraphContextPanel` arranges an icon-shortcut row and a prime area, each its own hosted Surface, into the *same* popup:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/context/context.py:38:56"
```

from: `GraphContextPanel` — registry_key: `haybale-graph-editor:panel:GraphContextPanel`

**Type-specific:** `hosts=(GraphToolBar, GraphContextBody)` declares the two Surfaces this panel may render; calling `self.render_surface()` on anything not listed there is an authoring error (see [panel-canon §3, "Hosting a surface"](../components/panels/panel-canon.md)). `GraphContextPanel` has no `actions:` annotation of its own — it never calls a verb directly, only passes the host along. `CreateNodeMenuPanel`, registered on `GraphContextBody`, is what actually renders the node-creation menu with search; `PastePanel`, registered on `GraphToolBar`, is the paste shortcut icon. Both receive `GraphActions` — `SessionContextMenuProvider` — by the same pipe, two hops down from where it was first injected.

## Graph menu / selection panel (with its disabled form)

Selection menu panels register against `SelectionMenu` and surface when one or more nodes or edges are selected. This surface is also what the floating toolbar's "⋯" hosts, so every panel here defines `draw_disabled()` too: an inapplicable command greys rather than disappearing, since this is the menu a user can right-click into with an empty selection.

Source: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py`

`DeleteSelectionMenuPanel` deletes every selected node and edge in one undo step, and renders its own greyed form when nothing is selected:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/selection/selection.py:105:137"
```

from: `DeleteSelectionMenuPanel` — registry_key: `haybale-graph-editor:panel:DeleteSelectionMenuPanel`

**Type-specific:** `poll()` gates on `edit.selected_nodes or edit.selected_edges` — when it is `False`, the host calls `draw_disabled()` instead of skipping the panel, so a fixed-shape command list never reflows or vanishes as the selection changes. `draw_disabled()` renders the same label, greyed and unclickable (`hui.menu_row(..., enabled=False)`) — it must not touch selection state, only render the inapplicable form. The default `draw_disabled()` (inherited, not overridden) is a no-op, so a panel that skips it keeps vanishing exactly as before; only a panel meant to appear in a fixed-shape menu like this one overrides it. `selection_label()` (a helper in the same file) generates a count-aware button label ("Delete 3 Nodes", "Delete Edge", "Delete Selection").

## Graph toolbar panel

Toolbar panels register against `SelectionToolbar` and contribute a single icon button to the floating toolbar that appears over a canvas selection.

Source: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/selection.py`

`CopyToolbarPanel` renders a single copy icon:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/selection.py:29:49"
```

from: `CopyToolbarPanel` — registry_key: `haybale-graph-editor:panel:CopyToolbarPanel`

**Type-specific:** `draw()` renders exactly one `hui.icon_action(...)`. The toolbar host owns the `ui.row` container; each panel just drops a single icon button into it. The panel has no label — only the icon and a tooltip.

## Graph toolbar / dropdown panel (content below the toolbar)

The other thing a toolbar icon can host: a *panel*, not a menu. `AppearanceToolbarPanel` hosts `NodeAppearance` in a `hui.dropdown`, which opens **below** the toolbar rather than beside it (`align=` and `direction=` place it — the same panel can hang below, stand above, or centre on its icon), on click rather than hover, and without `auto-close` — a menu's auto-close dismisses on any click inside, so the first click into a field would shut the panel. The rule of thumb is in [design-guide §8.8c](../reference/design-guide.md): commands go in a `hui.flyout`, content goes in a `hui.dropdown`.

Source: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/appearance.py`

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/appearance.py:54:81"
```

from: `AppearanceToolbarPanel` — registry_key: `haybale-graph-editor:panel:AppearanceToolbarPanel`

**Type-specific:** it declares a `poll()` where its toolbar neighbours do not — `SelectionToolbar.poll` is "something is selected", which an edges-only selection satisfies, and there is nothing to style without a node. What lands inside is `NodeAppearancePanel`, whose `draw()` is one call: `render_settings(bag, categories=("appearance",))` — the live `appearance` slice of the node's own props bag, with the same rows, reset chrome and subscriptions the properties editor renders, sliced rather than copied. Two things a dropdown body must respect: wrap content in `hw-panel` (the `QMenu` portals to `<body>`, outside the toolbar popup, so `.hw-panel`-scoped CSS otherwise misses it), and put the fields in a *panel* on a hosted surface — the emptiness rule counts what `render_panel` drew, so fields rendered straight into the body would grey the icon.

## Graph menu / overflow panel (a hosting panel that is itself nested)

`GraphMorePanel` (also in `panels/graph/menu/context/context.py`) is the canvas menu's "…" — a panel that both is a leaf on one Surface (`GraphToolBar`) and hosts another (`GraphMoreActions`) itself. It shows the general shape any extension-point overflow takes: a library that wants to add a canvas-menu command with no obvious home renders into `GraphMoreActions` instead of asking the framework to add a new built-in Surface.

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/context/context.py:80:103"
```

from: `GraphMorePanel` — registry_key: `haybale-graph-editor:panel:GraphMorePanel`

**Type-specific:** `hui.flyout("more_horiz", tooltip="More actions")` opens a submenu body; `self.render_surface(GraphMoreActions, ctx)` renders whatever is registered there inside it, still piping `self.actions` two hops down from the original host. An empty `GraphMoreActions` — no library has extended it yet — greys the "…" icon retroactively rather than opening an empty flyout; see [panel-canon §3, "What a nested panel may not assume"](../components/panels/panel-canon.md) and `.insights/feedback_nicegui_nested_menu_flyouts.md`.

## Graph menu / pin panel

Pin (port) context-menu panels register against `PinMenu` and surface when the user right-clicks a pin. Reached structurally, not declaratively: the canvas detects a pin from `data-pin-id` (emitted by every skin's rendered pins), so every skin gets this menu and none can suppress it.

Source: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py`

`PortInfoMenuPanel` shows port metadata (id, description, flow type, data type) in the pin context menu:

```python
--8<-- "barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py:26:57"
```

from: `PortInfoMenuPanel` — registry_key: `haybale-graph-editor:panel:PortInfoMenuPanel`

**Type-specific:** `provides = PortActions` on `PinMenu` is a small Protocol (one verb: `demote_setting`) — the sibling panel `DetachSettingMenuPanel` is the only one that calls it, shown only on a promoted inlet. `PortInfoMenuPanel` itself declares no `actions:` annotation; it only reads `ctx.data[EditState].active_port`. `layout.container` (not `with layout:`) is used here to render directly into the bare container without an extra wrapper.

## Skin menu panel (a library's own Surface)

A skin can add its own context menu on any element it renders, by writing `data-hw-menu-surface-id="<your-surface-id>"` on that element and registering a `Surface` — with panels against it — under that id. This is **not** how the pin, node, edge, or canvas menus work; those are structural or framework-declared and cannot be redirected this way. See [skin-canon's context-menu section](../components/skins/skin-canon.md) for the attribute contract.

## File browser menu panel

File browser menu panels register against `FileMenu` (from haybale-studio) and surface in the FileBrowser's right-click menu.

Source: `barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py`

`OpenInHaystackMenuPanel` opens a `.haywire` graph file in the GraphEditor:

```python
--8<-- "barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py:34:71"
```

from: `OpenInHaystackMenuPanel` — registry_key: `haybale-haystack:panel:OpenInHaystackMenuPanel`

**Type-specific:** `poll()` checks the file extension via `ctx.data[FileBrowserState].right_clicked_file`. `self.actions.reveal(EditorClass, binding_id, label)` tells the studio to open or focus the named editor bound to that file. The panel lives in haybale-haystack (not haybale-studio) because it depends on `HaystackState`, which is owned by that library.
