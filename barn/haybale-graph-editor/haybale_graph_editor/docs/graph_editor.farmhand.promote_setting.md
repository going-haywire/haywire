# Promote setting

`graph_editor:farmhand:promote_setting` · kind: farmhand

Promote a settings field to a data port. Not undo-routed (UI parity; later work).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'node_id': {'type': 'string'}, 'accessor': {'type': 'string'}, 'field': {'type': 'string'}, 'direction': {'type': 'string', 'default': 'inlet'}}, 'required': ['binding_id', 'node_id', 'accessor', 'field']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
