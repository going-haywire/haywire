# Arrange

`haybale-graph-editor:farmhand:arrange` · kind: farmhand

Auto-layout the flow of nodes, a node's downstream or upstream nodes, or the whole graph.

## Agent Instructions

Lay out nodes in layers along the graph's layout direction, as one undo step. scope='flow' (every node connected to node_id by any edge), 'downstream' or 'upstream' (nodes reached along edges from / into node_id) keeps node_id where it is and places the rest around it. scope='flow' also takes node_ids=[...] instead: every flow those nodes touch, one band per unconnected part, centred where the nodes were. scope='all' lays out the whole graph the same way (no node needed). Locked nodes never move. Nodes outside the scope are not avoided. Sizes are the cards' last rendered sizes; a node never shown in a studio counts as 200x200. Gap sizes come from the user's Arrange settings.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'scope': {'type': 'string', 'default': 'all'}, 'node_id': {'type': 'string', 'default': None}, 'node_ids': {'type': 'array', 'items': {'type': 'string'}, 'default': None}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
