# Move nodes

`graph_editor:farmhand:move_nodes` · kind: farmhand

Move nodes to absolute positions ({node_id: {x, y}}).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'positions': {'type': 'object'}}, 'required': ['binding_id', 'positions']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
