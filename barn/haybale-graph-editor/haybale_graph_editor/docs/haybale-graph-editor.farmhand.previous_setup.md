# Previous setup

`haybale-graph-editor:farmhand:previous_setup` · kind: farmhand

Apply or dismiss the previous setup nodes kept through a hot reload. One undo step.

## Agent Instructions

A hot reload rebuilds every node of the reloaded class from its new code; a node whose setup that changed keeps its previous setup and lists a 'previous_setup' warning in graph_editor_inspect_node (and a WARNING in studio_get_errors). action='apply' rebuilds the nodes from their previous setup, keeping where they are; action='dismiss' drops it. Every node in node_ids must hold one, or nothing changes and no_previous_setup is raised; an unknown action raises bad_action. One undo step on the shared undo timeline.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}, 'node_ids': {'type': 'array', 'items': {'type': 'string'}}, 'action': {'type': 'string'}}, 'required': ['binding_id', 'node_ids', 'action']}`
- **annotations**: `{'read_only_hint': False, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`
