# Collapse to Group

`haybale-graph-editor:panel:CollapseToGroupMenuPanel` · kind: panel

Collapse the selection into one Graph-node standing for a Subgraph.

## Details

- **surface**: `selection`
- **order**: `210`

## Notes

Collapse the selection into one Graph-node standing for a Subgraph.

Offered whenever two or more nodes are selected. A selection is refused when a
path that carries values (data, control or callback) leaves it and comes back
in; visual links don't count. The refusal comes when the command runs, with the
intervening nodes named — a row that quietly disappeared would leave the user
with nothing to read.
