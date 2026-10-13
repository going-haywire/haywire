# Operate widget

`haybale-graph-editor:farmhand:operate` · kind: farmhand

Change the value of a widget that is shown on a node card. Not undo-recorded.

## Agent Instructions

Change the value of a port whose widget is shown on its node card, the same change a person makes by using that widget. Use the exact port id from a graph_editor_inspect_node row. A port with no widget, a hidden widget, or an inlet fed by an edge raises not_operable. The write is verified by reading the value back: a value the port rejects raises set_rejected. Like a widget edit it is not undo-recorded, and it marks the graph as unsaved only when the value changed.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'node_id': {'type': 'string'}, 'port_id': {'type': 'string'}, 'value': {'anyOf': [{'type': 'string'}, {'type': 'number'}, {'type': 'integer'}, {'type': 'boolean'}, {'type': 'object'}, {'type': 'array'}, {'type': 'null'}], 'default': None}}, 'required': ['binding_id', 'node_id', 'port_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
