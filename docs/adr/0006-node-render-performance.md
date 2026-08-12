---
name: node-render-performance
description: Authoritative record of large-graph rendering perf work — measured root causes, upstream constraints, shipped optimizations, and declined levers
status: accepted
level: tactical
---

# Large-graph rendering & interaction performance

Authoritative record of the graph-editor performance work: the measured root
causes, the upstream constraints, every shipped optimization, and the levers
evaluated-and-declined. Supersedes the scattered notes in prior sessions; this
is the document to read (and update) before any further perf work on node
rendering.

---

## Context — two distinct cost axes

Large graphs (~200 nodes, ~20–23 ports each) are sluggish in two *separate* ways.
They share one currency — **raw NiceGUI element / VNode count** — but manifest at
different moments and were diagnosed independently.

**Axis A — construction cost (graph open / editor switch).** Selecting a graph in
the Haystack editor renders every node card synchronously on the Python side
(`visual_layer.sync_with_graph` → `on_validated` → per-node `add_node_visual` →
`UINode.render` → skin) before anything reaches the browser. On the 200-node
reference graph (`graphs/10x200nodes.haywire`, **0 edges**, 23 ports × 200 nodes)
this was ~2.7 s.

**Axis B — per-interaction cost (everything is slow while a big graph is the
active tab).** Clicking unrelated UI, switching a side-slot editor, or selecting
a node lags for seconds. **Proven by reading `nicegui.js`, not assumed:** NiceGUI
renders the ENTIRE page as ONE Vue component whose `render()` is
`renderRecursively(this.elements, 0)` — an unconditional, non-memoized walk of
the whole element tree on EVERY update, building a fresh `Vue.h(...)` VNode per
element. `this.elements` is one reactive object holding every element on the
page. So any mutation (even an unrelated tab click) dirties the single root →
full O(total-elements) render walk. Vue's diff then patches only what changed,
but the walk cost is already paid. A 200-node graph is tens of thousands of
elements, so the walk dominates every interaction. Focusing a *small* graph
restores responsiveness — `ui.tab_panels(...).props("keep-alive")` wraps slots in
Vue `<KeepAlive>`, which deactivates the inactive big panel's effects.

The unifying thesis both axes confirm: **the lever is element COUNT per node**
(each `ui.element`/`ui.label`/widget = one VNode built per page render and one
object to construct). LOD class tuning changes paint cost only, not element count,
so it helps pan but not the construction or re-walk costs.

## Upstream constraint (don't re-discover this)

NiceGUI shipped the exact fix for Axis B — PR #5761 *"Cache vnodes to avoid
unnecessary re-renders"* (memoizes `renderRecursively`, skipping unchanged
subtrees), in milestone 3.8 — then **REVERTED it** after regressions (e.g. #5823:
`ui.log` auto-scroll broke because cached vnodes skipped `updated()`). Verified
against the installed `nicegui/static/nicegui.js` (3.12.1): NO vnode cache;
`renderRecursively` rebuilds unconditionally. **Upgrading NiceGUI does not fix
this.** No open upstream issue tracks a clean re-implementation. Implication: any
Axis-B fix must be Haywire-side (reduce element count, or isolate the graph
subtree from the root render). Upstream's general guidance for large UIs is
"render fewer elements," not per-element optimization (zauberzeug/nicegui#338,
discussion #2876) — `expects_arguments` (Axis A, decision 2 below) was the one
exception: it was fixed upstream in NiceGUI 3.15, after being uncached on
`main` as of 2026-06.

## Diagnosis & measurements

Instruments are kept as `@pytest.mark.perf` tests (excluded from the default
suite; `uv run pytest -m perf tests/ui/widget/ -s`). See
`tests/ui/widget/README.md`. The browser-side findings below came from throwaway
Chrome-flame-chart probes (not retained).

**Axis A, profiled (`test_skin_render_profile.py`, 2026-06).** Overturned two
intuitive-but-wrong hypotheses:

- Widget construction is NOT dominant — `render_widget` is only ~13 % of render.
- The dominant *single* CPU cost is `events.handle_event` →
  `helpers.expects_arguments` → `inspect.signature`, ~674×/node (~135 000× for
  the graph). Every `.props()`/`.style()`/`.classes()` mutation fires an
  observable change handler that re-introspects the same fixed set of handler
  functions; `expects_arguments` is pure and signatures never change, so all but
  the first call per handler is wasted.
- Largest *element-count* source at the time: pin tooltips — each port eagerly
  built a QTooltip + 1–2 labels (3 elements), ~69 of ~155 elements/node (~45 %),
  all invisible until hovered. ~23–30 % of render time.

**Axis B, flame-charted (2026-06).** Editor-switch and node-select each showed
deep repeating `renderRecursively` towers. Ruled OUT as causes (so the mechanism
above is the real one): edge-update loop (graph had 0 edges yet still lagged);
PropertiesEditor redraw (lag identical whether Properties open or closed);
canvas `document.body` capture listeners (toggled off — no change);
`SelectionMoved` subscribers (only `node_settings` subscribes; lag independent
of it). `.node-selected` is box-shadow only — selection does not re-render the
card server-side.

**Browser-side pan (2026-06, earlier session).** Zoomed-out pan jank: Chrome
showed `Layerize` (compositor rebuilding the GPU layer tree) dominating, NOT
scripting — driven by the size of the transformed DOM subtree inside the
`will-change: transform` layer. CSS mitigations that did NOT help: removing
`will-change`/`translateZ`/`perspective`; `content-visibility:auto`; hiding the
8000×8000 connection SVG; per-frame `display` toggling for node culling (made it
WORSE — layout thrash). What DID help in probes: hiding the per-node widget/label
layer (`zoom-pan-lod2`) ~doubled fps; box-only ~4×. A first attempt to convert
LOD from `opacity:0` to real `display:none` regressed the zoomed-in / select
path badly (~5 s selects) and was reverted — **the cost is *transitioning*
detail in/out across many nodes, not merely rendering it.**

**Element census (reconcile the two numbers).** Earlier session (2026-06, before
the lazy-tooltip fix and counting inner DOM of widgets): ~187 DOM elements/node,
~37 400 total; labels the largest separate-element count, layout wrapper divs
only ~6 %. This session's Python-`Element` census (counting NiceGUI `Element`
constructions, not inner widget DOM): 155/node pre-tooltip-fix → **86/node**
after. The two methods differ (DOM nodes vs NiceGUI `Element` objects) and the
graph changed between them (the pin-gutter fix below had already landed); both
are recorded with their dates rather than averaged.

## Decisions — shipped optimizations

All three attack element count or per-element introspection; none touch the
Vue↔Python ownership boundary.

1. **Pin-gutter wrapper div removed** (2026-06, earlier session;
   `NodeSkin._render_pin` `cell_style` param). The pin now sits directly in its
   CSS-grid column (carrying `grid-column` + `justify/align-self: center`) instead
   of an extra wrapper div: 3 structural divs/port → 2. ~4 400 fewer elements on a
   200-node graph (~12 %). User-confirmed felt improvement — first practical
   validation of the element-count → cost thesis.

2. **~~`expects_arguments` cached at startup~~ — removed, fixed upstream (2026-08-12).**
   Shipped as a bounded `functools.lru_cache(maxsize=1024)` monkeypatch
   (`haywire.ui.nicegui_patches`) over `helpers.expects_arguments`, worth
   ~1.25× on Axis A CPU. NiceGUI 3.15 resolved `expects_arguments` once at
   handler-registration time instead of per-fire — the exact upstream fix
   anticipated below — making the local patch redundant. Removed in
   `843b218d`; the module and its `HaywireApp.__init__` hookup are gone. Kept
   here only as a pointer: if a future NiceGUI regression reopens this cost,
   the bounded-cache approach and its leak pitfall (below) are the known-good
   shape to reach for again.

3. **Lazy pin tooltips** (this session; `NodeSkin._add_pin_tooltip`). The tooltip
   (3 elements) is built on the pin's first `mouseenter` rather than at render,
   with visibility driven explicitly (`mouseenter`→build+show, `mouseleave`→hide)
   and `no-parent-event` on the QTooltip so our handlers are the SOLE controller.
   Measured: elements/node 155 → 86; render ~1.46× faster. Attacks both axes
   (fewer elements built AND fewer in the re-walk).

Combined, graph-open dropped from ~2.7 s toward ~1.4 s.

## Rationale for the tricky choices

**Patching a vendored internal (`expects_arguments`), while it was live.** Not
cached upstream at the time; the win was unavailable any other way short of
forking. Bounded to avoid a handler-pinning leak — the cache key is the
handler object, and handlers are bound methods recreated per element/
collection, so an unbounded cache (the first version, using `maxsize=None`)
pinned every handler and its element for the process lifetime. A
`WeakKeyDictionary` did not help (bound methods are recreated per access, so
weak keys evict before they hit); a bounded cache lost nothing since
per-element fires are consecutive (measured: every `maxsize` from 4 to `None`
gave the same 73% hit rate and ~1.4× speedup). The guard raised at startup if
the NiceGUI internal moved/renamed, rather than silently reverting. This was
always framed as a bridge, not a destination — see decision 2 above for the
upstream fix that made it removable.

**`no-parent-event` + explicit show/hide for tooltips.** A tooltip built on
`mouseenter` mounts *after* the event fired, so Quasar's hover listener misses
the first hover (appears only on the second). Manually `show()`-ing while leaving
Quasar's hide active then orphans tooltips on screen (two controllers disagree).
Sole-controller (`no-parent-event` + our handlers) is the only deterministic
option; mirrors how `node_menu_builder` drives flyouts explicitly on hover.

## Consequences

- First hover of a given pin pays a server round-trip to build+show its tooltip
  (subsequent hovers instant). Consistent with existing hover-built UI. Accepted.
- Measurement instruments retained as `perf` tests for re-measuring future
  changes against the same reference graph.
- Mount lifecycle facts for any future culling work: nodes mount in
  `VisualLayerHandlers.add_node_visual` (`ui.element` div → `UINode` → skin
  card), tracked in `self.node_panels[node_id]`; `remove_node_visual(node_id)`
  fully unmounts+deletes. These are the levers if Axis-B culling is ever revisited.

## Considered and declined

Recorded so they are not re-litigated as the "obvious next step":

- **Off-screen node culling / deferred mount.** Three layers:
  (1) CSS `display:none` for off-viewport nodes — the existing zoom-LOD system
  (`pan.vue`, `data-lod-level` → `opacity:0`/`pointer-events:none`) already covers
  pan, and per-frame display toggling was *measured to make pan worse* (layout
  thrash); (2) Vue `v-if` unmount — fights NiceGUI's 1:1 `Element`↔component
  coupling; (3) Python-side deferred construction (skip `add_node_visual`
  off-viewport) — the only layer that helps Axis A, but a long tail of edge cases
  (edges crossing the built/culled boundary, selection/state for UI-less nodes,
  teardown/rebuild policy). High effort, high regression surface, for a node count
  most users rarely reach. The 0-edge reference graph makes layer 3 look
  deceptively easy; a real edged graph is where the hard part lives. Declined.

- **Further structural-div / label reduction per port row.** One round already
  shipped (decision 1). Collapsing the remaining content div or merging the label
  into the widget conflicts with a hard requirement: **labels must stay
  skin-rendered (not merged into widgets), and widgets must remain independent
  components usable across inlet/outlet/config.** The pin/label/widget alignment
  is load-bearing CSS grid; further collapsing risks alignment regressions for a
  modest count reduction. Worse risk/reward than the wins above. Declined.

- **Upgrading NiceGUI for the vnode cache.** The fix was reverted upstream and is
  absent from 3.12.1 (see Upstream constraint). Declined — does nothing.

The shipped optimizations are the high-leverage, low-risk levers. The work stops
here by choice — at diminishing returns and rising risk — **not** because render
cost is exhausted. The genuinely large remaining lever (Axis-B element-count
reduction via culling) is gated on the Vue↔Python boundary work above and is
deferred, not forgotten.
