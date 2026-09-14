# Step 4 — Collapse and expand

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A selection can be collapsed into a Group and expanded back, both
undoable, with a convexity check that refuses the collapses that would make a
Graph-node incoherent.

**Architecture:** Collapse is "compute the crossing edges, dedup them into an
interface, move the selection into a definition". The crossing-edge computation is
the clipboard's **both-endpoints rule**, already implemented. Design record:
[2026-09-14-graph-nodes.md](2026-09-14-graph-nodes.md), decisions 12, 13, 26.

**Tech Stack:** Python 3.12, pytest.

## Global Constraints

- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- Collapse and expand are **inverses**. `collapse → expand` must round-trip to an
  equivalent graph; this is the primary test.
- A mergeable action's `merge()` MUST call `mark_executed()` on what it returns —
  see `.insights/project_undo_merge_executed_state.md`. An unexecuted merged action
  wedges the whole undo stack silently (`can_undo()` still says True).
- Click handlers must **return** the coroutine, never schedule it — see
  `.insights/project_stepper_flows.md` and `.insights/feedback_nicegui_async.md`.

## Pre-Flight Baseline

```sh
uv run ruff check packages/haywire-core/src/haywire/core/undo/ packages/haywire-core/src/haywire/core/graph/
uv run mypy packages/haywire-core/src/haywire/core/undo/ packages/haywire-core/src/haywire/core/graph/
uv run pytest tests/core/test_undo/ -q
```

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` | The two actions. |
| `packages/haywire-core/src/haywire/core/graph/subgraph.py` | Gains the convexity check + interface derivation helpers. |
| `packages/haywire-core/src/haywire/core/graph/clipboard.py` | Copy path excludes boundary nodes. |

---

### Task 1: Convexity check

**Files:** Modify `packages/haywire-core/src/haywire/core/graph/subgraph.py`

A selection is **convex** when no path leaves it and re-enters. `A → B → C` with
`{A, C}` selected is not: collapsing would give the parent `G → B` *and* `B → G`.
Under inlining that runs fine — the cycle check (`data_flow_builder.py:159-212`)
only ever sees the inlined graph — but the Graph-node would be **entered twice**
in one pass, which is incoherent for control flow.

- `check_convex(graph, node_ids) -> tuple[bool, list[str]]` — returns validity and
  the intervening node ids that would have to join the selection.
- This is a **reachability** test, not connectivity. `get_disconnected_components`
  (`core/graph/base.py:624`) is a different question; do not reuse it.

- [ ] `A → B → C`, selecting `{A, C}`, is refused and names `B`.
- [ ] A convex selection with a loop wholly inside it is accepted.

### Task 2: Interface derivation

**Files:** Modify `packages/haywire-core/src/haywire/core/graph/subgraph.py`

Compute the boundary interface from the crossing edges, reusing the
**both-endpoints rule** from `core/graph/clipboard.py:40-60` (an edge is internal
iff both endpoints are selected; everything else crosses).

Dedup per decision 12:

- **Inlets** group by their *outer source* — `(source_node_id, outlet_port_id)`.
  One outer outlet feeding three selected nodes mints **one** inlet that fans out
  inside, preserving the user's wiring exactly.
- **Outlets** group by their *inner source*. One inner outlet feeding four outside
  nodes mints **one** outlet.
- Pin labels come from the **inner** port's label, disambiguated with the inner
  node's label on collision (`value` → `Scale.value`). Naming from the inner side
  is what makes a pin meaningful to someone who did not build it — and it survives
  rewiring, which naming from the outer side does not.

- [ ] One outer outlet → three selected nodes yields exactly one inlet.
- [ ] Label collision produces `Node.port`, not a duplicate.

### Task 3: `CollapseToGraphNodeAction`

**Files:** Modify `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`

A `CompositeAction` that: runs Task 1's check (refusing with the intervening
nodes named), derives the interface via Task 2, creates the `SubgraphDefinition`
and registers it in the host's keyed table, creates the two boundary nodes and
stamps their ports, moves the selected nodes and internal edges into the
definition, creates the `GraphNode`, rewires the crossing edges to its pins, and
positions it at the selection centroid.

- [ ] Undo restores the original graph exactly, edges included.

### Task 4: `ExpandGraphNodeAction`

**Files:** Modify `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py`

The exact inverse: inline the definition's nodes back into the host (ids already
root-unique from step 2, so no remapping), rewire the Graph-node's edges to the
inner ports the boundary nodes pointed at, drop the boundary nodes, the Graph-node
and the definition.

- [ ] `collapse → expand` round-trips to an equivalent graph.
- [ ] `collapse → expand → undo → undo` returns to the original.

### Task 5: Delete and copy filtering

**Files:** Modify the delete path and `packages/haywire-core/src/haywire/core/graph/clipboard.py`

Boundary nodes cannot be deleted or copied (decision 26). Enforce it by filtering
them out of the selection in the delete and copy paths — **not** by adding a
`deletable` flag to `BaseIdentity`, which would have exactly one user and would
have to be honoured by every delete path to mean anything.

Deleting everything inside a Subgraph therefore empties its contents and leaves
the interface standing, which is correct: the boundary nodes are structure, not
content. A Subgraph Input pasted into an ordinary graph would be meaningless, so
copy excludes them too.

- [ ] Selecting every node inside a Subgraph and deleting leaves both boundary
      nodes standing.
- [ ] Copying a selection containing them yields a payload without them.

---

## Verification

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ tests/
uv run pytest tests/core/test_undo/ tests/core/test_graph/ -q
```

New tests under `tests/core/test_undo/test_collapse_expand.py`:

- Round-trip: `collapse → expand` yields an equivalent graph.
- Undo of collapse restores every edge.
- Dedup: one outer outlet feeding three selected nodes → one inlet.
- Convexity: `{A, C}` of `A → B → C` refused, naming `B`.
- Delete/copy filtering (Task 5).
- A collapsed selection containing a `ControlSwitch` keeps **both** exec exits on
  the Graph-node — multi-exit control is ordinary, not a loopback (decision 4).

## Depends on / unblocks

- Depends on: steps 1 and 2. Testable without step 3, but the result is not
  runnable until step 3 lands.
- Unblocks: step 5 wires these to the toolbar.
