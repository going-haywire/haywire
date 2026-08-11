# Redo

`graph_editor:farmhand:redo` · kind: farmhand

Redo the last undone change on this graph's SHARED human+agent timeline.

## Agent Instructions

Redo the last undone change on this graph's undo timeline — SHARED between the human editing in the studio UI and any agent calling these tools. Returns performed=false with no error when there is nothing to redo. Broadcasts to open studio UIs only when a change was actually redone.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
