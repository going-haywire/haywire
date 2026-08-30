# Echo

`haybale-testing:farmhand:echo` · kind: farmhand

Echo text back (canned read tool).

## Agent Instructions

Echo the given text back unchanged. Read-only, no side effects — used to exercise the Farmhand call path in tests, not a real capability.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
