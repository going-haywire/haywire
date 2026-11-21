# Release

`haybale-testing:farmhand:release` · kind: farmhand

Open a gate a Block call waits on.

## Agent Instructions

Open the gate named `gate` if a Block call is waiting on it. Returns `released: false` when no Block call waits on that gate yet. Used with Block to verify concurrent requests are not stalled — not a real capability.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'gate': {'type': 'string'}}, 'required': ['gate']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
