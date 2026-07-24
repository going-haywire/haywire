# Node Arrange (auto-layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Depends on:** the **Node Sizing** Check the current implementation of 
> Node sizing and verify that it fits the proposed approach.

**Goal:** A "Node Arrange" action that auto-lays-out a graph into a readable left-to-right flow — control spine as columns, the data nodes feeding each control node clustered as satellites upstream of it — respecting pinned nodes, as a single undoable operation. Reachable both from the UI and from the Farmhand MCP tool.

**Architecture:** A pure, synchronous, headless-testable function `arrange_layout(graph) -> dict[str, dict[str, float]]` in `packages/haywire-core/src/haywire/core/graph/arrange.py` (single module for v1; a per-phase subpackage split is a v2 concern). It consumes `graph.node_wrappers` / `graph.edge_wrappers`, reads per-node `props.width/height` (from the Node Sizing plan) and `props.pinned`, and returns absolute positions for every **non-pinned** node. It performs no mutation and touches no UI/DI. Two thin adapters call it and feed the result to the existing undoable sink `editor.move_nodes_to(positions)` (one `MoveNodesToAction`, one undo step): a UI action in the graph editor, and a new Farmhand tool `GraphEditorArrangeTool` (sibling of `move_nodes`/`add_node` in `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`).

**Layout model — two-tier, engine-mirrored.** Haywire's assembly already establishes the target shape: `ControlFlowBuilder.build` BFS-traverses CONTROL edges from an EVENT node and derives a `topology_order` (`packages/haywire-core/src/haywire/core/assembly/control_flow_builder.py`), and `DataFlowBuilder._backpropagate` walks DATA edges backward from each control node's inlets, stopping at control nodes (`.../assembly/data_flow_builder.py:139`). Arrange **mirrors** these two traversals (it re-implements them against `node_wrappers`/`edge_wrappers` rather than *calling* `FlowAssemblyManager`, because arrange must work on graphs that are not validly assembled — a tangled/partial graph is exactly when you reach for it). Ranks follow the **control spine**; each control node's backpropagated **data cluster** is placed as satellites immediately upstream in its column band. Layer index → posX (left→right = flow direction); order within a layer → posY. Column X cursor advances by `max_width_in_column + margin`; within a band, stack by `node.height + margin`.

**Dual-flow.** The directed graph used for ranking is built from control edges as the spine; data edges attach clusters. Nodes with no path to any control node (pure data islands, or a graph with no EVENT node at all) fall back to **data-only ranking** (rank on DATA edges alone, sinks right). `FlowType.CALLBACK`/`NONE` do not drive layering.

**Roots.** Multiple EVENT nodes → each starts its own control spine, laid out as **stacked horizontal bands** (one readable strip per flow). No EVENT node → the data-only fallback for the whole graph.

**Pinned.** `props.pinned` (already documented "Prevent auto-layout from moving this node") is honored by **compute-but-exclude**: pinned nodes participate in ranking so their neighbors place sensibly, but their ids are omitted from the positions dict handed to `move_nodes_to` — they never move. Overlap a pinned node causes is the user's to resolve (unpin or move it). Hard-constraint pinning (lay out around fixed anchors) is a v2 concern.

**Recenter.** After computing the layout, translate it so it aligns to the pinned nodes if any exist, else to the pre-arrange centroid of the moved nodes — so the graph tidies without leaping out of the viewport. Seed any randomness (`random.seed(0)`) so repeated arranges are deterministic.

**Tech Stack:** Python 3.12, uv workspace monorepo, pytest (`unit`, `integration`), ruff (line-length 109), mypy. Pure stdlib for the algorithm — **no** graph-layout dependency (no networkx, no ELK/Java); the bounded problem needs only plain Python over the graph's own dicts.

**Source docs:** Inquisition session 2026-07-22 (this plan is the record). Research (prior-art survey + licence analysis): `.scratch/node-arrange/research.md` — note all three surveyed Blender addons are **GPL-3.0**; the algorithm is reimplemented from the public papers, no code lifted. Assembly internals: `docs/architecture/execution/*`; the `move_nodes_to` seam: `packages/haywire-core/src/haywire/core/graph/editor.py:133`.

---

## Settled decisions (binding)

1. **Scope:** whole-graph arrange (not selection-scoped). One action lays out all non-pinned nodes.
2. **Surfaces:** both a UI action and a Farmhand tool, over one pure core function.
3. **Location:** single module `graph/arrange.py`; entry `arrange_layout(graph) -> dict[str, dict[str, float]]`.
4. **Layout:** two-tier — control spine (mirrors `ControlFlowBuilder`) + backpropagated data clusters (mirrors `DataFlowBuilder`). Re-implemented, not calling `FlowAssemblyManager` (must work on invalid graphs).
5. **Dual-flow:** control edges = spine; data edges = clusters; unranked-by-control nodes fall back to data-only ranking; CALLBACK/NONE ignored.
6. **Roots:** multi-EVENT → stacked bands; no-EVENT → data-only.
7. **Pinned:** compute-but-exclude (participate in ranking, omitted from the emitted positions).
8. **Undo/center:** single `MoveNodesToAction` (one undo); recenter on pinned-if-any else centroid; seeded RNG.
9. **v1 ranking/coords:** longest-path (or simplest topo) ranking + one/few barycenter ordering sweeps + per-column X cursor + within-column Y stacking. (Network-simplex + Brandes–Köpf are the v2 upgrade.)

## Explicitly out of scope (v1 non-goals)

- Selection-scoped arrange (whole-graph only).
- `pinned` as a hard positional constraint (compute-but-exclude only).
- **Edge routing / reroute-node insertion / bend-point optimization — arrange moves nodes, never edges.**
- Frame / cluster / group nesting layout (node-arrange's clustering is not ported).
- Network-simplex ranking or Brandes–Köpf coordinates (v2 upgrade).
- **Align / distribute manual toolset (the `align_nodes` idiom) — a separate possible feature, NOT arrange.**

---

## Global Constraints

- Test imports: `import haywire.core.graph.editor  # noqa: F401` first in every new test file (circular-import guard, CLAUDE.md).
- `arrange_layout` MUST stay pure and synchronous (no UI, no DI, no client) so it is unit-testable headless. All I/O (measured sizes) is already resolved by the Node Sizing plan into `props`.
- No new third-party dependency. If you reach for networkx/ELK, stop — re-read the Tech Stack line and the research doc's §5.
- Reimplement the algorithm from the public papers; do not copy from the GPL-3.0 reference addons (research §4).
- Quality gates after every task (ruff check + `ruff format --check`, mypy CI invocation, `pytest -m "not browser and not perf"` fast loop; full `pytest` before completion).

---

## Tasks

### 1. Graph → directed-layering structures (pure, tested in isolation)

- [ ] In `graph/arrange.py`, build the intermediate structures from `graph.node_wrappers`/`graph.edge_wrappers`: the set of EVENT roots; per-root control spine via BFS over CONTROL edges (mirror `ControlFlowBuilder.build`); per-control-node data cluster via backward BFS over DATA edges stopping at control nodes (mirror `DataFlowBuilder._backpropagate`); the set of nodes reachable by neither (data islands).
- [ ] Cycle handling: the traversals must be visited-guarded (control flow may legitimately loop — Haywire is not DAG-guaranteed like Blender trees). A back-edge is skipped for ranking, not fatal.
- [ ] Unit tests (no UI, headless): a single-EVENT linear control chain; a control node with a 3-node data cluster; a pure-data island; a control cycle (must terminate); a graph with no EVENT node.

### 2. Ranking + ordering

- [ ] Rank the control spine (longest-path / topological order along CONTROL edges). Attach each data cluster upstream of its control node (cluster nodes rank just before their consumer). Data islands: data-only ranking (sinks right).
- [ ] One (or a few) barycenter ordering sweeps within layers to reduce crossings (the single biggest quality win over naive BFS layering — do include it).
- [ ] Seed RNG (`random.seed(0)`) for determinism.
- [ ] Unit tests: ranks are monotonic along control flow; a data node ranks upstream of the control node it feeds; repeated calls are byte-identical.

### 3. Coordinate assignment + roots/banding + pinned + recenter

- [ ] Assign posX per layer (column X cursor = `x += max_width_in_column + margin_x`, reading `props.width`). Assign posY within a layer by stacking (`y += node.height + margin_y`, reading `props.height`).
- [ ] Multiple EVENT roots → stacked horizontal bands (offset each spine's band vertically). No EVENT → whole-graph data-only layout.
- [ ] Pinned: include pinned nodes in ranking/ordering, but OMIT them from the returned positions dict.
- [ ] Recenter: translate the computed layout to align with pinned nodes if present, else the pre-arrange centroid of the (moved) nodes. Read current positions via `props.get_position()`.
- [ ] Spacing constants: cluster at the top of the module as named constants (`COLUMN_MARGIN`, `ROW_MARGIN`, `CLUSTER_OFFSET`, …) with a `# TODO: promote to ArrangeSettings` note — hardcoded for v1, structured so a future settings bag is a mechanical lift.
- [ ] Unit tests: pinned node absent from output but its neighbors placed around it; two-EVENT graph produces two non-overlapping vertical bands; output centroid ≈ input centroid when no pins.

### 4. UI action

- [ ] Add a graph-editor action (menu entry / command; wire a keyboard shortcut if the editor has a binding convention) that calls `arrange_layout(graph)` then `editor.move_nodes_to(positions)`. Confirm it lands as one undoable `MoveNodesToAction` (one Ctrl-Z reverts the whole arrange).
- [ ] Test (browser harness, `@pytest.mark.browser`): trigger arrange on a small graph; assert nodes moved to computed positions and a single undo restores all prior positions.

### 5. Farmhand tool

- [ ] Add `GraphEditorArrangeTool` (registry_id e.g. `arrange`) in `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`, mirroring `GraphEditorMoveNodesTool`: resolve the editor via `_editor(ctx, binding_id)`, `ctx.fence(editor)`, compute + `move_nodes_to`, `ctx.broadcast(GraphDataMutated())`, return a summary. Headless-safe (no client needed — arrange is pure and sizes are already in `props`).
- [ ] Test (`tests/farmhand/…`): the tool arranges an open graph and reports the node count moved.

### 6. Full verification

- [ ] `uv run pytest` (full, incl. browser + the farmhand tests) green.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` (CI invocation) — no new findings.
- [ ] Manual smoke: build a tangled multi-EVENT graph with a few pinned nodes in the running app, run arrange from the UI and via the Farmhand tool, confirm readable bands, pinned nodes unmoved, one-undo revert.

### 7. Glossary update — DO LAST, only after the above has landed

> Do not touch `glossary.md` until tasks 1–6 are complete and merged. Then add, following `GLOSSARY_FORMAT.md`:
- [ ] **Node Arrange** — the whole-graph auto-layout action; two-tier (control spine + data clusters), respects pinned, one undo step.
- [ ] **Arrange band** — one EVENT flow's horizontal strip in a multi-EVENT arrange.
- [ ] **data cluster / satellites** — the data nodes backpropagated from a control node's inlets, placed upstream of it by arrange.
- [ ] Reconcile with existing **Control Flow** / **LocalizedDataFlow** entries (arrange mirrors those traversals; cross-reference rather than redefine).
