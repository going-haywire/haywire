# Get errors

`studio:farmhand:get_errors` · kind: farmhand

Query the studio's error ledger (since_seq/library/registry_key filters); results carry the current cursor for incremental polling and first_retained_seq so a client can detect when older history was evicted or deleted.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'since_seq': {'type': 'integer', 'default': None}, 'library': {'type': 'string', 'default': None}, 'registry_key': {'type': 'string', 'default': None}, 'limit': {'type': 'integer', 'default': 50}, 'offset': {'type': 'integer', 'default': 0}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
