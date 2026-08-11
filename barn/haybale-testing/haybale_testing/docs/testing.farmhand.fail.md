# Fail

`testing:farmhand:fail` · kind: farmhand

Always fails with a stable code.

## Agent Instructions

Always raises a FarmhandError with code 'testing_failure'. Used to exercise the structured error contract in tests — not a real capability. Never call this expecting a result.

## Details

- **input_schema**: `{'type': 'object', 'properties': {}, 'required': []}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
