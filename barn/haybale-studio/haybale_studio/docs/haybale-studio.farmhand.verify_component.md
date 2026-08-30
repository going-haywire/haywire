# Verify component

`haybale-studio:farmhand:verify_component` · kind: farmhand

Staged verification that a component registers and runs cleanly.

## Agent Instructions

Staged verification: registered -> (nodes) trial instantiation -> on_testrun(); error-ledger entries from the failing stage are attached.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'registry_key': {'type': 'string'}}, 'required': ['registry_key']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
