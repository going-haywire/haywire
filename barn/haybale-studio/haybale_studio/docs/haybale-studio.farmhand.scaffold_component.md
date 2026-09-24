# Scaffold component

`haybale-studio:farmhand:scaffold_component` · kind: farmhand

Write a canon-conformant skeleton for a new component into a project-local library.

## Agent Instructions

Write a canon-conformant skeleton for any component kind into a project-local library. kind=node clones the builtin Data node template: name= is the class name (snake_case is converted), label= defaults to it; the result reports the registry_key that actually registered and registration ('added' | 'failed' | 'timeout'). Other kinds get a stub to fill in. Read the kind's canon first — find it via the farmhand://docs/_manifest index (e.g. components/nodes/node-canon.md).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'kind': {'type': 'string'}, 'name': {'type': 'string'}, 'library': {'type': 'string', 'default': None}, 'label': {'type': 'string', 'default': None}}, 'required': ['kind', 'name']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
