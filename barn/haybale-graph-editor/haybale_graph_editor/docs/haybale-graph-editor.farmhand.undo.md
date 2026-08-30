# Undo

`haybale-graph-editor:farmhand:undo` · kind: farmhand

Undo the last change on this graph's SHARED human+agent timeline.

## Agent Instructions

Undo the last change on this graph's undo timeline — SHARED between the human editing in the studio UI and any agent calling these tools, so this can undo a change either one made. Returns performed=false with no error when there is nothing to undo. Broadcasts to open studio UIs only when a change was actually undone.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
