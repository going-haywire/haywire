# Uninstall library

`haybale-marketplace:farmhand:uninstall_library` · kind: farmhand

Uninstall an installed library via uv pip (streams progress). Destructive.

## Agent Instructions

Uninstall an installed library by library_id via uv pip (streams progress). DESTRUCTIVE: changes the venv, and any graphs using this library's components will break. Raises uninstall_failed with the underlying message on failure. On success, returns on_reload naming the follow-up action and broadcasts a catalog-changed signal.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'library_id': {'type': 'string'}}, 'required': ['library_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': False}`
