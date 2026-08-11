# Move nodes

`graph_editor:farmhand:move_nodes` · kind: farmhand

Move nodes to absolute positions ({node_id: {x, y}}).

## Agent Instructions

Move one or more nodes to absolute canvas positions in a single call: positions={node_id: {x, y}, ...}. Positions are absolute, not deltas — read current positions with graph_editor_query_graph first if you need a relative move. Opens one undo fence and broadcasts to open studio UIs on success.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'positions': {'type': 'object'}}, 'required': ['binding_id', 'positions']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
