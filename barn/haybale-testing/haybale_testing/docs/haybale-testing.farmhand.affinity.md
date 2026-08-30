# Affinity

`haybale-testing:farmhand:affinity` · kind: farmhand

Report handler thread and loop.

## Agent Instructions

Report which thread and asyncio loop the handler ran on. Read-only, no side effects — used to verify Farmhand call-path threading behavior in tests, not a real capability.

## Details

- **input_schema**: `{'type': 'object', 'properties': {}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
