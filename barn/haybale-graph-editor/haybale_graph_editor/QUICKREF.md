# haybale-graph-editor — component index (v0.1.3)

## farmhand
- `haybale-graph-editor:farmhand:add_node` — Add node — Add a node by registry key. Call studio_describe_component first to learn its ports.
- `haybale-graph-editor:farmhand:connect` — Connect — Connect an outlet to an inlet.
- `haybale-graph-editor:farmhand:demote_setting` — Demote setting — Remove a promoted port, returning the field to a plain setting.
- `haybale-graph-editor:farmhand:inspect_node` — Inspect node — One node's ports, settings, and health, at a chosen depth.
- `haybale-graph-editor:farmhand:move_nodes` — Move nodes — Move nodes to absolute positions ({node_id: {x, y}}).
- `haybale-graph-editor:farmhand:promote_setting` — Promote setting — Promote a settings field to a data port. Not undo-routed (UI parity; later work).
- `haybale-graph-editor:farmhand:query_graph` — Query graph — Nodes (with ports) and edges of an open graph.
- `haybale-graph-editor:farmhand:redo` — Redo — Redo the last undone change on this graph's SHARED human+agent timeline.
- `haybale-graph-editor:farmhand:remove_elements` — Remove elements — Remove nodes and/or edges (also the way to disconnect).
- `haybale-graph-editor:farmhand:set_metadata` — Set graph metadata — Set a graph's document metadata (label, description, author, version).
- `haybale-graph-editor:farmhand:set_property` — Set property — Set a node property (port value or settings field) by name. Undo-recorded.
- `haybale-graph-editor:farmhand:undo` — Undo — Undo the last change on this graph's SHARED human+agent timeline.

## state
- `haybale-graph-editor:state:EditState` — Edit State — 

## panel
- `haybale-graph-editor:panel:AppearanceToolbarPanel` — Appearance — 
- `haybale-graph-editor:panel:ClearDetailOverridesMenuPanel` — Reset Detail & Collapse — 
- `haybale-graph-editor:panel:CollapseSelectionMenuPanel` — Collapse — 
- `haybale-graph-editor:panel:CollapseToolbarPanel` — Collapse — 
- `haybale-graph-editor:panel:CopySelectionMenuPanel` — Copy Selection — 
- `haybale-graph-editor:panel:CopyToolbarPanel` — Copy — 
- `haybale-graph-editor:panel:CreateNodeMenuPanel` — Create Node — 
- `haybale-graph-editor:panel:DeleteEdgeMenuPanel` — Delete Connection — 
- `haybale-graph-editor:panel:DeleteSelectionMenuPanel` — Delete Selection — 
- `haybale-graph-editor:panel:DeleteToolbarPanel` — Delete — 
- `haybale-graph-editor:panel:DetachSettingMenuPanel` — Detach from setting — 
- `haybale-graph-editor:panel:DetailRankMenuPanel` — Detail Ranks — 
- `haybale-graph-editor:panel:DetailSelectionMenuPanel` — Detail — 
- `haybale-graph-editor:panel:DissolveRerouteMenuPanel` — Dissolve Reroute — 
- `haybale-graph-editor:panel:EdgeErrorsMenuPanel` — Connection Errors — 
- `haybale-graph-editor:panel:EdgeErrorsPanel` — Connection Errors — 
- `haybale-graph-editor:panel:EdgePathPanel` — Connection Path — 
- `haybale-graph-editor:panel:EdgeStatsPanel` — Execution Statistics — 
- `haybale-graph-editor:panel:EdgeWarningsMenuPanel` — Connection Warnings — 
- `haybale-graph-editor:panel:EdgeWarningsPanel` — Connection Warnings — 
- `haybale-graph-editor:panel:FocusGraphPanel` — Focus on Graph — 
- `haybale-graph-editor:panel:GraphContextPanel` — Graph Context — 
- `haybale-graph-editor:panel:GraphInfoPanel` — Graph Info — 
- `haybale-graph-editor:panel:GraphMetadataPanel` — Graph Metadata — 
- `haybale-graph-editor:panel:GraphMorePanel` — More Actions — 
- `haybale-graph-editor:panel:GraphSettingsPanel` — Graph Settings — 
- `haybale-graph-editor:panel:InsertRerouteMenuPanel` — Insert Reroute — 
- `haybale-graph-editor:panel:NodeAppearancePanel` — Node Appearance — 
- `haybale-graph-editor:panel:NodeErrorsPanel` — Node Errors — 
- `haybale-graph-editor:panel:NodeErrorsSelectionMenuPanel` — Node Errors — 
- `haybale-graph-editor:panel:NodeInfoPanel` — Node Properties — 
- `haybale-graph-editor:panel:NodePortsPanel` — Ports — 
- `haybale-graph-editor:panel:NodePropertiesPanel` — Node Properties — 
- `haybale-graph-editor:panel:NodeSettingsPanel` — Node Settings — 
- `haybale-graph-editor:panel:NodeStatusPanel` — Status — 
- `haybale-graph-editor:panel:PastePanel` — Paste — 
- `haybale-graph-editor:panel:PortInfoMenuPanel` — Port Info — 
- `haybale-graph-editor:panel:RebuildSelectionMenuPanel` — Rebuild — 
- `haybale-graph-editor:panel:ReconnectEdgeMenuPanel` — Reconnect Edge — 
- `haybale-graph-editor:panel:RedrawSelectionMenuPanel` — Redraw Selection — 
- `haybale-graph-editor:panel:ResetNodeCardsMenuPanel` — Reset Node Cards — 
- `haybale-graph-editor:panel:ResetSelectionMenuPanel` — Reset Selection — 
- `haybale-graph-editor:panel:RevalidateSelectionMenuPanel` — Revalidate Selection — 
- `haybale-graph-editor:panel:SelectionOverflowPanel` — More — 

## editor
- `haybale-graph-editor:editor:GraphEditor` — Graph Editor — Visual node graph editor for wiring data processing pipelines.
