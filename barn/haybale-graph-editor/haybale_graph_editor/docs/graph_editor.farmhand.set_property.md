# Set property

`graph_editor:farmhand:set_property` · kind: farmhand

Set a node property (port value or settings field) by name. Undo-recorded. 'name' resolves to a port id first, then a settings field — use the exact 'name' from a graph_editor_inspect_node row. The write is verified by reading the value back: a value rejected by the field's validator raises set_rejected rather than reporting a success that did not happen. Note min/max are UI hints only and are NOT enforced — an out-of-range write succeeds, so respect the bounds inspect_node reports.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'node_id': {'type': 'string'}, 'name': {'type': 'string'}, 'value': {'default': None}}, 'required': ['binding_id', 'node_id', 'name']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
