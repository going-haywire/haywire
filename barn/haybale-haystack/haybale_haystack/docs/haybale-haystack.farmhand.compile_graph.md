# Compile graph

`haybale-haystack:farmhand:compile_graph` · kind: farmhand

Compile without starting; returns compile diagnostics.

## Agent Instructions

Compile an open graph WITHOUT starting execution — use this to check for compile errors before haystack_start_graph, since starting a broken graph wastes the destructive-side-effects warning for nothing. Returns compile.ok and compile.error (null when ok).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
