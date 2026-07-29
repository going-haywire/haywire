# Add node

`graph_editor:farmhand:add_node` · kind: farmhand

Add a node by registry key. Call studio_describe_component first to learn its ports.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'registry_key': {'type': 'string'}, 'x': {'type': 'number', 'default': 3750.0}, 'y': {'type': 'number', 'default': 3750.0}}, 'required': ['binding_id', 'registry_key']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
