# List libraries

`studio:farmhand:list_libraries` · kind: farmhand

List installed libraries.

## Agent Instructions

Installed libraries: id, label, version, enabled. Pass detail=true to add description and tags. Synthetic libraries (dunder ids like '__system__') are excluded unless include_system=true.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'include_system': {'type': 'boolean', 'default': False}, 'limit': {'type': 'integer', 'default': 50}, 'offset': {'type': 'integer', 'default': 0}, 'detail': {'type': 'boolean', 'default': False}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
