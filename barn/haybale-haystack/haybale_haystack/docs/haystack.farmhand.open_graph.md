# Open graph

`haystack:farmhand:open_graph` · kind: farmhand

Open a .haywire file (idempotent per path).

## Agent Instructions

Open a .haywire file by path, relative to the workspace root, and return its binding_id. Idempotent: opening an already-open path returns the same session rather than duplicating it. Raises file_not_found if the path doesn't exist — run haystack_list_graphs to see valid paths.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
