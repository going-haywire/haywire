# Step 3 — Inlining: FlatGraphView and the assembly seam

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A graph containing Graph-nodes assembles to exactly the Flows the
equivalent hand-inlined graph would produce. The VM, the scheduler, lazy masks and
callbacks are not touched.

**Architecture:** This is the load-bearing step, and it is smaller than it looks.
The VM never resolves a node through the graph — its only lookup is
`flow.control_graph.get_node_info(current_node_id)` (`execution/vm.py:186`), and
data nodes execute as instances already held in `LocalizedDataFlow.execution_sequence`
(`execution/flow.py:60`). The whole flat-id assumption lives in **two lookups**
used by the assembly builders. Teaching those two to see through a Graph-node is
the entire execution change. Design record:
[2026-09-14-graph-nodes.md](2026-09-14-graph-nodes.md), decisions 5, 15.

**Tech Stack:** Python 3.12, pytest.

## Global Constraints

- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- **Do not modify** `execution/vm.py`, `execution/scheduler.py`, or
  `execution/flow.py`. If a change there seems necessary, the flat view is wrong —
  stop and raise it.
- The view is a **lookup shim over live instances**, not a graph transformer and
  not a copy. The nodes it returns are the same objects the canvas is drawing
  (decision 9), which is what makes error locations and live values work for free.
- Step 2 guarantees ids are unique across host + all instantiations, so the view
  never needs to namespace anything.

## Pre-Flight Baseline

```sh
uv run ruff check packages/haywire-core/src/haywire/core/assembly/
uv run mypy packages/haywire-core/src/haywire/core/assembly/
uv run pytest tests/core/test_execution/ tests/core/test_assembly/ -q
```

## The two lookups

Everything else in assembly travels as ids read off edges.

| Lookup | Call sites |
|---|---|
| `graph.get_node_wrapper(node_id)` | `assembly/control_flow_builder.py:100`; `assembly/data_flow_builder.py:88,132,177,243` |
| `graph._get_edge_wrappers_for_port(node_id, port_id)` | `assembly/data_flow_builder.py:124` |

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/assembly/flat_view.py` | **New.** `FlatGraphView`. |
| `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py` | Wraps the graph at the top of `assemble_graph()`. |

---

### Task 1: `FlatGraphView`

**Files:** Create `packages/haywire-core/src/haywire/core/assembly/flat_view.py`

A facade over the host graph exposing only what the builders use:

- `get_node_wrapper(node_id)` — searches the host's `node_wrappers`, then every
  Graph-node's instantiation, recursively. Returns the **live** wrapper.
- `_get_edge_wrappers_for_port(node_id, port_id)` — **the splice.** An edge landing
  on a Graph-node inlet is answered with the edges leaving the corresponding
  Subgraph Input outlet, and symmetrically for outlets. Neither Graph-nodes nor
  boundary nodes ever appear in a returned edge's endpoints.
- `list_node_wrappers()` — host nodes plus every instantiation, with Graph-nodes
  and boundary nodes excluded.
- `variables`, `graph_id` — pass through to the host. (`vm.py:78` reads
  `flow.graph_ref.variables`; under inlining the host's Variables are the ones
  that apply.)

**Splice rules to get right:**

- **Fan-out.** One outer outlet feeding a Graph-node inlet that fans to three
  inner inlets must resolve to three edges, since inlets are single-connection
  unless a port sets `allow_multiple_links` (`core/types/port.py:545`).
- **Unconnected Graph-node inlet.** Its value lives on the Graph-node's own port
  (decision 11). Push it onto the target inner inlets at inline time.
- **Nesting.** A Graph-node inside a Subgraph splices through both levels.
- **Adapter chains** on a boundary-crossing edge compose: the outer edge's chain
  then the inner edge's. Verify against a real crossing with a type conversion.

- [ ] A graph with one Graph-node produces the same `Flow` shape as the equivalent
      hand-inlined graph — control DAG, per-node localized data flows, topology order.
- [ ] Two levels of nesting resolve.

### Task 2: Wire it into assembly

**Files:** Modify `packages/haywire-core/src/haywire/core/assembly/flow_assembly_manager.py`

- Wrap the graph in a `FlatGraphView` at the top of `assemble_graph()`. Nothing
  downstream changes.
- Replace the stale placeholder comment at line 165
  (`# - Check for Graph-nodes with missing Source/Sink`) — the check now lives in
  step 1's validator, under different names.

- [ ] `tests/core/test_execution/` and `tests/core/test_assembly/` still green with
      no Graph-nodes present (the view must be transparent for ordinary graphs).

### Task 3: Prove the VM is untouched

**Files:** none — this is a guard, not a change.

Confirm by inspection and by test that no change was needed in `vm.py`,
`scheduler.py` or `flow.py`. If one was, the design assumption is broken and this
step should stop for review rather than adapt the VM.

- [ ] `git diff --stat packages/haywire-core/src/haywire/core/execution/` is empty.

---

## Verification

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ tests/
uv run pytest -m "not browser and not perf" -q > /tmp/t.log 2>&1; echo "exit=$?"
```

New tests under `tests/core/test_assembly/test_flat_view.py`:

- **Equivalence:** build graph A with a Graph-node and graph B hand-inlined; assert
  identical control DAGs, identical localized data flows per control node, and
  identical topology order.
- **Transparency:** a graph with no Graph-nodes assembles identically with and
  without the view.
- Fan-out: one outer outlet → Graph-node inlet → three inner inlets resolves to
  three edges.
- An unconnected Graph-node inlet's widget value reaches the inner inlets.
- Two levels of nesting resolve.
- Lazy masks: EVAL_MASK bit assignment over an inlined graph matches the
  hand-inlined equivalent.

## Depends on / unblocks

- Depends on: steps 1 and 2.
- Unblocks: step 4 can be built and tested without it, but a Group is not
  *runnable* until this lands.
