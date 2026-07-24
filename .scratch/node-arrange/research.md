# Node auto-arrange: prior-art survey + Haywire fit evaluation

> Sources are primary (GitHub source + algorithm papers). Date: 2026-07-21.
> Every non-obvious claim below cites a source file (path or raw URL) or a paper DOI.

## TL;DR recommendation

Implement a **pure-Python Sugiyama-style layered layout** (rank → order/crossing-reduction →
coordinate assignment), driven by the graph's **directed flow edges**, and feed the result into
`editor.move_nodes_to(...)` as a single undoable action. Do **not** vendor any of the three Blender
addons wholesale — all three are **GPL-3.0**, so their *code* cannot be copied into a permissively
licensed Haywire; the *algorithm* (Sugiyama framework + Brandes–Köpf coordinate assignment) is public
and must be reimplemented from the papers. `node-arrange` is the reference to *read for correctness*,
not to copy. See §4 (licence) and §5 (recommendation).

---

## 1. The three solutions (from their actual source)

### 1a. Leonardo-Pike-Excell/node-arrange — full Sugiyama pipeline

- **Repo meta**: Python; **GPL-3.0**; 23★, 4 forks; created 2024-08-04, last push **2026-07-01**
  (actively maintained); ~1.8 MB (dominated by a bundled networkx wheel).
  Source: `gh api repos/Leonardo-Pike-Excell/node-arrange`.
- **Dependency**: bundles **networkx 3.4.2** as a wheel — declared in
  [`source/blender_manifest.toml`](https://raw.githubusercontent.com/Leonardo-Pike-Excell/node-arrange/main/source/blender_manifest.toml)
  (`wheels = ["./wheels/networkx-3.4.2-py3-none-any.whl"]`). The whole algorithm is built on
  `networkx.MultiDiGraph` / `DiGraph` and its tree/topological utilities.
- **Algorithm class**: textbook **Sugiyama layered graph drawing**, with a *cluster/nesting* extension
  for Blender node **frames**. The top-level pipeline is explicit in
  [`source/arrange/sugiyama.py`](https://raw.githubusercontent.com/Leonardo-Pike-Excell/node-arrange/main/source/arrange/sugiyama.py)
  `sugiyama_layout()` (lines ~234-281): `compute_ranks → merge_edges → insert_dummy_nodes →
  add_columns → minimize_crossings → bk_assign_y_coords → assign_x_coords → route_edges → realize_layout`.
- **Step 1 — column/rank assignment** (`source/arrange/ranking.py`): the network-simplex ranking of
  Gansner–Koutsofios–North–Vo. The file header cites `http://dx.doi.org/10.1109/32.221135` (Gansner et
  al., *A Technique for Drawing Directed Graphs*, IEEE TSE 1993). It builds a **feasible tight tree**
  (`feasible_tree`), computes **cut values** (`compute_cut_values`), and iterates
  `leave_edge`/`enter_edge`/`exchange` until no negative-cut-value tree edge remains — this *is* the
  network-simplex rank optimiser. `normalize_and_balance` then compacts ranks and balances nodes with
  equal in/out degree. Nesting-graph construction cites CorpusID:14932050 (Sander, clustered layered
  layout).
- **Step 2 — ordering / crossing reduction** (`source/arrange/ordering.py`): iterated **barycenter/median
  sweeps** with crossing counting via a **binary-indexed (Fenwick) tree** (`get_cross_count`, lines
  ~891-936 — the Barth–Jünger–Mutzel O(E log|V|) crossing-count method). Constraints from clusters are
  resolved by `handle_constraints`. File header cites five graph-drawing papers, incl.
  `https://doi.org/10.7155/jgaa.00088`. Iteration count is user-tunable (`iterations`, default 25) and
  the search is randomised (`random.seed(0)` for determinism per run).
- **Step 3a — Y coordinates** (`source/arrange/y_coords.py`, `bk_assign_y_coords`): the
  **Brandes–Köpf** horizontal-coordinate-assignment algorithm (used here for the cross-layer axis).
  Header cites the canonical paper `http://dx.doi.org/10.1007/3-540-45848-4_3` *and* its 2020 erratum
  `https://arxiv.org/abs/2008.01252`. It runs the 4 alignments (`RIGHT_DOWN/RIGHT_UP/LEFT_DOWN/LEFT_UP`
  via `_DIRECTION_TO_IDX`), does conflict marking (`marked_conflicts`), block alignment
  (`horizontal_alignment` + `place_block`), `vertical_compaction`, and a `balance()` that averages the
  four candidate layouts.
- **Step 3b — X coordinates** (`source/arrange/x_coords.py`, `assign_x_coords`): simple per-column
  cursor — `x += max_width_in_col + spacing`, with adaptive spacing that widens columns when many edges
  span large vertical distances (cites `https://doi.org/10.7155/jgaa.00220`). `route_edges` inserts bend
  points / reroute dummies.
- **Cycles**: relies on `networkx.topological_generations` / `topological_sort` (ranking.py,
  ordering.py). Assumes a **DAG**; it does not implement an explicit cycle-removal (greedy-FAS) pass, so
  a truly cyclic selection would raise inside networkx. (Blender shader/geometry node trees are acyclic
  by construction, so the addon can assume this; a general tool cannot — see §3.)
- **Pinned / locked nodes**: **none**. It always re-lays-out the entire current selection; there is no
  per-node "don't move me" flag. Direction/anchor is only global (`origin`: CENTER / ACTIVE_OUTPUT /
  ACTIVE_NODE — see `NA_OT_RecenterSelected` in
  [`source/operators.py`](https://raw.githubusercontent.com/Leonardo-Pike-Excell/node-arrange/main/source/operators.py)).
- **Extras**: reroute insertion, collapsed-node stacking, frame (cluster) nesting, socket alignment
  modes (`NONE/MODERATE/FULL`) — all in
  [`source/properties.py`](https://raw.githubusercontent.com/Leonardo-Pike-Excell/node-arrange/main/source/properties.py).
- **Maturity signal**: cleanly modularised (`ranking/ordering/x_coords/y_coords/stacking/realize`),
  fully type-hinted, paper-cited. This is a serious, research-grade implementation — the best of the
  three by a wide margin.

### 1b. 3DSinghVFX/align_nodes — align/distribute/snap heuristics (no layout)

- **Repo meta**: Python; **GPL-3.0**; 56★, 5 forks; created 2020-08-18, last push **2022-09-27**
  (dormant ~4 yrs); ~79 KB. Source: `gh api repos/3DSinghVFX/align_nodes`.
- **Dependencies**: none beyond `bpy`/`mathutils`.
- **Algorithm class**: **not a graph-layout algorithm at all** — it is a set of *manual alignment,
  snap, and stack operators* keyed off the active node, exposed via a pie menu.
- **Operations exposed**
  ([`align_op.py`](https://raw.githubusercontent.com/3DSinghVFX/align_nodes/master/align_op.py),
  [`snap_op.py`](https://raw.githubusercontent.com/3DSinghVFX/align_nodes/master/snap_op.py)):
  - `AlignDependentNodes` / `AlignDependenciesNodes`: walk the link graph outward/inward from the active
    node (`getNodesWhenFollowingBranchedLinks`, a BFS over inputs or outputs with recursion at
    branches) and lay each successor a fixed `offset + width` to the right/left of the previous — a
    naive **chain placement**, no crossing reduction, no column packing.
  - `StakeUp/StakeDownSelectionNodes`: distribute selected nodes vertically by cumulative
    `dimensions.y + offset`.
  - `AlignTop/Right/LeftSide…`, and `snap_op.py`'s `SnapTop/Bottom/Left/Right/HeightCenter/WidthCenter`:
    pure per-axis snapping to the active node's edge/center. These are the classic
    "align-left / align-top / distribute" operations of a drawing tool.
- **Cycles**: irrelevant — no ranking. The branch-follow BFS uses a `nodesToCheck` set and a `nodes`
  visited list, so it won't loop forever, but it also does no real layout.
- **Pinned nodes**: no concept; everything is relative to the *active* node, which acts as an anchor.
- **Maturity**: small, dormant, "still in development" per its own `bl_info`
  ([`__init__.py`](https://raw.githubusercontent.com/3DSinghVFX/align_nodes/master/__init__.py)).

### 1c. KenzKD/Blender-Node-Layout-Organizer — BFS-level layout (JuhaW fork)

- **Repo meta**: Python; **GPL-3.0**; 4★, 0 forks; created 2022-01-24, last push **2022-07-05**
  (dormant); ~57 KB. Source: `gh api repos/KenzKD/Blender-Node-Layout-Organizer`.
- **Structure**: `Node Layout Organizer.py` is just a `bl_info` stub. The real code is
  [`Reference.py`](https://raw.githubusercontent.com/KenzKD/Blender-Node-Layout-Organizer/main/Reference.py),
  which **credits `"Original Code Author JuhaW"`** — i.e. it is a fork/copy of the well-known
  *JuhaW/NodeArrange* addon.
- **Dependencies**: none beyond `bpy` (+ stdlib `collections`, `itertools`).
- **Algorithm class**: **simple BFS layering from the output node** — a stripped-down "poor man's
  Sugiyama" with steps 1 (rank) + 3 (naive coords) but **no crossing reduction**.
  - `outputnode_search`: finds sink node(s) (no outputs but linked inputs).
  - `nodes_iterate`: BFS backward over linked inputs building levels `a[level]`, then de-duplicates so
    each node keeps only its **deepest** level (`for row1 … remove col2`) — this is longest-path ranking
    by hand.
  - `nodes_arrange`: assigns X per level (`x_last - (widthmax + margin_x)`) and stacks nodes in a level
    vertically by cumulative height (`y - margin_y - dimensions.y`). **Order within a level is arbitrary
    (BFS discovery order); there is no barycenter/median crossing-minimisation step.**
  - `nodes_center`: bounding-box recenter.
  - Also ships an `NA_OT_AlignNodes` operator (an "align to selected / tidy loose nodes" heuristic
    copied from Node Wrangler: pick horizontal-vs-vertical by which range is larger, then distribute).
- **Cycles**: the BFS has no visited-guard on re-entry; a cyclic tree would misbehave. Blender node
  trees are acyclic, so this is unhandled-but-fine there.
- **Pinned nodes**: none.
- **Maturity**: single-file, dormant, derivative. Useful only as an illustration of the *cheapest*
  viable layered layout.

---

## 2. Summary comparison

| | node-arrange | align_nodes | KenzKD / JuhaW |
|---|---|---|---|
| Language | Python | Python | Python |
| Deps | **networkx** (bundled wheel) | none (bpy only) | none (bpy only) |
| Algorithm class | **Full Sugiyama** (network-simplex rank + barycenter/median ordering + Brandes–Köpf coords) | Manual **align / snap / distribute** heuristics | **BFS longest-path layering**, no crossing reduction |
| Crossing reduction | Yes (iterated barycenter, Fenwick-tree crossing count) | No | **No** |
| Coordinate assignment | Brandes–Köpf (4-way, balanced) | fixed offset chaining | cumulative-height stacking |
| Cycle handling | assumes DAG (networkx topo sort) | n/a | assumes DAG (BFS) |
| Respects pinned/locked | **No** | No (anchors on active node) | No |
| Frames/clusters | Yes (nesting graph) | No | partial (groups recursed) |
| Licence | GPL-3.0 | GPL-3.0 | GPL-3.0 |
| Maturity | active (2026-07), modular, paper-cited, 23★ | dormant (2022), 56★ | dormant (2022), derivative, 4★ |

---

## 3. The standard algorithm these approximate (primary sources)

All three (where they do real layout) are approximations of the **Sugiyama framework** for layered
(hierarchical) graph drawing. Canonical four phases:

1. **Cycle removal** — reverse a small edge set to make the graph acyclic (greedy feedback-arc-set).
   *None of the three addons implement this* — they assume acyclic node trees.
2. **Layer / rank assignment** — put each vertex in a layer so edges point one way. Two common methods:
   longest-path (what KenzKD does by hand) and **network simplex**
   (Gansner, Koutsofios, North, Vo, *A Technique for Drawing Directed Graphs*, IEEE TSE 19(3), 1993 —
   DOI [10.1109/32.221135](https://doi.org/10.1109/32.221135); this is the algorithm behind Graphviz
   `dot`, and the one node-arrange's `ranking.py` reimplements).
3. **Crossing minimisation / ordering** — order vertices within each layer via repeated
   barycenter/median sweeps between adjacent layers (node-arrange's `ordering.py`).
4. **Horizontal coordinate assignment** — the widely used method is **Brandes & Köpf, *Fast and Simple
   Horizontal Coordinate Assignment*, GD 2001, LNCS 2265**, DOI
   [10.1007/3-540-45848-4_3](https://doi.org/10.1007/3-540-45848-4_3) — a linear-time block-alignment
   method run in four directions and combined. Note the **2020 erratum** (two bugs in the original)
   [arXiv:2008.01252](https://arxiv.org/abs/2008.01252) — implement from the erratum, not the 2001 text.
   node-arrange's `y_coords.py` cites exactly these two.

**Reference implementations worth knowing** (to read/validate against, not to depend on):
- **Graphviz `dot`** — the original network-simplex + BK pipeline (C). Canonical baseline.
- **dagre** (JavaScript, MIT) — a clean, readable Sugiyama implementation; its structure is the usual
  teaching model for a from-scratch port.
- **ELK / elkjs "layered"** — the most complete open layered layouter, but **Java** (elkjs is a JS
  transpile). Explicitly out of scope for Haywire: heavyweight, wrong runtime (see task constraints).
- **networkx** itself has **no** layered/Sugiyama layout (only spring/spectral/planar) — which is
  exactly why node-arrange had to write the whole pipeline on top of it. So "just add networkx" does not
  get Haywire a layered layout for free; the algorithm code is the deliverable regardless.

---

## 4. Licence compatibility (important)

- **All three addons are GPL-3.0** (verified: `license.spdx_id == "GPL-3.0"` for each via `gh api`; and
  every source file carries an SPDX/GPL header). Blender addons are GPL because they link Blender's
  GPL Python API — this is the norm.
- **Implication**: copying, adapting, or close-porting their *source code* into Haywire would make the
  derivative work GPL. If Haywire is (or intends to stay) permissively licensed, **do not lift code**
  from node-arrange / align_nodes / KenzKD.
- **What is safe**: the **algorithms** — Sugiyama phases, network-simplex ranking, barycenter ordering,
  Brandes–Köpf coordinate assignment — are published academic methods and are **not** covered by the
  addons' copyright. They must be **reimplemented from the papers** (§3), which double as the correct
  primary spec (BK erratum included). node-arrange is best used as a *cross-check reference while
  reading the papers*, keeping a clean-room boundary.
- **Confirm before building**: I did not find/verify Haywire's own licence in this pass — confirm the
  repo's target licence before deciding how strict the clean-room boundary must be. (If Haywire is
  itself GPL, the constraint relaxes, but a from-paper reimplementation is still preferable for a
  dependency-free, dual-flow-aware fit.)

---

## 5. Fit for Haywire

### 5.1 Which algorithmic approach

**Layered (Sugiyama) layout is the right model**, but a *pared-down* one, not node-arrange's full
cluster-aware machine. Reasoning:

- A Blueprint-style graph is a **left-to-right DAG-ish flow** — exactly the shape layered layout is
  designed for. Users expect "sources on the left, sinks on the right, flow reads one direction," which
  is what rank-assignment produces and what align/distribute heuristics (align_nodes) *cannot* produce.
- The cheap BFS approach (KenzKD) gives layers but **no crossing reduction**, so wide graphs look
  tangled. One barycenter ordering pass is a small amount of code and the single biggest quality win —
  worth including.
- align_nodes-style align/snap/distribute is genuinely useful, but as a **secondary manual toolset**
  ("tidy these few nodes"), not as the auto-arrange. It should not be the primary answer.

**Pure-Python / no heavy dep**: fully achievable. The four phases are a few hundred lines of plain
Python over Haywire's own `node_wrappers`/`edge_wrappers` dicts. **networkx is not required** —
node-arrange only leaned on it for generic graph plumbing (topo sort, tree ops), all of which is easy
to inline for this bounded problem. Do **not** add networkx (let alone ELK/Java). Recommended scope for
a first cut: **longest-path (or simplex) ranking + one-or-few barycenter ordering sweeps + a simple
per-column X cursor + within-column Y stacking**; optionally upgrade Y to Brandes–Köpf later for
straighter edges.

**Dual-flow question — which edges drive layering?** Haywire edges carry a `FlowType`
(`CONTROL / DATA / CALLBACK / NONE`; `packages/haywire-core/src/haywire/core/types/enums.py:4-17` and
`.../types/port.py`). Options:

- *Control-only layering*: ranks follow execution order — clean "program reads left-to-right," matches
  Blueprint mental model. But data-only subgraphs (pure-value nodes with no control pins) would be
  unranked and pile up.
- *Data-only layering*: matches Blender/shader intuition (node-arrange's world), but ignores execution
  order, which is Haywire's defining axis.
- *Both (recommended)*: build **one directed graph from the union of control + data edges**
  (ignore/soft-weight CALLBACK, and NONE) and rank on that. This keeps every node ranked, keeps flow
  monotonic, and is what the addons effectively do (they only have one edge kind). If desired, give
  **control edges a higher weight** in ranking/ordering so execution order dominates when control and
  data disagree — a small, principled tweak, not extra machinery. Layer index → X (left→right), position
  within layer → Y. **Recommend: union graph, control-weighted.**

**Cycles**: Haywire is *not* guaranteed acyclic the way Blender node trees are (control flow can loop;
data feedback is possible). Unlike all three addons, Haywire's layout **must** include a **cycle-removal
pass** (greedy feedback-arc-set: DFS, provisionally reverse back-edges, rank on the acyclic version,
restore edge identity for rendering). This is the one phase to add that the reference addons omit.

**Pinned**: `pinned` already exists (`.../node/properties.py:69-75`, "Prevent auto-layout from moving
this node"). None of the three addons support it — this is Haywire-specific and must be built:
- Simplest correct behaviour: **exclude pinned nodes from `move_nodes_to`** (compute their layout
  position but never emit it), so the rearrange flows around fixed anchors.
- Better: treat pinned nodes as **fixed constraints** — keep their current rank/column so surrounding
  nodes lay out relative to them. Start with "compute-but-don't-move"; upgrade to constraint-aware later.

### 5.2 Integration sketch (algorithm + seam only — not DI design)

- **Where**: a pure function/module, e.g. `arrange_layout(graph) -> dict[str, dict[str, float]]`, in
  core graph code (peer of `editor.py`). It takes the graph, returns the positions dict; it performs
  **no** mutation and touches no UI/DI. This keeps the algorithm unit-testable in isolation.
- **Consumes**:
  - `graph.node_wrappers` (`dict[id -> NodeWrapper]`) and `graph.edge_wrappers`
    (`packages/haywire-core/src/haywire/core/graph/base.py:111`).
  - Per node: dimensions `node.props.width` / `node.props.height`
    (`.../node/properties.py:124-125`), current position `node.props.get_position()`
    (`.../node/properties.py:138`) — needed for the pinned-anchor case and for centering.
  - Per node: `node.props.pinned` (`.../node/properties.py:69`) — excluded/constrained.
  - Per edge: endpoints + port `FlowType` to build the directed layering graph (control+data union,
    control-weighted).
- **Produces**: `positions: dict[str, dict[str, float]]` — `{node_id: {"posX": x, "posY": y}}` — for
  every non-pinned node, keyed by node id.
- **Sink**: `editor.move_nodes_to(positions)`
  ([`.../graph/editor.py:133`](packages/haywire-core/src/haywire/core/graph/editor.py)), which wraps the
  whole rearrange in one **`MoveNodesToAction`** — a single undo step (exactly the intended seam;
  editor.py:138). The existing Farmhand tool `GraphEditorMoveNodesTool` (registry_id `move_nodes`,
  `barn/haybale-graph-editor/haybale_graph_editor/farmhands/editor_tools.py`) already wraps this, so an
  agent-triggered "arrange" is also reachable by having a small tool compute positions then call the
  same path.
- **Axis mapping**: **rank/layer → posX** (left→right = flow direction), **order-within-layer → posY**.
  Column X cursor = `x += max_width_in_column + margin_x`; within a column, stack by
  `y += node.height + margin_y`. This mirrors node-arrange's `assign_x_coords` (per-column width cursor)
  and its Y stacking, but transposed to Haywire's left→right convention and without the frame/cluster
  and reroute complexity.
- **Determinism/centering**: seed any randomness (node-arrange uses `random.seed(0)`); recenter the
  computed layout on the pre-arrange centroid (or on the active/pinned nodes) so the graph doesn't jump
  in the viewport — cheap, and matches node-arrange's `old_center`/recenter behaviour.

---

## 6. Recommendation

1. **Reimplement, don't vendor.** All candidates are GPL-3.0; copy no code. Implement the Sugiyama
   phases from the papers (§3), using node-arrange as a correctness reference to read alongside them.
   Confirm Haywire's own licence first (§4).
2. **Pure Python, no new deps.** No networkx, no ELK/Java. The bounded problem needs only stdlib.
3. **Phased scope**:
   - *v1*: cycle-removal (greedy FAS) → longest-path ranking on the **control+data union graph
     (control-weighted)** → one/few **barycenter ordering** sweeps → per-column X cursor + within-column
     Y stacking → recenter. Respect `pinned` by **compute-but-exclude** from the emitted positions.
   - *v2 (optional)*: swap ranking to **network simplex** and Y to **Brandes–Köpf** (per its 2020
     erratum) for straighter edges; upgrade `pinned` to a hard positional constraint; add an
     align_nodes-style manual align/distribute toolset as a separate secondary feature.
4. **Single seam**: compute a `{id: {posX, posY}}` dict and hand it to `editor.move_nodes_to(...)` so the
   entire rearrange is one undoable `MoveNodesToAction`.

**Caveat to flag to the user**: the strongest reference implementation (node-arrange) is **GPL-3.0**, so
it can inform the design but its code cannot be reused in a permissive Haywire — the algorithm must be
built from the public papers. Also note the Brandes–Köpf **2020 erratum** if/when the BK coordinate step
is implemented (the 2001 paper has two known bugs).
