# Connect

`haybale-graph-editor:farmhand:connect` · kind: farmhand

Connect an outlet to an inlet.

## Agent Instructions

Create an edge from one node's outlet to another node's inlet, by exact pin id. Use graph_editor_inspect_node get=['ports'] on both endpoints first to find valid pin ids and confirm type compatibility — a bad id or an incompatible pair raises connect_failed. Opens one undo fence and broadcasts to open studio UIs on success.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'source_node_id': {'type': 'string'}, 'outlet': {'type': 'string'}, 'sink_node_id': {'type': 'string'}, 'inlet': {'type': 'string'}}, 'required': ['binding_id', 'source_node_id', 'outlet', 'sink_node_id', 'inlet']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
