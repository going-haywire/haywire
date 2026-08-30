# Read component source

`haybale-studio:farmhand:read_component_source` · kind: farmhand

Line-numbered source of any installed component.

## Agent Instructions

Line-numbered source of any installed component. Returns the first 400 lines by default; pass offset= to window further in, or full=true for the entire file. Truncated results say so in the summary and report total_lines.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'registry_key': {'type': 'string'}, 'offset': {'type': 'integer', 'default': 0}, 'limit': {'type': 'integer', 'default': 400}, 'full': {'type': 'boolean', 'default': False}}, 'required': ['registry_key']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
