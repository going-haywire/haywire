# Remove elements

`graph_editor:farmhand:remove_elements` · kind: farmhand

Remove nodes and/or edges (also the way to disconnect).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'nodes': {'type': 'array', 'items': {'type': 'string'}, 'default': []}, 'edges': {'type': 'array', 'items': {'type': 'string'}, 'default': []}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
