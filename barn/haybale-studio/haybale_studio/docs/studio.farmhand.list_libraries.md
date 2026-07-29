# List libraries

`studio:farmhand:list_libraries` · kind: farmhand

Installed libraries: id, label, version, description, tags, enabled. Synthetic libraries (dunder ids like '__system__') are excluded unless include_system=true.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'include_system': {'type': 'boolean', 'default': False}, 'limit': {'type': 'integer', 'default': 50}, 'offset': {'type': 'integer', 'default': 0}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
