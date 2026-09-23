# Group

`haywire-core:node:GraphNode` · kind: node

A Graph-node: one card standing for a whole Subgraph.

## Notes

One card standing for the Subgraph stored under ``subgraph_key``.

Ships port-less and mirrors its pins from the Subgraph's boundary nodes
whenever the interface changes. Binding a Subgraph and reconciling the
interface are the two things to call:

```python
graph_node.bind_subgraph("subgraph_a1b2c3")   # also reconciles
graph_node.reconcile_interface()              # after a boundary port edit
```

The node type follows the interface: a Subgraph with no control crossings
makes this a DATA node, anything else a CONTROL node.
