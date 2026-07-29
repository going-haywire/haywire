# Uninstall library

`marketplace:farmhand:uninstall_library` · kind: farmhand

Uninstall an installed library via uv pip (streams progress). Destructive.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'library_id': {'type': 'string'}}, 'required': ['library_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': False}`
