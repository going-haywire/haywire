# List graphs

`haybale-haystack:farmhand:list_graphs` · kind: farmhand

Open haystack entries plus .haywire files on disk in the workspace.

## Agent Instructions

List open graph sessions (with their binding_id, needed by every other haystack_*/graph_editor_* tool) plus every .haywire file found on disk under the workspace root, whether open or not. Use this first to discover a binding_id, or to find a file path to pass to haystack_open_graph.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'limit': {'type': 'integer', 'default': 100}, 'offset': {'type': 'integer', 'default': 0}}, 'required': []}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
