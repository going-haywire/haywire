# Start graph

`haystack:farmhand:start_graph` · kind: farmhand

Compile and start execution. Destructive: nodes perform real I/O.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': False}`
