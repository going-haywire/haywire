# Query graph

`haybale-graph-editor:farmhand:query_graph` · kind: farmhand

Nodes (with ports) and edges of an open graph.

## Agent Instructions

Nodes (with ports) and edges of an open graph. Pass detail=true for the full per-port setup (data_type, takes_many_links, outgoing_takes_many on a swinglet only, single_link when set, is_linked, link_count, use_mode, promoted, has_widget, is_linked_lazy) AND per-edge health (is_functional, is_linked, propagation, propagation_locked, style, adapter_chain, has_adapters, error; style is the edge's colour, width, dash and heads for a styled edge, null otherwise); default returns the base id/direction/wire_type/role per port and id/topology/wire_type/role per edge.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'limit': {'type': 'integer', 'default': 100}, 'offset': {'type': 'integer', 'default': 0}, 'detail': {'type': 'boolean', 'default': False}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
