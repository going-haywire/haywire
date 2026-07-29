# Write component source

`studio:farmhand:write_component_source` · kind: farmhand

Full-source write into a project-local library only. Existing components are hot-reloaded by the file watcher; follow with studio_verify_component.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'source': {'type': 'string'}, 'registry_key': {'type': 'string', 'default': None}, 'library': {'type': 'string', 'default': None}, 'kind': {'type': 'string', 'default': None}, 'filename': {'type': 'string', 'default': None}}, 'required': ['source']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': False}`
