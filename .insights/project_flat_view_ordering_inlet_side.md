# An ordering walk over a FlatGraphView must use inlet-side lookups

**Symptom.** A data node downstream of a data-only Group card ran before the Group's interior and read the previous frame's value: a one-frame lag, no error, no warning. Every single-node test passed.

**Cause.** `FlatGraphView` flattens a Subgraph into its host. To do so it splices the crossings of a data-only Subgraph (Output node to consumer, source to interior sink) into the lookups, and the crossings go only into the *inlet-side* lookups (`_get_edge_wrappers_for_port(..., incoming=True)`, which applies `_reroute_source`); an outgoing lookup returns the owning graph's edges unchanged. So an outlet-side walk misses the Output-to-consumer edge, and `SubgraphOutputNode` has no outlets to walk from. `_backpropagate` asked the inlet side and was right; `DataFlowBuilder._check_cycles` and `_topological_sort` built their dependencies from outlet-side lookups and so ordered the consumer before the Group's interior.

**Rule.** Any walk that orders or checks nodes over a `FlatGraphView` takes its dependencies from the inlet side: for each node, its inlets' incoming edges and their `source_node_id`. Do not rebuild "who depends on me" from outlets. `_get_edge_wrappers_for_port` requires the `incoming` keyword, so every caller names the end (ADR 0048, Q109).

Pinned by the swinglet assembly tests (`tests/core/test_assembly/test_swinglet_assembly.py`) and the Group ordering fix, commit 704ce6ec.
