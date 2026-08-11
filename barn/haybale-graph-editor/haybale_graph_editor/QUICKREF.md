# graph_editor — component index (v0.1.0)

## farmhand
- `graph_editor:farmhand:add_node` — Add node — Add a node by registry key. Call studio_describe_component first to learn its ports.
- `graph_editor:farmhand:connect` — Connect — Connect an outlet to an inlet.
- `graph_editor:farmhand:demote_setting` — Demote setting — Remove a promoted port, returning the field to a plain setting.
- `graph_editor:farmhand:inspect_node` — Inspect node — One node's ports, settings, and health, at a chosen depth.
- `graph_editor:farmhand:move_nodes` — Move nodes — Move nodes to absolute positions ({node_id: {x, y}}).
- `graph_editor:farmhand:promote_setting` — Promote setting — Promote a settings field to a data port. Not undo-routed (UI parity; later work).
- `graph_editor:farmhand:query_graph` — Query graph — Nodes (with ports) and edges of an open graph.
- `graph_editor:farmhand:redo` — Redo — Redo the last undone change on this graph's SHARED human+agent timeline.
- `graph_editor:farmhand:remove_elements` — Remove elements — Remove nodes and/or edges (also the way to disconnect).
- `graph_editor:farmhand:set_property` — Set property — Set a node property (port value or settings field) by name. Undo-recorded.
- `graph_editor:farmhand:undo` — Undo — Undo the last change on this graph's SHARED human+agent timeline.

## state
- `graph_editor:state:EditState` — Edit State — 

## panel
- `graph_editor:panel:CopySelectionMenuPanel` — Copy Selection — 
- `graph_editor:panel:CopyToolbarPanel` — Copy — 
- `graph_editor:panel:CreateNodeMenuPanel` — Create Node — 
- `graph_editor:panel:DeleteEdgeMenuPanel` — Delete Connection — 
- `graph_editor:panel:DeleteSelectionMenuPanel` — Delete Selection — 
- `graph_editor:panel:DeleteToolbarPanel` — Delete — 
- `graph_editor:panel:DetachSettingMenuPanel` — Detach from setting — 
- `graph_editor:panel:DissolveRerouteMenuPanel` — Dissolve Reroute — 
- `graph_editor:panel:EdgeErrorsMenuPanel` — Connection Errors — 
- `graph_editor:panel:EdgeErrorsPanel` — Connection Errors — 
- `graph_editor:panel:EdgePathPanel` — Connection Path — 
- `graph_editor:panel:EdgeStatsPanel` — Execution Statistics — 
- `graph_editor:panel:EdgeWarningsMenuPanel` — Connection Warnings — 
- `graph_editor:panel:EdgeWarningsPanel` — Connection Warnings — 
- `graph_editor:panel:GraphInfoPanel` — Graph Info — 
- `graph_editor:panel:GraphSettingsPanel` — Graph Settings — 
- `graph_editor:panel:InsertRerouteMenuPanel` — Insert Reroute — 
- `graph_editor:panel:NodeErrorsPanel` — Node Errors — 
- `graph_editor:panel:NodeErrorsSelectionMenuPanel` — Node Errors — 
- `graph_editor:panel:NodeInfoPanel` — Node Properties — 
- `graph_editor:panel:NodePortsPanel` — Ports — 
- `graph_editor:panel:NodePropertiesPanel` — Node Properties — 
- `graph_editor:panel:NodeSettingsPanel` — Node Settings — 
- `graph_editor:panel:NodeStatusPanel` — Status — 
- `graph_editor:panel:OverflowToolbarPanel` — More — 
- `graph_editor:panel:PasteMenuPanel` — Paste — 
- `graph_editor:panel:PortInfoMenuPanel` — Port Info — 
- `graph_editor:panel:ReconnectEdgeMenuPanel` — Reconnect Edge — 
- `graph_editor:panel:RedrawSelectionMenuPanel` — Redraw Selection — 
- `graph_editor:panel:ResetSelectionMenuPanel` — Reset Selection — 
- `graph_editor:panel:RevalidateSelectionMenuPanel` — Revalidate Selection — 

## editor
- `graph_editor:editor:GraphEditor` — Graph Editor — Visual node graph editor for wiring data processing pipelines.
