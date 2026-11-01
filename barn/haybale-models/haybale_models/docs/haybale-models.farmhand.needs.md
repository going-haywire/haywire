# Models a graph needs

`haybale-models:farmhand:needs` · kind: farmhand

The models an open graph references and does not have locally.

## Agent Instructions

Returns the missing models of an open graph, interiors included: label, size (null when unknown) and the node_ids that ask for it. Get binding_id from haystack_list_graphs.

## Details

- **input_schema**: `{'type': 'object', 'properties': {'binding_id': {'type': 'string'}}, 'required': ['binding_id']}`
- **annotations**: `{'read_only_hint': True, 'destructive_hint': False, 'idempotent_hint': False, 'open_world_hint': False}`

## Notes

Lists the models an open graph needs and this machine does not have.

Returns, for the graph under `binding_id`, each missing model with its label, size
(`null` when unknown) and the ids of the nodes that ask for it, interiors of
subgraphs and macros included, plus the known total in bytes. Call it before
starting a graph, or to decide what `models_fetch` should download. Get
`binding_id` from `haystack_list_graphs`.
