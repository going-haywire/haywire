# What the browser pays to render the studio, and how to measure it without being fooled

Four measured findings about the studio's rendering cost in the browser, and
the measuring rules they share. Each was first misdiagnosed by a measurement
that looked right: an fps number, a screenshot, a profile's top entry, or a
single engine.

1. [Measuring](#1-measuring): the rules and the instruments
2. [Element count and the render walk](#2-element-count-and-the-render-walk): every server message re-renders the whole page; a component costs ~3x a native tag
3. [Load stalls](#3-load-stalls): a large graph's load blocks the browser 1–3 s at a time; batching does not fix it
4. [Chrome-only cliffs](#4-chrome-only-cliffs): a per-widget 3D transform, element insertion over the canvas, and a promoted layer Chrome stops painting

Numbers marked "300-node fixture" were taken on `graphs/10x300nodes.haywire`
(300 nodes × 11 number widgets, no edges), deleted 2026-10-25. The current
corpus is `10x256n_5x224e` and `10x512n_5x448e`.

## 1. Measuring

- **Read the worst frame gap or main-thread wait, never fps or averages.** A
  stall at the start of a gesture leaves mid-gesture framerate, mean frame
  time and fps looking correct. And fps actively rewards some failures: not
  painting half the canvas is cheap (section 4.3).
- **Measure in both engines, and in the one the user is in.** The engines fail
  differently: Chrome's Layerize cliff does not exist in Firefox, Firefox's
  `[id="…"]` subtree scans cost nothing in Chrome
  ([[project_multi_canvas_dom_globals]]), and Firefox stalls longer on load.
- **Compare a settled run, not an early one.** Early in a load, every
  configuration looks the same because the load dominates. A cost that
  survives settling is yours (`earlyfreeze.py --settle 60`).
- **The top of a JS profile names who pays, not who causes.** A function that
  reads layout or computed style (`getBoundingClientRect`, `getComputedStyle`)
  is charged for the whole pending style and layout pass. Compare its sampled
  self time with the forced pass before blaming it (section 3).
- **Isolate paint with `visibility: hidden`, not `display: none`.** Hiding a
  child with `display: none` reflows its parent (hiding pins in a grid made
  panning *worse*, 6.05 → 2.16 fps), and when every part-by-part probe comes
  back flat while the whole is huge, suspect the container's own paint.
- **A screenshot is not evidence of paint completeness**: what is missing is
  missing, and the result looks plausible. Use `paintcheck.py`.
- **A synthetic event cannot see a blocked main thread.** A wheel dispatched
  from a probe runs only once the thread is free.
- **Keep the measurement off your own studio and graph.** `studioctl start`
  reuses whatever studio holds the port, including your interactive one. A
  probe that presses a mouse button can commit edges or move nodes in the
  fixture graph; check `git status` after a run. A graph is restored on page
  load only if it is listed in the active haystack (`last_haystack_name` in
  `.haywire/settings.json`); snapshot that file and `workspace_state.json`
  before a run and restore both after.

### Instruments

`.scratch/pan-perf/` drives a live studio headlessly or headed (see its
README); `session.py` is the shared plumbing (signed session cookie,
readiness). `.scratch/draw-perf/` times a load until fully drawn.

```sh
uv run python .scratch/pan-perf/panperf.py --runs 3                  # pan frame gaps
uv run python .scratch/pan-perf/panperf.py --runs 1 --trace /tmp/t.json
uv run python .scratch/pan-perf/analyze_trace.py /tmp/t.json --last 5
uv run python .scratch/pan-perf/paintcheck.py --zoom 0.069 [--pan]   # unpainted cards
uv run python .scratch/pan-perf/earlyfreeze.py --settle 60           # early vs settled pan
uv run python .scratch/pan-perf/startupgap.py --engine firefox       # main-thread wait during a load
uv run python .scratch/pan-perf/loadtrace.py --out /tmp/load.json --seconds 35
uv run python .scratch/pan-perf/loadtrace_analyze.py /tmp/load.json --app-only
```

`panperf.py --css '<hypothesis> !important'` bisects CSS without a source edit
or a studio restart. `.scratch/draw-perf/measure_engine.py` times a load until
every card and edge is drawn, in either engine.

To time a whole-page update directly: the root instance is `mounted_app` (a
module-scope `let`, not on `window`) or
`document.getElementById('c0').__vueParentComponent.proxy`. Measure
`$forceUpdate()` → `nextTick`. Do not time `inst.render.call(app, app)` alone:
outside a rendering instance `Vue.resolveComponent` takes a warning path and
the number is inflated.

## 2. Element count and the render walk

NiceGUI renders the entire page as one Vue component
(`nicegui.js`: `render() { return renderRecursively(this.elements, 0) }`), with
no memoization: upstream added a vnode cache (PR #5761) and reverted it, and
it is still absent at 3.13.0. Every server message rebuilds a VNode for every
element on the page, so the studio's responsiveness is element count times
per-element cost, paid on unrelated interactions too (clicking a Properties
field, switching a tab).

**A component costs ~3x a native tag.**

```js
Vue.h(app.config.isNativeTag(element.tag) ? element.tag : Vue.resolveComponent(element.tag), ...)
```

A native tag (`div`, `i`, `span`) becomes an element VNode. Anything else
(`q-icon`, `nicegui-drag`, any `.vue` component) gets a component instance,
its own props validation and its own render on patch. One whole-page update on
the 300-node fixture (33,954 elements), median of 9:

| tree | update |
|---|---|
| as shipped | **723 ms** |
| 6,611 `q-icon` retagged to `div` (count unchanged) | 545 ms |
| 3,294 `nicegui-drag` retagged to `div` | 614 ms |
| both | 513 ms |

About 30% of the cost was componentness alone: a plain div ~15 µs, a component
~40–45 µs. Moving pins off `q-icon` for real (`PinGlyph`) measured 723 →
619 ms (−14%); the retag simulation over-predicted −25%, so use retagging to
rank candidates, not to forecast.

**The rule.** On anything rendered per port or per node, prefer a native tag.
For a Quasar component's look, borrow its CSS classes (`.q-icon` and
`.material-icons` are plain stylesheet rules) on an element you build
yourself, as `haywire.ui.skin.pin_render.PinGlyph` does, locked by
`tests/ui/skin/test_pin_native_tag_contract.py`. Carry the props the component
interpreted: `q-icon`'s `size` and `color` become an inline `font-size` and an
inline `color` or a `text-*` class.

It hides: the retag changes no pixels, one node is imperceptible, and neither
fps nor a canvas profile finds it, because the cost lands on the root update.

Also true, and easy to get wrong:

- **The currency is NiceGUI elements, not DOM nodes.** A custom Vue component
  is one element however much DOM its template emits (33,954 elements against
  50,729 DOM nodes on the 300-node fixture).
- **The walk descends only into slots a component actually invokes.** NiceGUI
  passes children as a slot function, so a component that does not call its
  slot stops the walk there. That is why an inactive graph is nearly free: a
  deactivated `keep-alive` tab panel does not invoke its slot (a 60-node graph
  active with the 300-node graph kept alive measured 139 ms), and why "it gets
  fast again when I switch to a small graph" is this, not anything
  graph-specific. The culling spike `haywire.ui.components.cull` tests the
  same mechanism.
- **Client-side culling does not work.** Editing `children` in the client's
  `elements` is undone: the server re-sends the parent within ~2 s. Culling
  must unmount on the server.

## 3. Load stalls

Opening a graph of several hundred nodes stalls the main thread 1–3 s at a
time while the cards arrive; a gesture started then waits. Worst single wait
after the first node lands, fresh studio, graph restored as the only open tab,
three runs each (2026-10-28):

| | 256 nodes (`10x256n_5x224e`) | 512 nodes (`10x512n_5x448e`) |
|---|---|---|
| Chrome | 1.1 / 1.5 / 1.1 s | 3.0 / 2.2 / 2.3 s |
| Firefox | 2.5 / 2.1 / 1.8 s | 2.9 / 2.0 / 3.4 s |

The thread is free when the page is handed over (3–31 ms). The stalls start as
nodes arrive (4–8 s in) and come in bursts; 512 nodes has a second burst at
16–35 s. A Chrome trace of the 512-node load has six tasks over 200 ms, 6.4 s
in total:

| Work | Time |
|---|---|
| Vue mounting and patching (`RunMicrotasks`) | ~3.1 s |
| of which the render walk (`renderRecursively`) | 1.67 s, four walks of 0.6–0.8 s |
| style recalculation of the new DOM | 1.6 s |
| layout | 0.8 s |

One style and one layout pass per task: no thrashing. Each task is one
delivered message: mount the cards, walk the whole tree, recalculate style,
lay out. The levers are elements per card (a 512-node page carries 12,800
`[data-node-id]` elements, ~25 per card) and the render walk (section 2).

- **Batching node mounts does not help.** The server already mounts node by
  node (`sync_with_graph_chunked`, `asyncio.sleep(0)` between), and NiceGUI's
  outbox bundles whatever was queued between two flushes anyway. Fixed batches
  were tried and reverted (`99478c54a`, reverted in `b07adc60a`): time until
  the 512-node graph was fully drawn was 13.7 s node by node, 23 s in batches
  of 5, 14.7 s in 25 and 14.4 s in 50, and a batch only delayed the first
  card. Pacing delivery to shorten each stall trades total load time for
  responsiveness; that was measured only for total time.
- **Do not "fix" the profile's top entries.** `_edgeGeometryLooksWrong`
  (canvas.vue) and the minimap's `_getThemeColor` lead the JS self-time list,
  but each only forces the pending style and layout pass: 1049 ms sampled
  against a 1048 ms forced pass, 736 against 735. The frame pays the same pass
  without them.
- **What the user feels:** a gesture freezes, the graph jumps, then it is
  smooth, "gone after about a minute" (the load finishing). A pinch or
  ctrl+wheel during a stall can zoom the page instead of the canvas (only View
  > Actual Size undoes it): canvas zoom is `@wheel.prevent` on
  `.zoom-pan-container`, and Chrome does not wait for a blocked non-passive
  listener. Registering the listener earlier does not help. Whether this still
  happens is unverified (section 1, synthetic events).

## 4. Chrome-only cliffs

Firefox (WebRender) is unaffected by all three, so Firefox-side perf work
neither finds nor fixes them.

### 4.1 A 3D transform on a per-widget element

`.number-drag::after`, the focus underline on every number widget, used
`transform: scale3d(0, 1, 1)`. A 3D transform gives the element its own
transform node in Blink's paint property tree and blocks the paint-chunk
merging that `Layerize` (`PaintArtifactCompositor::Update`) depends on. One
costs nothing; 3,300 of them (300-node fixture) cost ~500 ms per Layerize,
86.5% of the main thread: 6 fps, half-drawn cards, and an unpainted app shell
(top bar, tabs, sidebar) because the compositor was too starved to raster.
The 2D `scaleX(0)` draws the same: 6.05 → 87.19 fps, p99 525 → 25.6 ms.
Firefox measured 18.94 fps with the fix and 18.99 without.

- Never `scale3d` / `translate3d` / `translateZ` / `matrix3d` on anything that
  appears once per widget, per pin or per node; use the 2D form. Judge by how
  many elements carry it, not by how heavy one looks. The design guide's
  underline animation (§8.25) is `scaleX`.
- `[data-node-id].dragging-node` in canvas.vue carries `translateZ(0)`. It
  matches one card at a time, so it is fine; do not copy it onto a selector
  that matches every node.
- Signature: `Layerize` dominating `CrRendererMain` self time in a trace.

### 4.2 Inserting an element over the canvas

Adding a DOM element into `.zoom-pan-container` re-layerizes the node subtree
below it, at the same scale (~500 ms per insertion, 300-node fixture), and
unlike a load stall it never settles. Worst frame gaps in ms during one short
pan, early and settled:

    inserted per gesture   EARLY [599, 530, 530, 516]   SETTLED [540, 253, 109, 92]
    inserted once, kept    EARLY [653, 512, 496, 493]   SETTLED [ 73,  61,  59,  59]
    no overlay at all      EARLY [555, 539, 118,  95]   SETTLED [ 78,  66,  65,  62]

An element that appears and disappears over the canvas must be created once
and toggled with a property that changes neither geometry nor paint
(`pointer-events`, or `opacity` on an already-composited layer).

### 4.3 A promoted layer Chrome stops painting

`will-change: transform` on `.zoom-pan-content` (`zoom/pan.vue`) made Chrome
stop painting part of the layer once the content in view got large: whole rows
of cards absent below a fixed line, at rest, indefinitely (300-node fixture,
`paintcheck.py`):

| zoom | cards in view | unpainted, promoted | unpromoted |
|---|---|---|---|
| 0.069 (fit) | 300 | **152** | 0 |
| 0.09 | 208 | **53** | 0 |
| 0.15 | 62 | 0 | 0 |

The promotion was removed. It had survived a review because the broken
configuration measured faster (86.8 fps with 155/208 cards painted against
38.1 fps with 208/208): not drawing is cheap. It was then wrongly reported
fixed by the 4.1 change on the strength of two screenshots; 4.1 fixed the
unpainted shell, not these cards (49.7% vs 50.7% unpainted). Firefox measured
19.08 vs 19.07 fps either way, so the removal costs Firefox nothing.

- Check any change to compositing, promotion, layer structure or
  `will-change` with `paintcheck.py`, never with `panperf.py` alone.
  `paintcheck.py` writes an annotated PNG boxing every unpainted card and
  excludes cards behind the debug HUD and the minimap.
- If promotion is ever restored, gate it on zoom (harmless at >= 0.15; the
  canvas's `data-lod-level` / `zoom-pan-lod*` classes fit this shape of rule)
  and re-run `paintcheck.py` at 0.069, the case that breaks first.

Related: [[project_large_graph_perf]], [[project_multi_canvas_dom_globals]], [[project_wheel_gesture_classification]].
