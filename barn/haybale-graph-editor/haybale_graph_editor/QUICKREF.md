# graph_editor — component index (v0.0.30)

## farmhand
- `graph_editor:farmhand:add_node` — Add node — Add a node by registry key. Call studio_describe_component first to learn its ports.
- `graph_editor:farmhand:connect` — Connect — Connect an outlet to an inlet.
- `graph_editor:farmhand:demote_setting` — Demote setting — Remove a promoted port, returning the field to a plain setting.
- `graph_editor:farmhand:inspect_node` — Inspect node — Drill down on ONE node in three steps — name only the sections and depth you need, because a node can carry 30+ settings fields and an unfocused call wastes most of what it returns. The read counterpart to graph_editor_set_property: a row's 'name' is exactly what you pass back as name=, and it joins a row across all depths.
Typical drill-down: get=['summary'] (returns setting_counts per bag, so you can see which bags are big) -> get=['settings'] by_bag=['the_relevant_bag'] at data='info' to learn what exists -> data='value' or 'all' with by_name=['the_one_field'].
get: any of summary, node_id, ports, settings, props, state (required, non-empty)
  summary: always returned — identity, per-bag setting_counts, validity (name it alone for a cheap survey)
  node_id: node_id + registry_key
  ports: ports grouped as inlets/outlets/configs
  settings: author-declared settings bags, nested {bag: {category: [rows]}} at data='info' and {bag: [rows]} deeper — never a flat list, so bag identity is always explicit
  props: framework properties (position, size, muted, skin) — never mixed into settings
  state: is_valid + per-stage lifecycle booleans + errors [{stage, message}] + warnings; read this after editing a node's source to learn WHICH stage failed
data: one of info, value, all (default info) — how much per row
  info: what it IS — label, description, category/data_type. NO values. Start here.
  value: what it is SET to — value, is_set, default, is_linked
  all: value plus everything writable — type, min/max/options, mirrors, ui_state, use_mode, validator
Four independent filters, ANDed together (each defaults to [] = no constraint). Values that match nothing on this node come back under 'unmatched', keyed by which filter missed.
  by_name: exact field or port names, e.g. ['confidence_threshold']
  by_bag: settings-bag accessors, e.g. ['depth'] returns that whole bag (see the per-bag counts in summary to pick one)
  by_category: author category labels, e.g. ['Exposure']
  by_dir: port directions, any of inlet, outlet, config — PORTS ONLY. Ports carry no bag or category, so by_bag/by_category exclude them outright; combining either with by_dir returns no ports and reports by_dir under 'unmatched'.
Value notes: a port holding a non-JSON value (mesh, frame) reports value_omitted instead of value. A field hidden by its node's own gating (e.g. a disabled feature flag) is NOT shown to the user either, so it collapses to {name, ui_state:'hidden'} — name it in by_name to expand it. is_set=false means the field INHERITS its value — writing the same value back is a silent no-op. min/max are UI hints and are NOT enforced on writes. The validator IS enforced: at data='all' a field carrying one reports validator {name, doc} — the predicate is opaque, so you cannot pre-check a value, and a rejected write is dropped silently by the framework; set_property verifies the write and reports the rejection.
- `graph_editor:farmhand:move_nodes` — Move nodes — Move nodes to absolute positions ({node_id: {x, y}}).
- `graph_editor:farmhand:promote_setting` — Promote setting — Promote a settings field to a data port. Not undo-routed (UI parity; later work).
- `graph_editor:farmhand:query_graph` — Query graph — Nodes (with ports) and edges of an open graph. Pass detail=true for the full per-port setup (data_type, allow_multiple_links, is_linked, link_count, use_mode, promoted, has_widget, is_linked_lazy) AND per-edge health (is_functional, is_linked, is_lazy, adapter_chain, has_adapters, error); default returns the base id/direction/flow_type per port and id/topology/flow_type per edge.
- `graph_editor:farmhand:redo` — Redo — Redo the last undone change on this graph's SHARED human+agent timeline.
- `graph_editor:farmhand:remove_elements` — Remove elements — Remove nodes and/or edges (also the way to disconnect).
- `graph_editor:farmhand:set_property` — Set property — Set a node property (port value or settings field) by name. Undo-recorded. 'name' resolves to a port id first, then a settings field — use the exact 'name' from a graph_editor_inspect_node row. The write is verified by reading the value back: a value rejected by the field's validator raises set_rejected rather than reporting a success that did not happen. Note min/max are UI hints only and are NOT enforced — an out-of-range write succeeds, so respect the bounds inspect_node reports.
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
