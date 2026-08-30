# Create graph

`haybale-haystack:farmhand:create_graph` · kind: farmhand

Create a new untitled graph (appears in open browser sessions).

## Agent Instructions

Create a new untitled, unsaved graph and return its binding_id. The graph appears in any open studio browser session immediately. It has no nodes yet — follow with graph_editor_add_node, then haystack_save_graph (it stays unsaved until you do).

## Details

- **input_schema**: `{'type': 'object', 'properties': {}, 'required': []}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
