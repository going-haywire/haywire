# Start graph

`haystack:farmhand:start_graph` · kind: farmhand

Compile and start execution. Destructive: nodes perform real I/O.

## Agent Instructions

Compile and start executing an open graph. DESTRUCTIVE — nodes perform real I/O once running (hardware, network, file writes), not a dry run. Consider haystack_compile_graph first to catch compile errors without side effects. Follow with haystack_stop_graph when done.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': False}`
