# Remove elements

`haybale-graph-editor:farmhand:remove_elements` · kind: farmhand

Remove nodes and/or edges (also the way to disconnect).

## Agent Instructions

Remove nodes and/or edges from an open graph by id, in one call — pass nodes=[...] and/or edges=[...] (either or both, each defaults to empty). This is also how to disconnect two nodes: pass the edge_id under edges=. Removing a node also removes its own edges. Opens one undo fence and broadcasts to open studio UIs on success.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'nodes': {'type': 'array', 'items': {'type': 'string'}, 'default': []}, 'edges': {'type': 'array', 'items': {'type': 'string'}, 'default': []}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
