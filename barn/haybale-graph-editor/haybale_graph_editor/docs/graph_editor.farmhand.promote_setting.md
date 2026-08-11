# Promote setting

`graph_editor:farmhand:promote_setting` · kind: farmhand

Promote a settings field to a data port. Not undo-routed (UI parity; later work).

## Agent Instructions

Promote a settings field to a live data port, so it can be wired instead of just set directly. accessor is the settings-bag accessor (e.g. 'depth') and field the field name within it — both come from a graph_editor_inspect_node settings row. direction is one of inlet/outlet/config (default inlet); an invalid direction raises bad_direction, and a field that can't be promoted raises not_promotable. NOT undo-routed — this does not join the undo timeline (UI parity gap, tracked for later work).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'node_id': {'type': 'string'}, 'accessor': {'type': 'string'}, 'field': {'type': 'string'}, 'direction': {'type': 'string', 'default': 'inlet'}}, 'required': ['binding_id', 'node_id', 'accessor', 'field']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
