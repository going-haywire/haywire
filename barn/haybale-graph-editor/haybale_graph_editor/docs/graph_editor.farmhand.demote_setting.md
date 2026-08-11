# Demote setting

`graph_editor:farmhand:demote_setting` · kind: farmhand

Remove a promoted port, returning the field to a plain setting.

## Agent Instructions

Reverse graph_editor_promote_setting: remove a promoted port by its port_id, returning the underlying field to a plain (non-port) setting. Any edges on that port are removed along with it. Broadcasts to open studio UIs on success.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'node_id': {'type': 'string'}, 'port_id': {'type': 'string'}}, 'required': ['binding_id', 'node_id', 'port_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
