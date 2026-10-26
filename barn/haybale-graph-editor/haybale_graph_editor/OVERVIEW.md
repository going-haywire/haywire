# Graph Editor

Visual graph editor library — host-agnostic

## Settings
- **Node Skin** — Settings controlling node layout and pin geometry.

## Farmhands
- **Add node** — Add a node by registry key. Call studio_describe_component first to learn its ports.
- **Connect** — Connect an outlet to an inlet.
- **Demote setting** — Remove a promoted port, returning the field to a plain setting. One undo step.
- **Inspect node** — One node's ports, settings, and health, at a chosen depth.
- **Move nodes** — Move nodes to absolute positions ({node_id: {x, y}}).
- **Operate widget** — Change the value of a widget that is shown on a node card. Not undo-recorded.
- **Promote setting** — Promote a settings field to a data port. One undo step.
- **Query graph** — Nodes (with ports) and edges of an open graph.
- **Redo** — Redo the last undone change on this graph's SHARED human+agent timeline.
- **Remove elements** — Remove nodes and/or edges (also the way to disconnect).
- **Set graph metadata** — Set a graph's document metadata (label, description, author, version). One undo step.
- **Set property** — Set a node property (port value or settings field) by name. Undo-recorded.
- **Undo** — Undo the last change on this graph's SHARED human+agent timeline.

## States
- **Edit State** — Per-session graph-editor state: selection, active items, clipboard.

## Panels
- **Adapter Chain** — List the adapters converting the source value to the sink type, in order.
- **Adapters** — One row per adapter in the edge's chain, each opening its source.
- **Add to Stage** — Put the selected nodes on the stage; offered when the selection holds an off-stage node.
- **Appearance** — The ⧉ icon that drops the appearance fields above the toolbar.
- **Appearance** — The selected node's appearance props, or a form applying to every selected node.
- **Arrange** — The "Arrange" row: a submenu over the stacking-order verbs.
- **Bring Forward** — Move each selected node one step up: above the next node over it.
- **Bring to Front** — Paint the selected nodes above every other node in this view.
- **Clone to Library** — Write a copy of this node's class into a library, as a new node to edit.
- **Collapse to Group** — Collapse the selection into one Graph-node standing for a Subgraph.
- **Connection Errors** — Edge errors panel for the context menu (right-click on edge).
- **Connection Errors** — Edge errors panel for PropertiesEditor.
- **Connection Path** — The source and target pins of the selected connection.
- **Connection Warnings** — Edge warnings panel for the context menu.
- **Connection Warnings** — Edge warnings panel for PropertiesEditor.
- **Copy Selection** — Copy the selected nodes and edges to the clipboard.
- **Create Node** — The hierarchical node-creation menu, search and tree together.
- **Delete Connection** — Delete the right-clicked connection.
- **Delete Selection** — Delete every node and edge in the current selection in one undoable step.
- **Detach from setting** — Removes a pin the user added, on the pin that carries it.
- **Detail** — The "Detail" row — a submenu over the density ranks.
- **Detail Ranks** — One row per node detail rank.
- **Develop** — The "Develop" row — a submenu over the node's source, cloning it, and rebuilding.
- **Dissolve Reroute** — Collapse a reroute node back into a direct connection.
- **Edit Instance** — Turn one macro placement into a modified instance and enter it.
- **Edit Source** — The "Edit Source" row — a submenu over the adapters behind this edge.
- **Edit Source** — The "Edit Source" row — a submenu over the components behind this node.
- **Edit Source** — The "Edit Source" row — a submenu over the components behind this pin.
- **Enter** — Enter a Group or a macro placement: open its inside as a level of the graph editor.
- **Execution Statistics** — Execution count, average time and test value of the selected connection.
- **Expand Group** — Expand a Group back into the graph around it.
- **Focus on Graph** — Fit the viewport to show every node in the graph, as an icon shortcut.
- **Fold** — Fold or unfold every selected node — one row, both directions.
- **Fold** — One button that folds or unfolds the selection.
- **Graph Context** — Layout-only root of the canvas menu: shortcut row, then prime area.
- **Graph Info** — Displays counts and framework-written metadata for the active graph.
- **Graph Metadata** — Renders the metadata of the active graph.
- **Graph Settings** — Renders the properties of the active graph.
- **Insert Reroute** — Split the active edge and insert a reroute node in between. Available for every edge.
- **Lock** — Lock or unlock one node, as protection against accidental manipulation.
- **Macro** — The "Macro" row — a submenu over the verbs between a card and a macro.
- **Modified instance** — Offer to put a modified instance back to its macro, or to cut it loose.
- **More** — The ⋯ — a panel that hosts the selection right-click menu.
- **More Actions** — The "…" — a panel that is itself a host.
- **New Node** — Open the New Node wizard, as an icon shortcut.
- **Node** — The node class itself, as a row that opens its source.
- **Node Errors** — Node errors panel for PropertiesEditor.
- **Node Errors** — Node errors panel for the unified selection context menu.
- **Node Info** — Displays basic identity information for the selected node.
- **Node Properties** — Displays per-instance node settings (collapsed, locked, skin, etc.).
- **Node Settings** — Discovers and renders all user-defined settings on the selected node.
- **Paste** — Paste at the click position, as an icon shortcut.
- **Ports** — Displays the inlet, outlet, and config ports of the selected node.
- **Propagation** — Lazy propagation pulls data on demand instead of pushing it to the target node.
- **Propagation** — Switch the edge between eager and lazy propagation, or show the mode it is fixed to.
- **Rebuild** — The "Rebuild" row — a submenu over redraw / revalidate / reset.
- **Reconnect Edge** — Removes the edge and starts a new connection drag from the anchor pin.
- **Redraw Selection** — Redraw every node/edge in the selection in one step.
- **Remove from Stage** — Take the selected nodes off the stage; offered when the selection holds an on-stage node.
- **Reset Detail** — Drop each selected node's own detail rank, so it follows the graph's again.
- **Reset Node Detail** — Make every node in the graph follow the graph's detail rank again.
- **Reset Selection** — Reset every node/edge in the selection in one step.
- **Reset to default** — Put the backing setting back to its declared default, from the pin.
- **Revalidate Selection** — Revalidate every node/edge in the selection in one step.
- **Save new Macro** — Save a Group as a new macro. Only visible when the right-clicked node is a Graph-node.
- **Send Backward** — Move each selected node one step down: below the next node under it.
- **Send to Back** — Paint the selected nodes below every other node in this view.
- **Set to none** — Clear the backing setting to absence (OPTIONAL[T] fields only).
- **Show widget** — The "Show widget ▸" row — picks when this pin's Widget is rendered.
- **Skin** — The skin that drew this node's card, as a row opening its source.
- **Skin** — Skin Configuration:Node dimensions, typography and label visibility.
- **Status** — Displays the validation and lifecycle status of the selected node.
- **Strategy** — One row per show-widget strategy, marked with the port's current choice.
- **Style** — The style fields of the selected edge, or a form applying to every selected edge.
- **Style** — The "Style…" row — a submenu with the connection's colour, line and arrow heads.
- **Style** — The connection's colour, line and arrow heads, where its connection type allows it.
- **Style** — The icon that drops the selected edges' colour, line and arrow heads above the toolbar.
- **Theme** — The node theme colouring this card, as a row opening its source.
- **Type** — The pin's data type, as a row that opens the type's source.
- **Widget** — The widget editing this pin, as a row that opens the widget's source.

## Editors
- **Graph Editor** — Visual node graph editor for wiring data processing pipelines.

## Skins
- **Inset** — The interior's stage, operable in the card
- **Split** — Configs across the top, inlets and outlets in columns side by side
- **Stacked** — One port column, outlets over configs over inlets, with collapsible groups
