# Node Arrange (auto-layout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revision 2026-10-29.** Re-settled against the current code; supersedes the 2026-07-22 plan (in git
> history, `d60e4c102`). The July two-tier model (control spine + data clusters), `props.pinned` and
> whole-graph-only scope are dropped — see "What changed since July" at the end.

**Goal:** Auto-layout and flow-selection verbs for the graph editor:

| Where | Verb | Acts on |
| --- | --- | --- |
| Node menu → **Layout** | Arrange Flow | every node connected to the node (any edge, either direction) |
| Node menu → **Layout** | Arrange Downstream | the node + everything reachable along edges from it |
| Node menu → **Layout** | Arrange Upstream | the node + everything that reaches it along edges |
| Node menu → **Select** | Select Downstream | same set as Arrange Downstream — replaces the selection |
| Node menu → **Select** | Select Upstream | same set as Arrange Upstream — replaces the selection |
| Canvas menu (… flyout) | Arrange All | every node in the graph |
| Farmhand | `arrange` tool | any of the four arrange scopes |

Every arrange is one undoable `MoveNodesToAction` (one Ctrl-Z).

**Architecture:** One pure, synchronous, headless-testable core module
`packages/haywire-core/src/haywire/core/graph/arrange.py`:

- `connected_nodes(graph, node_id, scope) -> set[str]` — the node set for a scope (also what Select uses).
- `arrange_layout(graph, scope, node_id=None) -> dict[str, dict[str, float]]` — absolute positions for
  the nodes that move; feed straight to `editor.move_nodes_to(positions, PATCH)`.

It reads `graph.node_wrappers` / `graph.edge_wrappers` (`EdgeWrapper.source_node_id → sink_node_id`),
`node.props.posX/posY/width/height` (auto axes are measured in-browser and written back into
`width`/`height`, so props hold real sizes; a never-rendered headless node reads the 200/200 default),
`node.props.locked`, and the graph's `layout_direction`. No UI, no DI, no mutation.

Adapters: (1) node-menu panels → `SelectionActions` verbs → canvas events → visual layer / selection
handler; (2) canvas-menu panel → `GraphActions` verb → same arrange event; (3) Farmhand tool.

**Tech stack:** Python 3.12, pure stdlib (no networkx/ELK). Algorithm reimplemented from the public
papers (research: `.scratch/node-arrange/research.md`; the surveyed Blender addons are GPL-3.0 — read,
never copy).

---

## Settled decisions (binding)

1. **Flow = weakly connected component.** "Arrange Flow" covers every node reachable from the start
   node over any edge, ignoring direction. Works for data-only nodes; shared nodes need no special case.
2. **Up/downstream follow all edges** (control + data), outlet → inlet; traversal is visited-guarded
   (cycles terminate). Edges are never typed/filtered.
3. **Node verbs need exactly one selected node.** The menu rows poll on a single selected node
   (`_single_node(ctx)` in `selection.py` is the existing predicate) and grey otherwise. The start
   node is unambiguous.
4. **The start node is the anchor.** It never moves; the layout is translated so the start node keeps
   its position. Nodes outside the arranged set are ignored — overlaps with them are the user's to fix.
5. **No pinning.** `props.pinned` no longer exists and is not reintroduced. **`props.locked` is
   honored** ("Protect this node from being moved…"): a locked node takes part in ranking/ordering but
   is omitted from the emitted positions. It is the existing move-protection, not a new gate.
6. **One algorithm for every scope:** plain layered (Sugiyama-lite) layout over the directed graph of
   all edges inside the set — rank, a few barycenter ordering sweeps, coordinate assignment.
   Back-edges of cycles are ignored for ranking.
7. **Direction follows the graph's `layout_direction`.** Compute in abstract (rank axis, cross axis)
   space, then map: L2R rank→+x; R2L rank→−x; T2B rank→+y; B2T rank→−y. Rank-axis extent of a node is
   its width for horizontal directions, height for vertical ones (and vice versa for the cross axis).
   Graph tier only; per-node overrides are not considered.
8. **Patch only.** All arrange/select verbs act in the PATCH channel; the rows grey in a stage canvas
   (`self.channel.stage`). Stage is free-form composition.
9. **Menus:** a new **"Layout"** submenu (Arrange Flow / Downstream / Upstream) and a new **"Select"**
   submenu (Select Downstream / Upstream) on `SelectionMenu`. The existing "Arrange" submenu stays the
   stacking-order verbs, untouched.
10. **Select replaces the selection** with the computed set (start node excluded), excluding locked
    nodes (the canvas keeps locked nodes out of multi-selections — same rule as `select_all_toggle`).
    No active node/edge afterwards.
11. **One graph at a time.** Arrange/select act on the graph shown in the canvas; a Graph-node (Group/
    macro placement) is one card. Interiors are not touched, boundaries are not crossed.
12. **Also:** whole-graph "Arrange All" on the canvas context menu, and a Farmhand `arrange` tool.
    Arrange All has no anchor: it lays out each connected component as its own band (stacked along the
    cross axis) and recenters on the pre-arrange centroid of the moved nodes.

## Explicitly out of scope

- Multi-node start sets (decision 3).
- Edge routing / reroute insertion / bend points — arrange moves nodes, never edges.
- Avoiding nodes outside the arranged set.
- Stage-channel layout.
- Per-node `layout_direction` mixing.
- Network-simplex ranking / Brandes–Köpf coordinates (v2).
- Align/distribute toolset.
- Keyboard shortcuts (can follow via the EditorCommand convention once the verbs exist).
- An `ArrangeSettings` bag — spacing is module constants, structured for a later mechanical lift.

---

## Global constraints

- `arrange.py` stays pure and synchronous: no UI, no DI, no client.
- No new third-party dependency.
- Every `SelectionActions` verb added to the Protocol MUST be implemented by **both** implementors —
  `handlers/context_menu.py` (emits the event) and `handlers/selection_toolbar.py` (delegates to
  `_menu_provider`). A verb missing on either fails the *whole* menu, not just its row
  (`render_surface` isinstance-checks the host against `provides`).
- Hosting panels that poll true over nothing cost the menu its popup (`.insights/project_surface_popup_emptiness_contract.md`):
  the Layout/Select hosts poll on exactly the predicate their leaves poll on, and draw a greyed
  `submenu_row` in `draw_disabled`.
- Test node keys come from `Cls.class_identity.registry_key` and are `isinstance`-checked
  (`.insights/project_unknown_key_yields_error_node.md`). Tests never read repo `graphs/`.
- Quality gates after every task: `uv run ruff check` + `uv run ruff format --check` on touched files,
  mypy (CI invocation), smallest covering pytest tier; full `-m "not browser and not perf" -n 4` and
  `-m browser -n 4` before completion. Baseline ruff/mypy on the touched areas before Task 1.

---

## Tasks

### 1. Core: scopes and reachability

- [ ] `arrange.py`: `class ArrangeScope(Enum)`: `FLOW`, `DOWNSTREAM`, `UPSTREAM`, `ALL`.
- [ ] `connected_nodes(graph, node_id, scope)`: BFS over `edge_wrappers` — DOWNSTREAM follows
      `source→sink`, UPSTREAM `sink→source`, FLOW both; ALL returns every node id. Always contains
      `node_id` (for non-ALL). Unknown `node_id` → empty set.
- [ ] Unit tests (`tests/core/test_graph/test_arrange.py`): linear chain both ways; fan-in/fan-out;
      control + data edges both followed; a cycle terminates; FLOW crosses direction changes; isolated
      node yields `{node_id}`.

### 2. Core: layering

- [ ] Build the induced directed graph over the set (edges with both ends inside; multi-edges collapse).
- [ ] Cycle handling: DFS from the start node (or all sources, for ALL/FLOW) marks back-edges, which are
      dropped for ranking.
- [ ] Ranking: longest-path. DOWNSTREAM: start node at rank 0. UPSTREAM: start node at the max rank.
      FLOW/ALL: sources at rank 0. Normalize to start at 0.
- [ ] Ordering: initial order by BFS discovery, then a fixed number of alternating barycenter sweeps
      (constant `ORDER_SWEEPS`); ties broken by node id → deterministic, no RNG.
- [ ] Unit tests: ranks strictly increase along every non-back edge; start-node rank per scope; two
      calls return identical results; a barycenter case where a crossing is removed.

### 3. Core: coordinates, direction, anchor, locked

- [ ] Abstract coordinates: rank axis cursor advances by `max rank-extent in the rank + RANK_GAP`;
      cross axis stacks by `cross-extent + CROSS_GAP`, each rank centered on the cross axis.
- [ ] ALL: lay out each weakly connected component separately, stack components along the cross axis
      with `BAND_GAP`.
- [ ] Map abstract → canvas per `layout_direction` (decision 7). Positions are top-left (`posX/posY`):
      for R2L/B2T, mirror using each node's own extent so cards don't overlap after negation.
- [ ] Anchor: translate so the start node's computed position equals its current one. ALL: translate
      so the centroid of moved nodes equals their pre-arrange centroid.
- [ ] Drop locked nodes and the start node from the returned dict (both stay put).
- [ ] Constants at module top (`RANK_GAP`, `CROSS_GAP`, `BAND_GAP`, `ORDER_SWEEPS`) with
      `# TODO: promote to ArrangeSettings`.
- [ ] Unit tests: start node absent from output and its neighbours placed relative to it; no two
      arranged cards overlap (rect test with props sizes); each of the four directions puts a
      downstream node on the correct side; locked node absent; ALL: two components don't overlap and
      the centroid is preserved; result is byte-identical across calls.

### 4. Arrange in the canvas

- [ ] `event_definitions.py`: `ArrangeNodesEvent(node_id: Optional[str], scope: str)` (graph_event,
      category "user", mirroring `RestackEvent`).
- [ ] `visual_layer.py`: `@handles_event(ArrangeNodesEvent) process_arrange` — return if
      `self.channel.stage`; `positions = arrange_layout(graph, ArrangeScope(event.scope), event.node_id)`;
      `editor.move_nodes_to(positions, self.channel)`; `ui.notify` "Nothing to arrange" (warning) on
      empty — mirror `process_restack`.
- [ ] `SelectionActions.arrange_from(node_id: str, scope: ArrangeScope)` — context_menu emits the event;
      selection_toolbar delegates.
- [ ] `GraphActions.arrange_graph()` — emits `ArrangeNodesEvent(node_id=None, scope="all")`; find the
      GraphActions implementor(s) and add it to each.
- [ ] Tests: handler-level test that the event yields one undo step and one Ctrl-Z restores all prior
      positions (see existing restack/stage handler tests for the fixture pattern).

### 5. Select in the canvas

- [ ] `SelectConnectedEvent(node_id: str, scope: str)` (DOWNSTREAM/UPSTREAM only).
- [ ] `handlers/selection.py`: handler beside `select_all_toggle` — set =
      `connected_nodes(...) − locked`, write it to the handler and `EditState` exactly as
      `select_all_toggle` does (clear edges, no active node/edge, publish `SelectionMoved`,
      `sync_selections`). Extract the shared tail of `select_all_toggle` into a private helper rather
      than copying it.
- [ ] `SelectionActions.select_from(node_id: str, scope: ArrangeScope)` on both implementors.
- [ ] Tests: selection equals the computed set; locked node excluded; `EditState` mirrors it.

### 6. Menus

- [ ] `surfaces/selection.py`: `SelectionLayoutMenu` and `SelectionSelectMenu` (no `poll`, like
      `SelectionArrangeMenu`; docstring says why).
- [ ] New `panels/graph/menu/selection/layout.py`: host `LayoutSelectionMenuPanel`
      (surface=SelectionMenu, hosts=(SelectionLayoutMenu,), view band, `order` next to Arrange's 420)
      + three leaf panels via a `_ArrangeMenuPanel` base (`scope`, `row_label`, `row_icon`), shaped like
      `_RestackMenuPanel`. Same file: host `SelectSelectionMenuPanel` + two leaves via
      `_SelectMenuPanel`. Poll: exactly one selected node, and not a stage canvas for Layout. Hosts
      draw a greyed `submenu_row` in `draw_disabled` when the selection is non-empty.
- [ ] Access: arrange is an edit (EDIT, like the restack rows); select is view-level. Check how the
      restack rows / other selection-menu rows declare `requires` (ADR 0060) and follow it.
- [ ] Canvas menu: `ArrangeAllMenuPanel` on `GraphMoreActions` (beside `ResetNodeCardsMenuPanel`),
      polls `active_graph` has ≥ 2 nodes, patch canvas only.
- [ ] Icons: add `layout`, `arrange_flow`, `arrange_downstream`, `arrange_upstream`, `select_flow`,
      `select_downstream`, `select_upstream` (Material names) to `hui.icon` with one-line docstrings,
      as the existing entries do.
- [ ] Tests (`tests/ui/graph_canvas/`, follow `test_selection_edit_menu.py`): rows poll true for one
      node, grey for two or none, grey in a stage canvas; clicking a row calls the right verb with the
      right scope; the toolbar ⋯ still renders (both implementors satisfy the Protocol).

### 7. Farmhand tool

- [ ] `GraphEditorArrangeTool` (registry_id `arrange`) in `farmhands/editor_tools.py`, beside
      `GraphEditorMoveNodesTool`: args `binding_id`, `scope` (`flow|downstream|upstream|all`),
      `node_id` (required unless `all`). `_editor` → `ctx.fence(editor)` → `arrange_layout` →
      `move_nodes_to(positions, PATCH)` → `ctx.broadcast(GraphDataMutated())` → summary with the
      moved count. Unknown node → `FarmhandError` with `ids`; nothing to move → summary "0 nodes",
      not an error. `annotations=_MUTATING`; `instructions` notes locked nodes and the start node never
      move, and that headless-only nodes size as 200×200 until rendered.
- [ ] Optional `select`-style query is NOT added: `graph_editor_query_graph` already lists edges.
- [ ] Test in `tests/farmhand/…` mirroring the move_nodes tool test.

### 8. Verification

- [ ] Full gates (see Global constraints). Commit anything under `barn/haybale-testing` before the full
      suite (`.insights/project_docs_test_reverts_barn_testing.md`).
- [ ] Live check in the running studio: mixed control/data graph with a cycle, a locked node, a
      Group card; each of the five node verbs + Arrange All; one Ctrl-Z per arrange; T2B graph arranges
      top-down; rows greyed in the stage view and with two nodes selected; Farmhand `arrange` via MCP.

### 9. Docs + glossary — after landing only

- [ ] Graph-editor docs page for the Layout/Select submenus and Arrange All (follow
      `docs/reference/doc-authoring.md`); regenerate library docs (`uv run haywire docs
      barn/haybale-graph-editor`).
- [ ] Glossary (after merge): **Arrange** collision — the stacking-order submenu already uses the word;
      add **Layout (verbs)** / **Arrange Flow/Downstream/Upstream** and **Flow (arrange sense)** =
      weakly connected component, cross-referencing Control Flow / execution group so the three senses
      of "flow" stay distinct.

---

## What changed since July

- `props.pinned` is gone → replaced by the anchor (start node) + existing `props.locked`.
- "Arrange" now names the stacking-order submenu → new verbs live under "Layout".
- `LayoutDirection` (framework < graph < node) exists → layout follows the graph tier.
- `LayoutChannel` PATCH/STAGE → patch only.
- Node sizes: `width`/`height` + `size_adapt` (auto axes written back from the render) → props still a
  valid size source.
- Multiple same-type event nodes and execution groups (ADR 0064) made "flow = event spine" ambiguous →
  flow = weakly connected component, single algorithm for all scopes.
- `move_nodes_to(positions, channel)` gained `channel`.
- Groups/Subgraphs/reroutes exist → per-graph only, Graph-node = one card, reroute = ordinary node.
