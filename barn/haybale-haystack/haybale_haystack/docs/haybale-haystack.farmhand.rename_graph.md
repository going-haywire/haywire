# Rename graph

`haybale-haystack:farmhand:rename_graph` · kind: farmhand

Rename an open graph's file on disk and rekey it.

## Agent Instructions

Rename an open graph: renames its file on disk to new_name and updates its display_name. The binding_id itself does not change. Raises graph_not_found for an unknown binding_id, rename_failed if the rename itself fails (e.g. name collision).

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'new_name': {'type': 'string'}}, 'required': ['binding_id', 'new_name']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
