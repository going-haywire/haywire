# Step 3 — The assembly seam

**Built.** What the seam is, and where its reasoning lives.

A Group's card and both boundary nodes execute as ordinary nodes in the host's
flow. The boundary nodes copy values across the boundary, each write firing that
port's own pipes so the rest of the journey runs over real edges with their own
adapter chains. Control crosses on strings carried in `outlet_map` and
`ExecutionContext.control_pin`, never on an edge.

Three pieces:

| Piece | What it does |
|---|---|
[`BaseGraph.control_transitions()`](packages/haywire-core/src/haywire/core/graph/base.py) | Returns `{outlet_id: (next_node_id, inlet_id)}` for one node. Its default enumerates the node's real control outlets and follows their edges. `ControlFlowBuilder` asks this instead of reading each port itself, so a view can answer differently. |
[`core/assembly/flat_view.py`](packages/haywire-core/src/haywire/core/assembly/flat_view.py) | `FlatGraphView` — tree-wide `get_node_wrapper`, the virtual control crossings, and three `_get_edge_wrappers_for_port` splices that order a data-only Subgraph's dependencies. Wrapped once at the top of `assemble_graph()`, transparent for a graph with no Subgraph. |
[`core/graph/subgraph_crossing.py`](packages/haywire-core/src/haywire/core/graph/subgraph_crossing.py) | The four id spaces that meet at a boundary, every conversion between them, and `copy_inward` / `copy_outward`. |

The VM, the scheduler, `execution/flow.py` and the pipe layer are untouched.

**Read first:**

- [ADR 0036](docs/adr/0036-groups-execute-through-their-boundary-nodes.md) — why
  the execution model is this and not something simpler.
- `.insights/project_assembly_decides_when_pipes_decide_where.md` — the
  distinction any change here has to respect: assembly decides *when* a node
  runs, pipes decide *where* a value goes.

**Tests:** [`tests/core/test_assembly/test_flat_view.py`](tests/core/test_assembly/test_flat_view.py)
asserts on port values after a frame, not on the assembled shape. A Group that
assembles into the right nodes in the right order can still deliver nothing.
