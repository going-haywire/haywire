# Graph Editor

Visual graph editor library — host-agnostic

## Settings
- **Node Skin** — 

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
- **Edit State** — 

## Panels
- **Adapter Chain** — 
- **Adapters** — 
- **Add to Stage** — 
- **Appearance** — 
- **Appearance** — 
- **Arrange** — 
- **Bring Forward** — 
- **Bring to Front** — 
- **Clone to Library** — 
- **Collapse** — 
- **Collapse** — 
- **Collapse to Group** — 
- **Connection Errors** — 
- **Connection Errors** — 
- **Connection Path** — 
- **Connection Warnings** — 
- **Connection Warnings** — 
- **Copy Selection** — 
- **Create Node** — 
- **Delete Connection** — 
- **Delete Selection** — 
- **Detach from setting** — 
- **Detail** — 
- **Detail Ranks** — 
- **Dissolve Reroute** — 
- **Edit** — 
- **Edit** — 
- **Edit** — 
- **Edit Instance** — 
- **Enter** — 
- **Execution Statistics** — 
- **Focus on Graph** — 
- **Graph Context** — 
- **Graph Info** — 
- **Graph Metadata** — 
- **Graph Settings** — 
- **Group** — 
- **Insert Reroute** — 
- **Lock** — 
- **Modified instance** — 
- **More** — 
- **More Actions** — 
- **New Node** — 
- **Node** — 
- **Node Errors** — 
- **Node Errors** — 
- **Node Info** — 
- **Node Properties** — 
- **Node Settings** — 
- **Paste** — 
- **Ports** — 
- **Propagation** — Lazy propagation pulls data on demand instead of pushing it to the target node.
- **Propagation** — 
- **Rebuild** — 
- **Reconnect Edge** — 
- **Redraw Selection** — 
- **Remove from Stage** — 
- **Reset Detail** — 
- **Reset Node Detail** — 
- **Reset Selection** — 
- **Reset to default** — 
- **Revalidate Selection** — 
- **Send Backward** — 
- **Send to Back** — 
- **Set to none** — 
- **Show widget** — 
- **Skin** — 
- **Skin** — Skin Configuration:Node dimensions, typography and label visibility.
- **Status** — 
- **Strategy** — 
- **Style** — 
- **Style** — 
- **Style** — 
- **Style** — 
- **Theme** — 
- **Type** — 
- **Widget** — 

## Editors
- **Graph Editor** — Visual node graph editor for wiring data processing pipelines.

## Skins
- **Inset** — The interior's stage, operable in the card
- **Split** — Configs across the top, inlets and outlets in columns side by side
- **Stacked** — One port column, outlets over configs over inlets, with collapsible groups
