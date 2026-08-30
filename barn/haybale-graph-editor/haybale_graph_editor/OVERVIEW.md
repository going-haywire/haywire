# Graph Editor

Visual graph editor library — host-agnostic

## Farmhands
- **Add node** — Add a node by registry key. Call studio_describe_component first to learn its ports.
- **Connect** — Connect an outlet to an inlet.
- **Demote setting** — Remove a promoted port, returning the field to a plain setting.
- **Inspect node** — One node's ports, settings, and health, at a chosen depth.
- **Move nodes** — Move nodes to absolute positions ({node_id: {x, y}}).
- **Promote setting** — Promote a settings field to a data port. Not undo-routed (UI parity; later work).
- **Query graph** — Nodes (with ports) and edges of an open graph.
- **Redo** — Redo the last undone change on this graph's SHARED human+agent timeline.
- **Remove elements** — Remove nodes and/or edges (also the way to disconnect).
- **Set graph metadata** — Set a graph's document metadata (label, description, author, version).
- **Set property** — Set a node property (port value or settings field) by name. Undo-recorded.
- **Undo** — Undo the last change on this graph's SHARED human+agent timeline.

## States
- **Edit State** — 

## Panels
- **Appearance** — 
- **Collapse** — 
- **Collapse** — 
- **Connection Errors** — 
- **Connection Errors** — 
- **Connection Path** — 
- **Connection Warnings** — 
- **Connection Warnings** — 
- **Copy** — 
- **Copy Selection** — 
- **Create Node** — 
- **Delete** — 
- **Delete Connection** — 
- **Delete Selection** — 
- **Detach from setting** — 
- **Detail** — 
- **Detail Ranks** — 
- **Dissolve Reroute** — 
- **Execution Statistics** — 
- **Focus on Graph** — 
- **Graph Context** — 
- **Graph Info** — 
- **Graph Metadata** — 
- **Graph Settings** — 
- **Insert Reroute** — 
- **More** — 
- **More Actions** — 
- **Node Appearance** — 
- **Node Errors** — 
- **Node Errors** — 
- **Node Properties** — 
- **Node Properties** — 
- **Node Settings** — 
- **Paste** — 
- **Port Info** — 
- **Ports** — 
- **Rebuild** — 
- **Reconnect Edge** — 
- **Redraw Selection** — 
- **Reset Detail & Collapse** — 
- **Reset Node Cards** — 
- **Reset Selection** — 
- **Revalidate Selection** — 
- **Status** — 

## Editors
- **Graph Editor** — Visual node graph editor for wiring data processing pipelines.
