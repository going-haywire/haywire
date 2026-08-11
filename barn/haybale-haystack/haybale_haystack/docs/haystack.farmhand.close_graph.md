# Close graph

`haystack:farmhand:close_graph` · kind: farmhand

Close an open graph entry. NEVER deletes the file on disk.

## Agent Instructions

Close an open graph session by binding_id, removing it from the open-entries list. NEVER deletes the file on disk — the graph can be reopened later with haystack_open_graph. Raises graph_not_found for an unknown binding_id.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
