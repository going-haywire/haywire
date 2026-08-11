# Get library docs

`marketplace:farmhand:get_library_docs` · kind: farmhand

Docs for an installed library (OVERVIEW/QUICKREF/README) or an available one.

## Agent Instructions

Docs for an installed library (OVERVIEW/QUICKREF/README from its folder) or an available one (network fetch of its docs_url). Pass component=<registry_key> to fetch one component's deep doc (installed: wheel; available: docs_url). Long documents are truncated at 12000 chars with total_chars reported; pass full=true for everything.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'library': {'type': 'string'}, 'component': {'type': 'string', 'default': ''}, 'full': {'type': 'boolean', 'default': False}}, 'required': ['library']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': True}`
