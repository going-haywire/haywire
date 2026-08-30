# Set graph metadata

`haybale-graph-editor:farmhand:set_metadata` · kind: farmhand

Set a graph's document metadata (label, description, author, version).

## Agent Instructions

Set one or more of a graph's document metadata fields — label (free-text title), description (what the graph is for), author, version (the author's own version string, NOT the file format version). Omitted fields are left alone; pass several at once when describing a graph you just built. Read the current values from graph_editor_query_graph's 'metadata' key. Metadata is not undoable and does not mark the graph dirty (matching graph settings), so an edit is only persisted by a later save.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'label': {'type': 'string', 'default': None}, 'description': {'type': 'string', 'default': None}, 'author': {'type': 'string', 'default': None}, 'version': {'type': 'string', 'default': None}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
