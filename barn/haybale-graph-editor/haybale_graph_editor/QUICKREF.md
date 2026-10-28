# haybale-graph-editor — component index (v0.2.4)

## setting
- `haybale-graph-editor:setting:NodeSkinSettings` — Node Skin — Settings controlling node layout and pin geometry.

## farmhand
- `haybale-graph-editor:farmhand:add_node` — Add node — Add a node by registry key. Call studio_describe_component first to learn its ports.
- `haybale-graph-editor:farmhand:connect` — Connect — Connect an outlet to an inlet.
- `haybale-graph-editor:farmhand:demote_setting` — Demote setting — Remove a promoted port, returning the field to a plain setting. One undo step.
- `haybale-graph-editor:farmhand:inspect_node` — Inspect node — One node's ports, settings, and health, at a chosen depth.
- `haybale-graph-editor:farmhand:move_nodes` — Move nodes — Move nodes to absolute positions ({node_id: {x, y}}).
- `haybale-graph-editor:farmhand:operate` — Operate widget — Change the value of a widget that is shown on a node card. Not undo-recorded.
- `haybale-graph-editor:farmhand:previous_setup` — Previous setup — Apply or dismiss the previous setup nodes kept through a hot reload. One undo step.
- `haybale-graph-editor:farmhand:promote_setting` — Promote setting — Promote a settings field to a data port. One undo step.
- `haybale-graph-editor:farmhand:query_graph` — Query graph — Nodes (with ports) and edges of an open graph.
- `haybale-graph-editor:farmhand:redo` — Redo — Redo the last undone change on this graph's SHARED human+agent timeline.
- `haybale-graph-editor:farmhand:remove_elements` — Remove elements — Remove nodes and/or edges (also the way to disconnect).
- `haybale-graph-editor:farmhand:set_metadata` — Set graph metadata — Set a graph's document metadata (label, description, author, version). One undo step.
- `haybale-graph-editor:farmhand:set_property` — Set property — Set a node property (port value or settings field) by name. Undo-recorded.
- `haybale-graph-editor:farmhand:undo` — Undo — Undo the last change on this graph's SHARED human+agent timeline.

## state
- `haybale-graph-editor:state:EditState` — Edit State — Per-session graph-editor state: selection, active items, clipboard.
- `haybale-graph-editor:state:GraphAppState` — Graph App State — 

## panel
- `haybale-graph-editor:panel:AddToStageMenuPanel` — Add to Stage — Put the selected nodes on the stage; offered when the selection holds an off-stage node.
- `haybale-graph-editor:panel:AppearanceToolbarPanel` — Appearance — The ⧉ icon that drops the appearance fields above the toolbar.
- `haybale-graph-editor:panel:ArrangeSelectionMenuPanel` — Arrange — The "Arrange" row: a submenu over the stacking-order verbs.
- `haybale-graph-editor:panel:BringForwardMenuPanel` — Bring Forward — Move each selected node one step up: above the next node over it.
- `haybale-graph-editor:panel:BringToFrontMenuPanel` — Bring to Front — Paint the selected nodes above every other node in this view.
- `haybale-graph-editor:panel:ClearDetailOverridesMenuPanel` — Reset Detail — Drop each selected node's own detail rank, so it follows the graph's again.
- `haybale-graph-editor:panel:ClearSettingMenuPanel` — Set to none — Clear the backing setting to absence (OPTIONAL[T] fields only).
- `haybale-graph-editor:panel:CloneToLibraryMenuPanel` — Clone to Library — Write a copy of this node's class into a library, as a new node to edit.
- `haybale-graph-editor:panel:CollapseSelectionMenuPanel` — Fold — Fold or unfold every selected node — one row, both directions.
- `haybale-graph-editor:panel:CollapseToGroupMenuPanel` — Collapse to Group — Collapse the selection into one Graph-node standing for a Subgraph.
- `haybale-graph-editor:panel:CollapseToolbarPanel` — Fold — One button that folds or unfolds the selection.
- `haybale-graph-editor:panel:CopySelectionMenuPanel` — Copy Selection — Copy the selected nodes and edges to the clipboard.
- `haybale-graph-editor:panel:CreateNodeMenuPanel` — Create Node — The hierarchical node-creation menu, search and tree together.
- `haybale-graph-editor:panel:DeleteEdgeMenuPanel` — Delete Connection — Delete the right-clicked connection.
- `haybale-graph-editor:panel:DeleteSelectionMenuPanel` — Delete Selection — Delete every node and edge in the current selection in one undoable step.
- `haybale-graph-editor:panel:DetachSettingMenuPanel` — Detach from setting — Removes a pin the user added, on the pin that carries it.
- `haybale-graph-editor:panel:DetailRankMenuPanel` — Detail Ranks — One row per node detail rank.
- `haybale-graph-editor:panel:DetailSelectionMenuPanel` — Detail — The "Detail" row — a submenu over the density ranks.
- `haybale-graph-editor:panel:DevelopSelectionMenuPanel` — Develop — The "Develop" row — a submenu over the node's source, cloning it, and rebuilding.
- `haybale-graph-editor:panel:DissolveRerouteMenuPanel` — Dissolve Reroute — Collapse a reroute node back into a direct connection.
- `haybale-graph-editor:panel:EdgeAdapterChainPanel` — Adapter Chain — List the adapters converting the source value to the sink type, in order.
- `haybale-graph-editor:panel:EdgeAdapterEditMenuPanel` — Adapters — One row per adapter in the edge's chain, each opening its source.
- `haybale-graph-editor:panel:EdgeErrorsMenuPanel` — Connection Errors — Edge errors panel for the context menu (right-click on edge).
- `haybale-graph-editor:panel:EdgeErrorsPanel` — Connection Errors — Edge errors panel for PropertiesEditor.
- `haybale-graph-editor:panel:EdgePathPanel` — Connection Path — The source and target pins of the selected connection.
- `haybale-graph-editor:panel:EdgePropagationMenuPanel` — Propagation — Lazy propagation pulls data on demand instead of pushing it to the target node.
- `haybale-graph-editor:panel:EdgePropagationPanel` — Propagation — Switch the edge between eager and lazy propagation, or show the mode it is fixed to.
- `haybale-graph-editor:panel:EdgeStatsPanel` — Execution Statistics — Execution count, average time and test value of the selected connection.
- `haybale-graph-editor:panel:EdgeStyleBodyPanel` — Style — The style fields of the selected edge, or a form applying to every selected edge.
- `haybale-graph-editor:panel:EdgeStyleMenuPanel` — Style — The "Style…" row — a submenu with the connection's colour, line and arrow heads.
- `haybale-graph-editor:panel:EdgeStylePanel` — Style — The connection's colour, line and arrow heads, where its connection type allows it.
- `haybale-graph-editor:panel:EdgeStyleToolbarPanel` — Style — The icon that drops the selected edges' colour, line and arrow heads above the toolbar.
- `haybale-graph-editor:panel:EdgeWarningsMenuPanel` — Connection Warnings — Edge warnings panel for the context menu.
- `haybale-graph-editor:panel:EdgeWarningsPanel` — Connection Warnings — Edge warnings panel for PropertiesEditor.
- `haybale-graph-editor:panel:EditEdgeMenuPanel` — Edit Source — The "Edit Source" row — a submenu over the adapters behind this edge.
- `haybale-graph-editor:panel:EditInstanceMenuPanel` — Edit Instance — Turn one macro placement into a modified instance and enter it.
- `haybale-graph-editor:panel:EditSelectionMenuPanel` — Edit Source — The "Edit Source" row — a submenu over the components behind this node.
- `haybale-graph-editor:panel:EnterMenuPanel` — Enter — Enter a Group or a macro placement: open its inside as a level of the graph editor.
- `haybale-graph-editor:panel:FocusGraphPanel` — Focus on Graph — Fit the viewport to show every node in the graph, as an icon shortcut.
- `haybale-graph-editor:panel:GraphContextPanel` — Graph Context — Layout-only root of the canvas menu: shortcut row, then prime area.
- `haybale-graph-editor:panel:GraphInfoPanel` — Graph Info — Displays counts and framework-written metadata for the active graph.
- `haybale-graph-editor:panel:GraphMetadataPanel` — Graph Metadata — Renders the metadata of the active graph.
- `haybale-graph-editor:panel:GraphMorePanel` — More Actions — The "…" — a panel that is itself a host.
- `haybale-graph-editor:panel:GraphSettingsPanel` — Graph Settings — Renders the properties of the active graph.
- `haybale-graph-editor:panel:GroupMenuPanel` — Expand Group — Expand a Group back into the graph around it.
- `haybale-graph-editor:panel:InsertRerouteMenuPanel` — Insert Reroute — Split the active edge and insert a reroute node in between. Available for every edge.
- `haybale-graph-editor:panel:LockToolbarPanel` — Lock — Lock or unlock one node, as protection against accidental manipulation.
- `haybale-graph-editor:panel:MacroSelectionMenuPanel` — Macro — The "Macro" row — a submenu over the verbs between a card and a macro.
- `haybale-graph-editor:panel:ModifiedInstanceMenuPanel` — Modified instance — Offer to put a modified instance back to its macro, or to cut it loose.
- `haybale-graph-editor:panel:NewNodeToolbarPanel` — New Node — Open the New Node wizard, as an icon shortcut.
- `haybale-graph-editor:panel:NodeAppearancePanel` — Appearance — The selected node's appearance props, or a form applying to every selected node.
- `haybale-graph-editor:panel:NodeErrorsPanel` — Node Errors — Node errors panel for PropertiesEditor.
- `haybale-graph-editor:panel:NodeErrorsSelectionMenuPanel` — Node Errors — Node errors panel for the unified selection context menu.
- `haybale-graph-editor:panel:NodeInfoPanel` — Node Info — Displays basic identity information for the selected node.
- `haybale-graph-editor:panel:NodePortsPanel` — Ports — Displays the inlet, outlet, and config ports of the selected node.
- `haybale-graph-editor:panel:NodePreviousSetupPanel` — Settings reset by a code change — Restore or discard the settings the active node had before a code change rebuilt it.
- `haybale-graph-editor:panel:NodePropertiesPanel` — Node Properties — Displays per-instance node settings (collapsed, locked, skin, etc.).
- `haybale-graph-editor:panel:NodeSettingsPanel` — Node Settings — Discovers and renders all user-defined settings on the selected node.
- `haybale-graph-editor:panel:NodeSkinMenuPanel` — Skin — The skin that drew this node's card, as a row opening its source.
- `haybale-graph-editor:panel:NodeSkinSettingsPanel` — Skin — Skin Configuration:Node dimensions, typography and label visibility.
- `haybale-graph-editor:panel:NodeSourceMenuPanel` — Node — The node class itself, as a row that opens its source.
- `haybale-graph-editor:panel:NodeStatusPanel` — Status — Displays the validation and lifecycle status of the selected node.
- `haybale-graph-editor:panel:NodeThemeMenuPanel` — Theme — The node theme colouring this card, as a row opening its source.
- `haybale-graph-editor:panel:PastePanel` — Paste — Paste at the click position, as an icon shortcut.
- `haybale-graph-editor:panel:PinEditMenuPanel` — Edit Source — The "Edit Source" row — a submenu over the components behind this pin.
- `haybale-graph-editor:panel:PinShowWidgetMenuPanel` — Show widget — The "Show widget ▸" row — picks when this pin's Widget is rendered.
- `haybale-graph-editor:panel:PortShowWidgetStrategyPanel` — Strategy — One row per show-widget strategy, marked with the port's current choice.
- `haybale-graph-editor:panel:PortTypeMenuPanel` — Type — The pin's data type, as a row that opens the type's source.
- `haybale-graph-editor:panel:PortWidgetMenuPanel` — Widget — The widget editing this pin, as a row that opens the widget's source.
- `haybale-graph-editor:panel:PreviousSetupSelectionMenuPanel` — Settings reset by a code change — Restore or discard the settings the active node had before a code change rebuilt it.
- `haybale-graph-editor:panel:RebuildSelectionMenuPanel` — Rebuild — The "Rebuild" row — a submenu over redraw / revalidate / reset.
- `haybale-graph-editor:panel:ReconnectEdgeMenuPanel` — Reconnect Edge — Removes the edge and starts a new connection drag from the anchor pin.
- `haybale-graph-editor:panel:RedrawSelectionMenuPanel` — Redraw Selection — Redraw every node/edge in the selection in one step.
- `haybale-graph-editor:panel:RemoveFromStageMenuPanel` — Remove from Stage — Take the selected nodes off the stage; offered when the selection holds an on-stage node.
- `haybale-graph-editor:panel:ResetNodeCardsMenuPanel` — Reset Node Detail — Make every node in the graph follow the graph's detail rank again.
- `haybale-graph-editor:panel:ResetSelectionMenuPanel` — Reset Selection — Reset every node/edge in the selection in one step.
- `haybale-graph-editor:panel:ResetSettingMenuPanel` — Reset to default — Put the backing setting back to its declared default, from the pin.
- `haybale-graph-editor:panel:RevalidateSelectionMenuPanel` — Revalidate Selection — Revalidate every node/edge in the selection in one step.
- `haybale-graph-editor:panel:SaveNewMacroMenuPanel` — Save new Macro — Save a Group as a new macro. Only visible when the right-clicked node is a Graph-node.
- `haybale-graph-editor:panel:SelectionOverflowPanel` — More — The ⋯ — a panel that hosts the selection right-click menu.
- `haybale-graph-editor:panel:SendBackwardMenuPanel` — Send Backward — Move each selected node one step down: below the next node under it.
- `haybale-graph-editor:panel:SendToBackMenuPanel` — Send to Back — Paint the selected nodes below every other node in this view.

## editor
- `haybale-graph-editor:editor:GraphEditor` — Graph Editor — Visual node graph editor for wiring data processing pipelines.

## skin
- `haybale-graph-editor:skin:InsetSkin` — Inset — The interior's stage, operable in the card
- `haybale-graph-editor:skin:SplitNodeSkin` — Split — Configs across the top, inlets and outlets in columns side by side
- `haybale-graph-editor:skin:StackedNodeSkin` — Stacked — One port column, outlets over configs over inlets, with collapsible groups
