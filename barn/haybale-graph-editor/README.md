# Graph Editor

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save`.*
<!-- marketstall:share-url:end -->

Graph editor library for Haywire — host-agnostic visual graph editing

## Farmhands
- **Add node** — Add a node by registry key. Call studio_describe_component first to learn its ports.
- **Connect** — Connect an outlet to an inlet.
- **Demote setting** — Remove a promoted port, returning the field to a plain setting.
- **Inspect node** — Drill down on ONE node in three steps — name only the sections and depth you need, because a node can carry 30+ settings fields and an unfocused call wastes most of what it returns. The read counterpart to graph_editor_set_property: a row's 'name' is exactly what you pass back as name=, and it joins a row across all depths.
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
- **Move nodes** — Move nodes to absolute positions ({node_id: {x, y}}).
- **Promote setting** — Promote a settings field to a data port. Not undo-routed (UI parity; later work).
- **Query graph** — Nodes (with ports) and edges of an open graph. Pass detail=true for the full per-port setup (data_type, allow_multiple_links, is_linked, link_count, use_mode, promoted, has_widget, is_linked_lazy) AND per-edge health (is_functional, is_linked, is_lazy, adapter_chain, has_adapters, error); default returns the base id/direction/flow_type per port and id/topology/flow_type per edge.
- **Redo** — Redo the last undone change on this graph's SHARED human+agent timeline.
- **Remove elements** — Remove nodes and/or edges (also the way to disconnect).
- **Set property** — Set a node property (port value or settings field) by name. Undo-recorded. 'name' resolves to a port id first, then a settings field — use the exact 'name' from a graph_editor_inspect_node row. The write is verified by reading the value back: a value rejected by the field's validator raises set_rejected rather than reporting a success that did not happen. Note min/max are UI hints only and are NOT enforced — an out-of-range write succeeds, so respect the bounds inspect_node reports.
- **Undo** — Undo the last change on this graph's SHARED human+agent timeline.
