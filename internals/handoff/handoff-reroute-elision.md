# Handoff: Reroute Node Elision at Assembly Time

**Date:** 2026-06-21  
**Repo:** `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`  
**Branch:** `master` (work was squash-merged as `f09c3ead`)

---

## Context

Reroute nodes are visual pass-through nodes inserted by the "Split Edge" action to bend/organise wires. They have a single inlet and outlet of the same `FlowType` (DATA, CONTROL, or CALLBACK) and their worker simply forwards the inlet value to the outlet and returns the outlet id.

Each node execution has ~1µs overhead. A graph with many bent wires could accumulate dozens of reroute nodes, adding measurable latency to every flow execution.

**The goal:** at assembly time, elide reroute nodes — collapse chains of `upstream → reroute → downstream` into a direct connection `upstream → downstream` — so they incur zero runtime cost.

---

## What Was Just Completed

The previous session extended reroute nodes from DATA-only to all three edge types (DATA, CONTROL, CALLBACK). This is the prerequisite for elision — it would be wrong to elide a node that the execution engine treats differently from the edges around it.

Key commit: `f09c3ead` — see `git show f09c3ead` for the full diff.

Relevant changes:
- `NodeType.REROUTE` is now a **standalone bit** (no DATA bit) — `packages/haywire-core/src/haywire/core/node/behavior.py`
- `_validate_reroute_node` accepts any same-FlowType passthrough pair — `packages/haywire-core/src/haywire/core/validation/structural_validator.py`
- Worker returns `REROUTE_OUTLET_ID` unconditionally — `barn/haybale-graph-editor/haybale_graph_editor/nodes/reroute.py`
- Menu poll shows "Insert Reroute" for all edge types — `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py`

---

## Where Elision Should Happen

The assembly pipeline lives in:
```
packages/haywire-core/src/haywire/core/assembly/
  flow_assembly_manager.py   ← entry point; calls ControlFlowBuilder + DataFlowBuilder
  control_flow_builder.py    ← builds ControlFlowGraph (CONTROL/EVENT nodes + outlet_map)
  data_flow_builder.py       ← builds LocalizedDataFlow for each control node (BFS backprop)
```

Reroutes currently pass through both builders invisibly — no special handling exists. Elision needs to happen in each builder's traversal, separately per FlowType:

### DATA reroutes
Elided in `DataFlowBuilder._backpropagate`. When backpropagating from a DATA inlet and the source of an edge is a REROUTE node, skip it and continue to the reroute's own inlet instead. The reroute node is then simply absent from `LocalizedDataFlow.execution_sequence`.

### CONTROL reroutes
Elided in `ControlFlowBuilder.build`. When following EXEC outlets and the next node is a REROUTE, skip it and connect directly to the reroute's own EXEC outlet's target. The reroute node is then absent from `ControlFlowGraph.control_nodes`.

### CALLBACK reroutes
Elided in `FlowAssemblyManager._process_callback_edges` (or wherever callback edge topology is walked). When a CALLBACK edge's source is a REROUTE, walk back to the upstream EVENT node before registering.

---

## Key Types and Properties

```python
# Check for reroute
from haywire.core.node.behavior import NodeType
NodeType.REROUTE in node.behavior.node_type  # True for reroute nodes

# Port ids (fixed constants)
from haybale_graph_editor.nodes.reroute import REROUTE_INLET_ID, REROUTE_OUTLET_ID
# REROUTE_INLET_ID  = "in"
# REROUTE_OUTLET_ID = "out"
```

The reroute node's inlet and outlet always have these fixed ids. A reroute in latent (port-less) state has `len(node.ports) == 0` and should be treated as a no-op (it cannot appear in a compiled flow anyway — no edges connect to it yet).

---

## Constraints and Traps

1. **Hot-reload:** Assembled flows are cached in `FlowAssemblyManager.assembled_flows`. Elision must be transparent — if a reroute node is later deleted or its edges change, the flow must reassemble. The existing dirty-flow mechanism handles this already, as long as elision only happens inside the builders (not as a graph mutation).

2. **Do NOT mutate the graph.** Elision should be a compile-time view, not a structural change to `graph.node_wrappers` or `graph.edge_wrappers`. Mutating the graph would break undo, serialisation, and the visual canvas.

3. **Chains of reroutes** — e.g. `A → rr1 → rr2 → B` — must be fully collapsed to `A → B`. The traversal should loop/recurse until it finds a non-reroute node.

4. **REROUTE is standalone**: `is_data_node` is now `False` for reroutes. The data_flow_builder may have guards like `if NodeType.DATA in node_type` that would silently skip reroute nodes — verify whether this already produces correct elision accidentally or whether reroutes are currently included incorrectly.

5. **Tests:** The integration tests in `tests/core/test_undo/test_split_edge_reroute.py` test split/undo but not execution. New tests should verify that a flow containing reroute nodes produces identical outputs to the same flow without reroutes, and that the reroute node's worker is *not called* after elision.

---

## Suggested Reading Order

1. `docs/architecture/execution/` — execution pipeline overview
2. `packages/haywire-core/src/haywire/core/assembly/control_flow_builder.py` — full file
3. `packages/haywire-core/src/haywire/core/assembly/data_flow_builder.py` — full file
4. `packages/haywire-core/src/haywire/core/execution/flow.py` — how `LocalizedDataFlow.execution_sequence` is consumed at runtime
5. `barn/haybale-graph-editor/haybale_graph_editor/nodes/reroute.py` — current worker (to be made unreachable after elision)

---

## Suggested Skills

- **`superpowers:codemap-navigator`** — run before diving into assembly code to get a structural map of the execution pipeline
- **`superpowers:design`** — use before touching the builders; the elision approach (compile-time skip vs. graph rewrite) is an architectural decision
- **`superpowers:writing-plans`** — once the approach is settled, write a plan before editing; the builders have subtle BFS/DFS traversal logic
- **`superpowers:verify`** — run after implementation to confirm no regressions and that reroute workers are truly not called in execution
