# Add node

`graph_editor:farmhand:add_node` · kind: farmhand

Add a node by registry key. Call studio_describe_component first to learn its ports.

## Agent Instructions

Add a node instance to an open graph by registry_key, at an optional (x, y) canvas position (defaults near the origin). Call studio_describe_component or studio_list_components first to find a valid registry_key. Opens one undo fence and broadcasts to open studio UIs. Follow up with graph_editor_inspect_node to see the new node's ports/settings before wiring or setting them.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'registry_key': {'type': 'string'}, 'x': {'type': 'number', 'default': 3750.0}, 'y': {'type': 'number', 'default': 3750.0}}, 'required': ['binding_id', 'registry_key']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
