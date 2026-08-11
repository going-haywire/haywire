# Stop graph

`haystack:farmhand:stop_graph` · kind: farmhand

Stop a running graph (bounded grace, then teardown).

## Agent Instructions

Stop a running graph by binding_id: gives nodes a bounded grace period to shut down cleanly, then tears down execution. Safe to call on a graph that is not currently running.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
