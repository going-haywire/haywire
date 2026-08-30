# Dismiss errors

`haybale-studio:farmhand:dismiss_errors` · kind: farmhand

Dismiss one or all ledger entries.

## Agent Instructions

Dismiss ledger entries: pass seq=<n> to remove one, or all=true to clear every retained entry. Removal is permanent for that entry but leaves the monotonic cursor untouched, so incremental since_seq polling stays correct. Broadcasts so open studio Errors editors refresh. Dismissing an absent seq is a no-op (idempotent).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'seq': {'type': 'integer', 'default': None}, 'all': {'type': 'boolean', 'default': False}}, 'required': []}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': True, 'open_world_hint': False}`
