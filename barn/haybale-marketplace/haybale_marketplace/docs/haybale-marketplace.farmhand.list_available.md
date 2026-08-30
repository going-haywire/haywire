# List available

`haybale-marketplace:farmhand:list_available` · kind: farmhand

Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache.

## Agent Instructions

Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache. Returns name/version/label/install_spec per row; pass detail=true for the full record (description, author, tags, dependencies, source_url, docs_url, ...).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'limit': {'type': 'integer', 'default': 50}, 'offset': {'type': 'integer', 'default': 0}, 'detail': {'type': 'boolean', 'default': False}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
