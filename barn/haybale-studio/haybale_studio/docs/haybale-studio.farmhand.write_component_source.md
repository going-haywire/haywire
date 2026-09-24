# Write component source

`haybale-studio:farmhand:write_component_source` · kind: farmhand

Full-source write into a project-local library only.

## Agent Instructions

Full-source write into a project-local library only. Haywire libraries the source imports are added to the library's linked_libraries first; the file watcher then registers or hot-reloads it, and the result reports registration ('added' | 'reloaded' | 'failed' | 'timeout'), the observed registry_key, ledger errors, linked_libraries_added and undeclared_imports (pyproject declarations `haywire share` will ask for). Follow with studio_verify_component.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'source': {'type': 'string'}, 'registry_key': {'type': 'string', 'default': None}, 'library': {'type': 'string', 'default': None}, 'kind': {'type': 'string', 'default': None}, 'filename': {'type': 'string', 'default': None}}, 'required': ['source']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': True, 'idempotent_hint': False, 'open_world_hint': False}`
