# Save graph

`haystack:farmhand:save_graph` · kind: farmhand

Save an open graph; save_as writes to a new path.

## Agent Instructions

Save an open graph (by binding_id) to its current path. Pass save_as=<path> (relative to the workspace root) to write to a new path instead — e.g. to save an untitled graph from haystack_create_graph for the first time. Raises graph_not_found for an unknown binding_id, save_failed if the write itself fails.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'save_as': {'type': 'string', 'default': None}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
