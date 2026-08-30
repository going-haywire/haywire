# Block

`haybale-testing:farmhand:block` · kind: farmhand

Sleep off-loop for `seconds`.

## Agent Instructions

Sleep for `seconds` (default 1.0) off the event loop via ctx.offload(). Used to verify concurrent requests are not stalled by a blocking handler — not a real capability.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'seconds': {'type': 'number', 'default': 1.0}}, 'required': []}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
