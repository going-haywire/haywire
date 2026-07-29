# Stop graph

`haystack:farmhand:stop_graph` · kind: farmhand

Stop a running graph (bounded grace, then teardown).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
