---
name: N graph canvases are mounted at once, and parts of the canvas still resolve one
description: Groups open in their own keep-alive tab, so several canvas.vue instances are live in the DOM at the same time; every document-global DOM lookup inside the canvas now reaches the wrong one
type: project
---

The EDIT slot is a headless `ui.tab_panels` with `keep-alive`: every open graph
keeps its panel in the DOM and switching is a `set_value`
([slot.py](../packages/haywire-core/src/haywire/ui/app/slot.py) —
`_create_panel` / `_ensure_drawn`). `GraphEditor` nests a second one inside its
own panel, one level per Group the user stepped into
([graph_editor.py](../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py)
— `_mount_level`). So a single session routinely holds one canvas per open
document plus one per open Group, all mounted, all running the same `canvas.vue`
template.

That template is repeated verbatim per canvas, so **every id inside it is
duplicated**: `connection-svg`, `node-container`, and anything else written as a
literal. The canvas root is the one element with a unique id —
`:id="containerId"`, from
[canvas.py](../packages/haywire-core/src/haywire/ui/components/graph/canvas.py)
(`GraphCanvasVue.container_id`). Scope DOM queries to it:

```js
const root = document.getElementById('<container_id>');
const svg = root ? root.querySelector('.connection-svg') : null;
```

`VisualLayerHandlers._await_client_drawn` does this, and
[debug_overlay.vue](../packages/haywire-core/src/haywire/ui/components/debug_overlay/debug_overlay.vue)
does the same by class, for the same reason.

**A deselected `q-tab-panel` is not in the DOM**, and it gets there two
different ways — which is the distinction that cost three wrong diagnoses:

| | First time a panel is selected | Every time after |
|---|---|---|
| Vue | mounts the component | `keep-alive` **deactivates**, then reactivates it |
| Hook | `mounted()` | `deactivated()` / `activated()` |
| The canvas keeps | nothing — it is new | its `edgePaths` and its paths |
| Messages sent meanwhile | dropped: no component | delivered: the component is alive |
| `document.getElementById` | finds nothing | finds nothing — the tree is **detached** |

Both states answer 0 to `document.querySelectorAll('.graph-canvas').length`, so
a probe cannot tell them apart. Check the console for the mount log, or for
`activated`, before concluding which one you are looking at.

So the globals below bite only between canvases on screen *at the same time* —
several open documents, or a canvas next to the minimap — never between the
levels of one graph editor, which take turns.

## A canvas whose panel was deselected loses its edges, and its stale node shapes

Deselecting a panel destroys the canvas component; selecting it again builds a
new one. Its **nodes come back** — they are server-side NiceGUI elements, and
the framework re-renders them into the new panel. Its **edges do not**: those
are SVG paths `canvas.vue` builds itself, out of `run_method` messages that were
addressed to a component which no longer exists. Everything sent while the panel
was deselected went nowhere at all.

"Nodes come back" holds for a node whose **ports did not change** while the
panel was away — the element re-renders from current server state either way.
It does not hold for a card whose *shape* changed meanwhile, which is a
Graph-node: its pins mirror another graph's boundary nodes, so editing inside a
Subgraph reshapes the card on the hidden host canvas. See the section below.

Nothing on the Python side notices. `VisualLayerHandlers.edge_states` is the
server's record of *having sent* an edge, and `on_validated` skips any edge
already in it — so a naive "re-sync" emits an empty batch and looks like it
worked. `resync_edges()` exists precisely to bypass that guard.

The fix is mount-driven, not timing-driven: `canvas.vue`'s `mounted()` emits
`CanvasMountedEvent`, and `process_canvas_mounted` sends the edges back. Every
re-mount is covered by construction — first reveal of a Group level, a tab panel
re-keyed by a save-as, anything future. Do not try to push edges at a canvas
from the switch that reveals it: at that moment it does not exist yet.

The *reactivation* path needs nothing from Python — the component still holds
its edges. What it needs is `activated()`, which flushes edges parked while the
tree was detached and checks the geometry (below).

## A Graph-node reshaped while its canvas was hidden needs a belt-and-braces redraw

Growing a pin on a boundary node inside a Subgraph reshapes the Graph-node card
on the **host** canvas — which is the canvas the user is not looking at, because
they are inside the Subgraph. The model side is correct and needs nothing:
`reconcile_interface`'s `add()` goes through `rejig`, whose `_pop()` calls
`mark_as_structuraly_dirty()`, and `NODE_VALIDATION_REQUESTED` is in
`requires_redraw()`. Traced with the extra `redraw()` removed, the host batch
arrives with the card correctly flagged.

It still does not repaint, because `on_validated` refreshes through
`self.node_panels.get(node_id)` and the host canvas is a deselected panel at
that moment. `UINode.refresh()` ignores the reason it is handed and always
re-renders, so the reason is never what decides this — **delivery** is. Nothing
replays it on return: `process_canvas_mounted` resyncs edges only.

`GraphNode._on_definition_validated` therefore calls `self.wrapper.redraw()`
alongside the graph mark, on top of the mark the rejig already made. It works by
adding a *second* batch for the same card at a different point in the
debounce/mount sequence, so one of them finds the panel present. That is
odds-improving, not a guarantee — keep it, but do not read it as the mechanism
being sound.

**The real fix, when this bites again**: a node-side counterpart to
`resync_edges()` — on mount, re-render nodes whose ports changed while the
canvas was detached. Start narrow (Graph-nodes are the only cards another
graph's activity reshapes) and cover both paths, since first selection MOUNTs
while later ones keep-alive ACTIVATE. Do **not** "fix" it by pausing a hidden
graph's validation scheduler: a hidden graph is exactly where these edits
originate, paused marks re-create the load-time queue bug that
`force_validation`'s recursion into subgraphs closes, and haystack's unsaved and
autorestart gates would stop firing for every background graph.

## Pin coordinates come from the live matrix, never a cached zoom

`_transformScreenToSVG` converts a pin's screen rect into content space. It used
to divide by `zoomState.zoom`, which **starts at 1 on every mount** and is only
corrected when this canvas's own `ZoomPanContainer` reports in. Anything
measured in that window came out scaled by the ratio between the two, drawing
the whole edge set away from its pins at a constant factor.

Measured in the field with `.scratch/edgecheck.js`: `scaleRatio 2.303`, worst
endpoint 850px out — and **mixed**, 144 edges drawn wrong against 180 drawn
right, because the second group was parked and flushed later, once the zoom had
arrived. That mix is why sampling one edge to decide whether the set is healthy
gives a false negative.

It now reads `svg.getScreenCTM()` — what the browser is actually painting with,
which cannot be stale. The cached zoom survives only as a fallback for a
detached SVG, where nothing measurable exists anyway.

`edgecheck.js`'s `scaleRatio` is the diagnostic for the whole family: it is the
drawn span over the real pin span on screen, needs no access to the component,
and a value of k says the measurement used a zoom k times wrong.

## Where an edge gets drawn is also checked, not only reasoned about

Displacement arrived through several races around a canvas coming back on
screen: the cached zoom above, whether the DOM is attached, whether the nodes
have laid out. Each was plausible; each survived the harness test written for
it, and the one that proved real was only found by measuring a live session.
So the repair does not name a cause:

`_repairEdgeGeometryIfWrong` compares one drawn endpoint against its pin —
through `getScreenCTM()` and `getBoundingClientRect()`, sharing no arithmetic
with the code that drew it, so a canvas that measured wrongly cannot confirm
itself — and re-measures everything when they disagree. It runs after every
batch and on `activated()`. One edge decides: every way this goes wrong puts the
whole set out at once.

It is the automatic form of the user-discovered remedy, selecting every node and
deselecting again. If you find the underlying race, fix it too — but leave the
check.

Three bug reports were this one thing: a Group edited in the background came back
without the edges that changed, a save-as redrew the graph with no edges at all,
and both needed the tab closed and reopened.

**Edges also fail to draw for a reason that is not about panels**: geometry comes
from `getBoundingClientRect()` on the two pin elements, so an edge whose pins are
not in the DOM — a node culled off-viewport, or one still mounting from the same
message batch — cannot be created. That used to be final: logged, dropped, never
retried. `_pendingEdges` now parks them, and `_flushPendingEdges` retries on the
pending-node MutationObserver and on un-cull.

**What the load overlay waits for follows from that**: not one drawn path per
edge — parked edges make that count unreachable, and the overlay sat on its full
20 s deadline on any graph large enough to cull. `_syncAllEdges` stamps
`data-hw-edge-batch` on the canvas root once a batch has been through a render
tick, and `_await_client_drawn` waits for that counter to move.

## Still global, and what each one does when it bites

| Where | What happens with more than one canvas mounted |
|---|---|
| `_findNodesInRectangle` — `document.querySelectorAll('[data-node-id]')` ([canvas.vue:2368](../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L2368)) | A marquee sweeps every mounted canvas. `_getNodeBoundingRect` reads inline `left`/`top` and falls back to 100×50 when `offsetWidth` is 0, so a hidden card reports its real canvas coordinates: ids from another graph at overlapping coordinates ride along with the selection. |
| `_cleanupObservers` — `document.querySelectorAll('.ui-node-slot')` ([canvas.vue:986](../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue#L986)) | One canvas unmounting disconnects **every** canvas's per-slot size observers. Closing a background Group tab stops node re-measure on the canvas the user is looking at. |
| `document.getElementById(nodeId / pinUUID / edge_id)` throughout `canvas.vue` | Correct only because node ids are unique across a whole graph tree and pin/edge ids derive from them. Nothing enforces that across two open documents: ids are `uuid4().hex[:6]`, so a collision is improbable per pair and not structurally excluded (`BaseGraph.generate_unique_node_id`). |
| `SkinFactory`, keyed by `node_id` alone (`_nodeid_to_factory_subscriber`, `_nodeid_to_skin_regkey`) | App-wide, one instance for every session and every canvas. Two canvases showing the same node id share one subscriber set, and `_nodeid_to_skin_regkey` keeps only the last writer's. |
| `GraphEditor.draw()` clearing `EditState` selection | Selection state is per session, not per canvas. A first draw of any canvas clears the selection of whichever canvas the user was working in. |
| The graph-load overlay (`graph_load_modal`) | A full-viewport `Popup` backdrop at `z-index: 5000`. Opening a large graph blocks interaction with every already-drawn canvas, not just the one loading. |

## The standing cost of keeping them mounted

The page is one Vue component with no memoization, and the render walk scales
with total element count ([ADR 0006](../docs/adr/0006-node-render-performance.md),
`project_nicegui_component_vs_native_tag.md`). Every open Group is elements the
walk visits on every server message, so each one makes every interaction
fractionally slower. Two things release it: the X on the level's tab, and
`_prune_dead_levels`, which closes a level the moment its Subgraph stops
existing. Levels are never restored on restart — they are not in the workspace
snapshot, only their document is.
