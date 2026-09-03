# Zoomed-out pan performance — branch measurements

Started 2026-08-31. Baseline commit: `ceef2274`.

**Symptom.** `graphs/10x200nodes.haywire` (200 nodes, **0 edges**) with every node
collapsed still drops framerate badly during pan once zoomed out far enough to
see nearly all of them — even though each collapsed card is near-empty
(`show.ports()` returns only *linked* ports, and there are no edges, so the
cards carry zero pins).

That is the finding the whole experiment turns on: **the cost is per-card and
per-frame, not per-card-contents.** Each branch below isolates one candidate.

---

## Protocol

Same every time, or the numbers are noise.

1. `git checkout <branch>` → **restart the studio** (`uv run haywire`). A browser
   reload is not enough: `.vue` files compile at import.
2. Open `graphs/10x200nodes.haywire`, collapse all, enable the debug overlay.
3. Click **`zoom 0.09`** on the overlay. It reports the zoom it actually reached
   — the pan container floors zoom at "canvas fills viewport" when its min-zoom
   setting is automatic, so on a small window it can land higher than asked. That
   is fine as long as it is **the same on every branch**, which it will be at a
   fixed window size. Don't resize the window mid-comparison.
4. In the devtools console, tag the session once per branch:
   ```js
   window.__hwPerfBranch = 'perf/pan-hover-gate'
   ```
5. Click **`record 5s`**. A 3-second countdown runs first — **start panning
   during it** with a trackpad two-finger swipe, and keep it moving until the
   HUD shows the result.
   - Trackpad, *not* middle-mouse drag. Middle-drag moves the content with the
     cursor 1:1, so no card ever sweeps under the pointer and the hover
     hypothesis cannot show up.
   - Keep the sweep roughly the same speed and length each run. Pan distance is
     the input variable this protocol does not pin down.
6. The finished row appears in the HUD verbatim, and a **`copy row`** button
   appears next to `record`. Click it, then paste into the runs table below.
   (The copy must be button-driven: a clipboard write needs transient user
   activation, and by the time a run ends the click that started it is 8s old.)
   The row is also selectable in place, logged bare to the console, and kept in
   `window.__hwPerfRuns`.
7. **3 runs per branch**, take the median. Baseline first, and again at the end
   if the machine has been busy.

Notes on the instrument: during the window the overlay writes no text and
suspends its DOM census, so the numbers exclude the HUD's own cost. Scene counts
(zoom / LOD / els / nodes) are snapshotted when the window opens, i.e. after the
countdown.

**`perf/hot-path-logs` must be measured with devtools open.** It removes
`console` calls from hover and mutation paths, which cost nothing when nothing
is listening — measuring it with devtools closed tests nothing.

---

## Branches

**Baseline is `perf/measure-window`, not `master`.** It is master plus the
recorder and nothing else — no behaviour change — so it is the only way to
measure a baseline with the same instrument as every candidate. Each branch
below forks from it, so all of them carry an identical HUD.

| Branch | Change | Hypothesis under test |
|---|---|---|
| `perf/measure-window` | recorder only | **baseline** |
| `perf/pan-hover-gate` | `.hw-panning [data-node-id] { pointer-events: none }` during a pan burst | Hover churn: cards swept per pan is ∝ 1/zoom; each crossing toggles a stacking context, a 200ms box-shadow transition, `hw-lod-hover` subtree invalidation and 14 edge-map sweeps |
| `perf/pan-raf-coalesce` | rAF-coalesce `_setPanDirect` | Unthrottled floor: pan currently writes per mousemove/wheel event, and Mac trackpads exceed 60Hz |
| `perf/minimap-color-cache` | Cache the 4 `getComputedStyle` reads in `_draw()` | Forced style flush every frame, immediately after the transform write |
| `perf/edge-node-index` | `nodeId → Set<edge_id>` map, early-return when a node has no edges | Edge-sweep churn on hover (7 whole-map sweeps per enter *and* per leave) |
| `perf/hot-path-logs` | Drop `console.debug`/`log` from hover + style-mutation paths | Devtools-only cost |

And the branch that tests the leading hypothesis — 200 node containers each
carry an inline `z-index: 100`, so each is its own stacking context and its own
paint chunk; the compositor re-walks every chunk in the cull rect each frame,
and zooming out puts all 200 in it:

| `perf/node-zindex-drop` | Drop inline `z-index: 100` (`visual_layer.py:261`) and `[data-node-id] { z-index: 10 }` | Paint-chunk walk scales with cards inside the cull rect |

---

## Runs

Each finished run copies its row to the clipboard — paste it here.

| branch | fps | mean ms | p95 ms | p99 ms | max ms | stalls | eng | longtasks (ms) | lt-obs | LoAF (ms) | s+l ms | main ms | pan px | zoom | LOD |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ⚠ superseded (no pan px / no LoAF, provenance unclear) | 26.07 | 38.36 | 74.98 | 83.32 | 108.4 | 16 | ff | - | ? | - | - | - | ? | 0.150 | high |
| ⚠ superseded | 25.36 | 39.43 | 74.98 | 82.56 | 91.68 | 24 | ff | - | ? | - | - | - | ? | 0.150 | high |
| ⚠ superseded | 28.4 | 35.21 | 66.34 | 74.98 | 75 | 16 | ff | - | ? | - | - | - | ? | 0.150 | high |
| ⚠ superseded | 26.31 | 38.01 | 74.64 | 83.7 | 83.96 | 21 | ff | - | ? | - | - | - | ? | 0.150 | high |
| ⚠ superseded | 36 | 27.78 | 58.48 | 74.98 | 75.06 | 22 | ff | - | ? | - | - | - | ? | 0.150 | high |
| ⚠ superseded | 26.76 | 37.37 | 74.3 | 75.32 | 83.58 | 20 | ff | - | ? | - | - | - | ? | 0.150 | high |
| `perf/measure-window` | 13.13 | 76.13 | 141.74 | 166.64 | 166.64 | 66 | ff | - | void | void | - | - | 5313 | 0.090 | high |
| `perf/measure-window` | 12.37 | 80.81 | 149.44 | 150.1 | 150.1 | 63 | ff | - | void | void | - | - | 7455 | 0.090 | high |
| `perf/measure-window` | 12.28 | 81.45 | 141.8 | 150 | 150 | 62 | ff | - | void | void | - | - | 7292 | 0.090 | high |
| `perf/measure-window` | 17.37 | 57.58 | 150.3 | 167.3 | 167.3 | 54 | ff | - | void | void | - | - | 4854 | 0.084 | raw |
| `perf/measure-window` | 11.32 | 88.35 | 174.08 | 175.7 | 175.7 | 53 | ff | - | void | void | - | - | 5716 | 0.084 | raw |
| `perf/measure-window` | 11.58 | 86.35 | 166.68 | 175.62 | 175.62 | 58 | ff | - | void | void | - | - | 4695 | 0.084 | raw |
| `perf/node-zindex-drop` | 10.53 | 94.97 | 167.14 | 183.3 | 183.3 | 53 | ff | - | void | void | - | - | 5539 | 0.084 | raw |
| `perf/node-zindex-drop` | 12.17 | 82.18 | 158.34 | 166.72 | 166.72 | 61 | ff | - | void | void | - | - | 4982 | 0.084 | raw |
| `perf/node-zindex-drop` | 12.08 | 82.79 | 166.66 | 174.98 | 174.98 | 55 | ff | - | void | void | - | - | 5690 | 0.084 | raw |
| `perf/node-zindex-drop` | 34.4 | 29.07 | 42.2 | 50.1 | 50.9 | 2 | cr | 0 (0ms) | yes | 0 (0ms) | 0 | - | 7636 | 0.090 | raw |
| `perf/node-zindex-drop` | 24.92 | 40.13 | 49.4 | 50.1 | 50.1 | 3 | cr | 0 (0ms) | yes | 1 (53ms) | 0 | - | 3015 | 0.090 | raw |
| `perf/node-zindex-drop` | 25.12 | 39.81 | 42.5 | 50 | 50 | 0 | cr | 0 (0ms) | yes | 2 (102ms) | 0 | - | 2828 | 0.090 | raw |
| **`perf/flatten-3d`** | 15.22 | 65.69 | 83.28 | 92.18 | 92.18 | 75 | ff | 0 (0ms) | NO | n/a | n/a | **2.7** | 4371 | 0.090 | high |
| **`perf/flatten-3d`** | 14.78 | 67.67 | 83.32 | 92.18 | 92.18 | 74 | ff | 0 (0ms) | NO | n/a | n/a | **2.72** | 4965 | 0.090 | high |
| **`perf/flatten-3d`** | 14.43 | 69.29 | 83.34 | 83.62 | 83.62 | 72 | ff | 0 (0ms) | NO | n/a | n/a | **2.64** | 4703 | 0.090 | high |
| ⚠ branch unconfirmed (cr) | 23.48 | 42.58 | 50 | 50.1 | 50.1 | 4 | cr | 0 (0ms) | yes | 0 (0ms) | 0 | 2.18 | 1977 | 0.090 | high |
| ⚠ branch unconfirmed (cr) | 24.6 | 40.65 | 50 | 50.1 | 50.3 | 6 | cr | 0 (0ms) | yes | 0 (0ms) | 0 | 2.11 | 2038 | 0.090 | high |
| ⚠ branch unconfirmed (cr) | 23.68 | 42.23 | 50 | 50.1 | 50.8 | 3 | cr | 0 (0ms) | yes | 0 (0ms) | 0 | 2.14 | 2295 | 0.090 | high |

---

## Medians

| Branch | engine | fps | p99 ms | Δ fps vs matched baseline | Verdict |
|---|---|---|---|---|---|
| `perf/measure-window` @0.090 high | ff | 12.37 | 150.1 | — | baseline |
| `perf/measure-window` @0.084 raw | ff | 11.58 | 175.62 | — | baseline |
| **`perf/flatten-3d`** @0.090 high | ff | **14.78** | **92.18** | **+2.41 (+19.5%)** | **MERGE** — p99 -38.6%, spreads disjoint |
| `perf/node-zindex-drop` @0.084 raw | ff | 12.08 | 174.98 | +0.50 (+4.3%) | **DROP** — inside noise |
| `perf/node-zindex-drop` @0.090 raw | cr | 25.12 | 50.1 | no cr baseline yet | pending |
| `perf/pan-hover-gate` | — | — | — | — | **NOT BUILT** — main thread is 4% of the frame |
| `perf/pan-raf-coalesce` | — | — | — | — | **NOT BUILT** — same |
| `perf/minimap-color-cache` | — | — | — | — | **NOT BUILT** — same |
| `perf/edge-node-index` | — | — | — | — | **NOT BUILT** — same |
| `perf/hot-path-logs` | — | — | — | — | **NOT BUILT** — same |

Verdict = merge / drop / inconclusive.

---

## Combined

Winners rebase onto `master` in order, then re-measure — these interact
(rAF coalescing changes how often the hover gate re-arms), so combined ≠ sum of
parts.

| Stack | fps | p99 ms | Δ fps vs master |
|---|---|---|---|
|  |  |  |  |

---

## Observations

### CONFIRMED — hover during a pan costs 2.2x, and the property does not matter (2026-09-03)

Reported from Firefox, visible in both engines: hovering a node puts a slim
highlight box on it, and panning while that box is up is 3-4x slower. Let go of
the highlight and the pan is smooth again.

**It reproduces, and `perf/pan-hover-gate` — listed in the Branches table and
never built — is back on.** It was written off when the main thread looked idle;
that reading came from the retracted LoAF instrument.

Controlled measurement (`--fake-hover`, which rotates a class through one card
per frame under the normal per-frame auto-pan, zoom 0.09):

| probe | fps | main ms |
|---|---|---|
| control, no churn | **40.4** | 17.9 |
| class toggled, **empty rule** | 37.7 | 19.6 |
| inert custom property (`--hw-nothing: 1`) | 22.2 | 45.2 |
| `z-index: 1001` only | 18.8 | 53.1 |
| `outline: 1px` only | 17.9 | 55.7 |
| both (the real hover rule) | **18.2** | 54.9 |

**The finding is the flatness of that table.** Every rule that changes a
computed style on a card costs the same ~2.2x, including a custom property
nothing reads. Toggling the class with *no* rule attached is free (37.7 vs
40.4). So this is not the `z-index`, and not the `outline`:

> **Changing the computed style of one node card, once per frame, halves the
> framerate during a pan.** `main ms` ≈ `mean frame ms`, so it is entirely
> main-thread — style recalc and paint invalidation, not compositing.

The real hover does exactly that, twice per crossing (one card in, one out),
plus the JS handler's `hw-lod-hover` class. Cards swept per frame scales as
1/zoom, so at low zoom the real cost is likely worse than this 1-card-per-frame
model.

The indicated fix is the original gate: suppress hover for the duration of a
pan burst (`pointer-events: none` on cards, or neutralising the hover rule via
a container class). Expected recovery is the 18 -> 40 fps in the table.
**Not built — it changes interaction behaviour and is the user's call.**

#### ⚠ `--wheel-pan` is not an instrument

Real hover churn needs real pointer events: `setPan` moves content without
firing any, so the browser never re-runs hit-testing and the hovered card never
changes. `--wheel-pan` was added to get real churn, and its numbers must not be
used for comparison — its wheel events are driven on a wall clock, so a slow
frame receives fewer of them. Three runs of *identical* config gave
**16.3 / 56.1 / 66.8 fps** with pan travel spanning 555-2040 px.

An earlier pass through this section drew an A/B conclusion and a whole
CSS bisect from those numbers before the spread was checked. All of it was
noise; the table above replaces it. Use `--wheel-pan` to make a symptom
*appear*, never to size it.

### REJECTED — gating `will-change` on zoom. Measured, viable, and not worth it (2026-09-03)

The obvious follow-up to removing promotion was to put it back *above a zoom
threshold*, where it does not break painting, and recover the 87 fps there.
Built the measurements, then dropped the idea. Recorded so nobody rebuilds it.

**The mechanism is geometric, not a memory budget.** At a fixed viewport the
painted band is a constant in *layer-local* px — 4143 at zoom 0.05 and 4143 at
0.069, while covering 207 vs 286 css px. A tile-memory budget would hold
constant in device px, not layer px. (Close to Blink's 4000px cull-rect
expansion constant, but the correspondence was never proven — see the caveat
below.)

**The safe boundary is real and computable at runtime**, measured by sweeping
zoom at three viewport sizes (`paintcheck.py --sweep`):

| canvas (css) | lowest zoom that paints completely | viewport/zoom at that point |
|---|---|---|
| 799x435 | 0.08 | 5438 local px |
| 1199x735 | 0.12 | 6125 local px |
| 1327x819 | 0.12 | 6825 local px |

So the gate would be roughly `viewportHeight / zoom <= ~6000`, which the
component can evaluate for itself.

**And here is why it was dropped.** fps at the zooms where promotion is safe:

| zoom | promoted | unpromoted | gain |
|---|---|---|---|
| 0.12 | 80.6 | 41.7 | +93% — but *exactly* on the boundary, zero margin |
| 0.18 | 84.6 | 72.2 | +17% |
| 0.25 | 91.6 | 78.9 | +16% |

1. **It buys nothing in the regime that motivated the investigation.** Zoomed
   out with 300 cards in view, promotion stays off and the framerate is
   unchanged. The 87 fps at low zoom was never real — it was fast *because* it
   was not drawing.
2. **The only large gain sits exactly on the failure boundary.** Taking the
   +93% at 0.12 means shipping with no safety margin. Backing off to a safe
   margin leaves ~17%.
3. **It reintroduces a silent failure** whose mechanism is still not proven,
   guarded by a threshold fitted to three viewport sizes on one graph. The
   failure mode is a blank canvas, and fps cannot detect it.

17% is not worth a heuristic that fails silently and invisibly. **Low-zoom
performance has to come from doing less work (the paint-property node count),
not from promotion.**

⚠ **Caveat on the mechanism.** "Constant in layer-local px" holds at a fixed
viewport, but the constant itself is not universal: the band was 8954 local px
at a 799x435 canvas against 4143 at 1199x735 — a *smaller* viewport gave a
*larger* band. So the geometric finding rules memory out, but does not amount to
a working model of Blink's cull rect. Do not build anything that assumes one.

### `lod_enabled` is off ON PURPOSE — do not propose it as a free win (2026-09-03)

Several sections below note that `editor.pan_zoom.lod_enabled` is `false` and
treat re-enabling it as an untried, no-code lever. **It is not.** It is off by
an explicit decision: the LOD *transition* freezes for ~500 ms as layers are
admitted or hidden, so zooming becomes jerky. The stutter is more annoying than
the steady-state framerate it buys.

That matches the June-2026 finding recorded in the project notes — converting
LOD from `opacity: 0` to real `display: none` regressed node selection to ~5 s
and was reverted, because **the cost is transitioning detail in and out across
many nodes at once, not rendering it**.

So the LOD lever is not "switch it on"; it is "make the crossing cheap", which
is a different and much larger piece of work. Any measurement taken at
LOD `high` on this graph is measuring the configuration the app is actually
used in.

### FIXED — zoom jumped mid-pan: wheel/trackpad misclassification (2026-09-03)

Not a perf bug, but it lives in `pan.vue` and it corrupts every hand-panned
measurement in this file, so it belongs here.

`handleWheel` decided mouse-wheel-vs-trackpad **per event**, on
`|deltaY| >= 50 && deltaX === 0`. The middle of a fast vertical trackpad swipe
satisfies both, so fast pans flipped into zoom mid-gesture:

| gesture | zoom before → after |
|---|---|
| fast swipe down (pan to bottom) | 0.30 → **0.02** |
| fast swipe up (pan to top) | 0.30 → **2.96** |

Slow swipes (`|deltaY| < 50`) and diagonal swipes (`deltaX != 0`) were always
fine, which is how it survived: only the fast straight-line case broke.

Fixed by classifying the **first event of a gesture** and latching that until
the stream goes quiet — a trackpad swipe ramps up from small deltas, a wheel
notch opens at full magnitude. `wheelcheck.py` covers it (6/6), asserting both
that a swipe does not zoom **and** that it still pans, since a handler that does
nothing would pass the first half alone.

**Consequence for this file: any `hand` row taken with a fast vertical trackpad
sweep may have been silently zooming.** `pan px` would not reveal it — a zoom
also moves the pan values. Another reason the `auto40` rows supersede them.

### SOLVED — cards not rendering was `will-change` promotion, NOT the framerate (2026-09-03)

**Two separate Chrome bugs, and fps could only see one of them.**

Promoted by `will-change: transform`, Chrome stops painting the layer once the
content in view gets large. Counting cards that actually carry pixels
(`paintcheck.py`, which walks every card's client rect and asks whether that
rectangle has any internal contrast):

| zoom | cards in view | never painted, promoted | unpromoted |
|---|---|---|---|
| 0.069 (fit) | 300 | **152** | 0 |
| 0.09 | 208 | **53** | 0 |
| 0.15 | 62 | 0 | 0 |

It is a hard horizontal cut, not a flicker — everything below a fixed line is
absent, **at rest, indefinitely**. That is the reported "only sections of the
nodes render, sometimes only half of them". Removed `will-change: transform`
from `.zoom-pan-content` in `zoom/pan.vue`.

**Cost: Chrome 87 → 38 fps at zoom 0.09. Deliberate.** A correct 38 fps beats a
fast half-drawn canvas. Everything paints at rest *and* mid-pan, at every zoom
tested (0.05 / 0.069 / 0.09 / 0.15).

**Firefox is unaffected, A/B'd in one session:** 19.08 fps unpromoted vs 19.07
promoted, spreads fully overlapping, and 278/278 cards painted either way.
Neither Chrome fix costs Firefox anything.

#### ⚠ Why this was missed for so long, including once in this file

The comment in `pan.vue` used to read *"will-change: transform is KEPT —
removing promotion was tested separately, made no difference in Firefox, and
trended worse in Chrome."* That was true, and it was decided **on framerate
alone**. Framerate is blind to this failure: the blank region costs nothing to
not-draw, so dropping half the canvas makes the number go **up**.

The same mistake was repeated here on 2026-09-03: the `scale3d` fix below was
reported as having resolved the rendering symptom, on the strength of a
before/after screenshot pair. It had not. It fixed the *unpainted app shell*
(genuine raster starvation, caused by 500 ms main-thread stalls); the blank
**node** regions are this separate bug and survived it untouched — confirmed by
restoring `scale3d` via CSS and measuring 49.7% blank against 50.7% with the
fix in place. Eyeballing one screenshot is not a measurement.

**Rule: any change to compositing, promotion or layer structure must be checked
with `paintcheck.py`, not only `panperf.py`.** An fps run cannot see a
paint-completeness regression, and will usually reward one.

### SOLVED — the Chrome framerate cliff was `scale3d` on a widget pseudo-element (2026-09-03)

**`6.05 → 87.19 fps` in Chrome. One CSS token.**

`.number-drag::after` — the focus underline on every number widget — animated
with `transform: scale3d(0, 1, 1)`. Changed to the 2D `scaleX(0)`
(`number/drag.vue`). The animation is identical; it only ever scaled on X.

| | fps | mean ms | p99 ms | main ms | Layerize |
|---|---|---|---|---|---|
| before | 6.05 | 165.31 | 525.0 | 159.40 | ~500 ms × 27 per 5 s |
| after | **87.19** | **11.47** | **25.6** | **7.28** | ~4 ms × 465 per 5 s |

**Why it costs so much.** A 3D transform gives the element its own transform
node in Blink's paint property tree and blocks the paint-chunk merging that
`PaintArtifactCompositor::Update` — `Layerize` in a trace — depends on. One
widget costs nothing. `10x300nodes.haywire` has 300 nodes × 11 number widgets =
**3300 of them**, and at that count Layerize went to ~500 ms per call, 86.5% of
the main thread. The compositor was then too starved to raster tiles in time,
which is the reported *"not all node cards are rendered, strong flickering"* —
reproducible on demand — no screenshot is committed, because the harness can
inject either bug back in one command:

```sh
# the shell going unpainted (this bug)
uv run python .scratch/pan-perf/panperf.py --runs 1 --shots /tmp/shots \
    --css '.number-drag::after { transform: scale3d(0,1,1) !important; }'

# the blank node regions (the will-change bug above)
uv run python .scratch/pan-perf/paintcheck.py --zoom 0.069 \
    --css '.zoom-pan-content { will-change: transform !important; }'
```

**Scope:** the `--shots` pair shows the *app shell* (top bar, tabs, sidebar)
going unpainted and coming back. It does **not** show the blank node regions
being fixed — that is the separate `will-change` bug, and it survived this fix
untouched. Do not read those shots as evidence for anything but the shell.

**Firefox is unaffected, measured both ways:** 18.94 fps with the fix, 18.99
with `scale3d` injected back. WebRender has no Layerize step, which is exactly
why this was Chrome-only and why the Firefox work never touched it.

**The main-thread verdict for this graph is now settled and inverted from the
200-node file below.** `main ms` 159.4 of a 165.3 ms frame — 96%, not 4%. Every
"the main thread is idle, build a compositor-side branch" conclusion further
down this file is scoped to `10x200nodes.haywire` and does not transfer.

#### The bisect, in order

Each row is the median of 3 automated runs, Chrome, zoom 0.090, LOD high,
`auto40`. Baseline 6.05 fps.

| probe | fps | reading |
|---|---|---|
| baseline | 6.05 | — |
| `--silence-console` | 6.06 | console/devtools cost is **not** a factor |
| `[data-node-id] { z-index: auto }` | 6.01 | 7500 stacking contexts are **not** it |
| `.hw-detail-label { display: none }` | 6.13 | labels are not it |
| `.number-drag { overflow: visible }` | 6.11 | 13.8k clip nodes are not it |
| `.number-drag * { transition: none }` | 6.28 | transitions are not it |
| `.number-drag__arrow { opacity: 1 }` | 6.72 | 6600 opacity effect nodes: +11%, marginal |
| `.number-drag__arrow { display: none }` | 6.98 | widget children are not it |
| `.number-drag__center { display: none }` | 7.06 | widget children are not it |
| `.connection-pin { display: none }` | 2.16 | **worse** — removing pins reflows the grid |
| `[data-node-id] > * { display: none }` | 119.60 | the cost is card **contents**, not the box |
| `.widget-container { display: none }` | 117.78 | …and specifically the number widgets |
| `.widget-container { visibility: hidden }` | 113.58 | …paid at **paint**, not at layout |
| **`.number-drag::after { display: none }`** | **89.85** | the pseudo-element alone |
| **`.number-drag::after { transform: scaleX(0) }`** | **82.20** | **the 3D transform alone** |
| fix at source | 87.19 | confirmed after `studioctl restart` |

The two `display: none` probes contradicting each other individually
(`arrows` 6.98, `center` 7.06, both hidden = the whole widget = 117) is the tell
that led here: the cost was not in any child, it was in the container's own
paint — and the container's only paint is that pseudo-element.

**Still on the table**, now that the cliff is gone: Layerize is still 61% of a
(much smaller) main-thread budget at ~4 ms per call, and `canvas.vue:3389` puts
`translateZ(0)` on `.dragging-node` — harmless at one element, the same
anti-pattern at scale.

### The protocol is now automated — hand runs are superseded (2026-09-03)

Everything above was gathered by hand, and the section below correctly concluded
that at this scale a hand run resolves nothing (5.85–11.31 fps on identical
code). **`.scratch/pan-perf/` now drives the whole protocol** — login, graph
load, settle, zoom, record, read-back — against real Chrome or Firefox with
nothing left to the operator. Three runs of identical code land inside ~6%.

```sh
uv run python .scratch/pan-perf/panperf.py --runs 3
uv run python .scratch/pan-perf/panperf.py --runs 3 --css '<hypothesis>'   # A/B, no restart
uv run python .scratch/pan-perf/panperf.py --runs 1 --trace /tmp/t.json    # what it is doing
```

See `.scratch/pan-perf/README.md`. The one rule it cannot enforce for you:
**restart the studio after editing a `.vue`** — they compile at import.

`--css` is what made the bisect above possible at all: a hypothesis costs ~70
seconds and no source edit, so twelve of them fit in the time one hand-measured
branch used to take.

### 300 nodes x 20 ports is a DIFFERENT REGIME — and hand-panning cannot measure it (2026-09-02)

New graph: `graphs/10x300nodes.haywire`, 300 nodes, **10 inlets/widgets + 10
outlets each**, 0 edges. Everything below this section was measured on
`10x200nodes.haywire`, whose collapsed cards carry **zero** pins. The two are
not the same workload and the older conclusions do not transfer.

| | fps | main ms | mean frame | reading |
|---|---|---|---|---|
| ff baseline | 12.14 | 237.65 | 82.38 | main >> frame |
| cr baseline | 1.67 | 543.68 | 597.22 | **91% main-thread** |

**The main-thread verdict inverts.** At 200 nodes main-thread was 4-5% of the
frame and the file concluded "even eliminating main-thread work entirely buys
4%". At 300x20 it is **91% in Chrome**, with LoAF reporting 11 frames /
5880 ms inside a 5 s window. Chrome — which was 1.8x *faster* than Firefox at
200 nodes — is now 7x *slower*. That is a cliff, not a curve.

`els` was 419 on the 1.67 fps Chrome run. The DOM is small; the per-frame work
over it is not. Whatever this is, it is not element count.

**Two branches tested and reverted, neither on trustworthy evidence:**

1. **`perf/restore-preserve3d`** — restored the strongest of the five flattened
   3D hints, inside the existing `@media (-webkit-min-device-pixel-ratio: 0)`
   block, on the theory that Chrome's cliff was the lost compositing promotion.
   **Firefox 12.14 → 3.12/2.40 fps. Chrome unmoved.** Two findings: the
   compositing-recovery line is dead (so `translateZ(0)` and `image-rendering`
   are no longer indicated either), and — importantly — **that media query is
   NOT a browser gate.** Modern Firefox matches `-webkit-min-device-pixel-ratio`.
   Anything living in that block reaches both engines.
2. **`perf/zoomstate-nonreactive`** — `canvas.vue` writes `this.zoomState` (a
   reactive `data()` field) on every pan frame, while all 5 readers are
   coordinate maths inside event handlers; no template binding, no computed, no
   watcher observes it. Making it a plain instance field is a real removal of
   per-frame reactivity work. **Result: unresolved — see below.** Reverted
   because it could not be shown to help, not because it was shown not to.

### ⚠ Hand-panned single runs cannot resolve anything at this scale

Five runs of `perf/zoomstate-nonreactive`, identical code:

| fps | main ms | els |
|---|---|---|
| 11.31 | 185.16 | 2755 |
| 9.09 | 269.29 | 2435 |
| 6.74 | 310.46 | 2315 |
| 9.15 | 284.93 | 2687 |
| 5.85 | 311.07 | 2290 |

**5.85–11.31 fps — a 1.9x spread with nothing changing between runs**, against a
single-run baseline of 12.14. The within-branch variance exceeds any effect
worth chasing, so no single-run comparison in this regime means anything, in
either direction. `els` drifting 2290–2755 on a fixed graph says the census is
sampling different scene states too.

The cause is the one the Protocol section already flagged and never fixed: **pan
distance is not a controlled input.** A hand gesture cannot repeat itself, and
`pan px` is the dominant term in how much work a frame does.

**Fix: the recorder now drives the pan itself** (`auto-pan` button, default on).
A triangle-wave sweep of `autoPanPxPerFrame` (40) px per *frame* — per frame,
not per ms, so a 2 fps engine and a 60 fps engine are handed identical work per
frame and `pan px` reduces to frames x speed. Rows now carry a `pan` column
(`auto40` / `hand`).

**Every row above this section is a `hand` row and is not comparable to an
`auto` row.** Re-baseline both engines with auto-pan before testing anything
else.

### Chrome confirms the main-thread verdict; the Chrome comparison is still open

Chrome @0.090, LOD `high`: median **23.68 fps / 42.23 ms mean / 50.1 ms p99**,
**`main ms` 2.14 — 5.1% of the frame.**

**Two engines now agree.** Firefox 2.7 ms of 67.7 (4.0%), Chrome 2.14 ms of
42.23 (5.1%). The main thread is not the bottleneck, measured directly in both,
with a calibrated instrument. That conclusion is settled.

**But no Chrome verdict is possible yet — there is still no Chrome baseline.**
The only other Chrome data is `perf/node-zindex-drop` at LOD `raw`, a different
branch *and* a different LOD. Whichever branch produced this set, the run that
resolves it is the *other* one, in Chrome, at 0.090 / LOD high.

**The two engines are not even running at the same refresh rate.** Chrome's p99
of 50.1 ms is exactly 3 × 16.67 ms (60 Hz); Firefox's 92.18 ms is 11 × 8.33 ms
(120 Hz). Frame *counts* are comparable across engines, but "worst frame in
vsyncs" is not — Chrome is dropping to every 3rd refresh, Firefox to every 11th.

**`pan px` is not a controlled input.** Across six Chrome runs it spans
1977–7636, a 3.9× range, and it correlates *positively* with fps — the 34.4 fps
run had by far the most travel. It is partly an output: more frames rendered
means more wheel deltas applied and more accumulated travel. Keep it as the
"did the content actually move" check it was added for; do not read it as
workload.

### `perf/flatten-3d` — MERGE, and the main-thread question is finally answered

Firefox, zoom 0.090, LOD `high` — directly comparable to the baseline runs at
the same zoom and LOD.

| | fps | mean | p99 | spread |
|---|---|---|---|---|
| baseline | 12.37 | 80.81 | 150.10 | 12.28–13.13 |
| `perf/flatten-3d` | **14.78** | **67.67** | **92.18** | 14.43–15.22 |

**+19.5% fps, −38.6% p99, and the two spreads do not overlap** — baseline's best
run (13.13) is below flatten-3d's worst (14.43). This is the first change in the
whole investigation that moved the number.

Removing five 3D compositing hints — `translateZ(0)`, `backface-visibility`,
`-webkit-perspective`, `preserve-3d`, and the `matrix3d` branch below zoom 0.5 —
was worth a fifth of the framerate and cut worst-case frames by nearly 40%.

**`main ms` = 2.7 of a 67.7 ms frame. 4%.**

That is the answer to the question this investigation kept failing to ask
properly. The main thread does 2.7 ms of work per frame; the other 96% is spent
elsewhere — raster, GPU, compositing, vsync. Measured directly, in the engine
that shows the symptom, with an instrument calibrated against a known
12 ms/frame load (it reported 12.06).

The earlier LoAF argument reached the same conclusion through a broken
instrument and was rightly retracted. **The conclusion now stands on a working
one.** The five main-thread JS branches are dead:

- `perf/pan-hover-gate`, `perf/pan-raf-coalesce`, `perf/minimap-color-cache`,
  `perf/edge-node-index`, `perf/hot-path-logs` — all optimise a thread that is
  idle 96% of the frame. Even eliminating main-thread work entirely buys 4%.

> **SCOPE LIMIT (added 2026-09-02).** True for `10x200nodes.haywire` (0 edges,
> pinless collapsed cards) and nothing else. On `10x300nodes.haywire`
> (10 inlets + 10 outlets per node) the main thread runs **91% of the frame** in
> Chrome. These five branches are dead *for that graph*, not in general — see
> the 300x20 section at the top of Observations before citing this.

**Caveat on `stalls`:** it went *up* (63 → 74) while everything else improved.
It counts frames over 50 ms, so a run that renders more frames records more of
them. It is confounded by frame count and should not be read as a regression.

**Still 14.78 fps.** flatten-3d is a real win but not the whole story; the
remaining 96% is still off-thread. Next candidates, all compositor-side:

1. **flatten-3d in Chrome — required before merging.** It removes hints written
   *for* Chrome. It must not regress the engine they were aimed at.
2. `will-change: transform` is still on the layer. Dropping promotion entirely
   is the next isolated probe.
3. Card chrome (border, radius, shadow, background) flattened at low zoom — the
   per-visible-node raster cost that collapse and LOD both failed to touch.

### Chrome is 1.8x faster than Firefox — but both are bad (2026-08-31)

`perf/node-zindex-drop`, LOD `raw`, same graph and protocol:

| | fps | mean | p99 | stalls |
|---|---|---|---|---|
| Chrome @0.090 | 25.12 | 39.81 | 50 | 2 |
| Firefox @0.084 | 12.08 | 82.79 | 175 | 55 |
| Firefox adjusted to 0.090 | 13.87 | | | |

**Chrome 1.81x the framerate, 3.5x lower p99, and 2 stalls against 55.** So a
large part of what was being measured all along is Firefox-specific — and every
compositing hint on `.zoom-pan-content` is Chrome-flavoured (`translateZ(0)`,
`-webkit-perspective`, `-webkit-transform-style`), with the `matrix3d` branch
below zoom 0.5 added because "Chrome handles it better". Those may be actively
hurting Firefox. That makes `perf/flatten-3d` the indicated probe again, this
time on evidence rather than on the retracted LoAF argument.

**But 25 fps is still bad**, so there is a shared cause underneath the
Firefox-specific multiplier. Two separate problems, not one.

**LoAF still cannot answer the main-thread question, even in Chrome.** It
reports only frames of 50ms or more; Chrome's frames here average ~40ms, just
under the threshold, and its p99 sits exactly on it. So `LoAF 0-2` is a
threshold artefact, not evidence of an idle main thread. Do not repeat the
Firefox mistake in a subtler form.

Hence the new **`main ms`** column: a MessageChannel task posted from inside the
rAF callback fires only after the browser has finished that frame's rendering
update, so the delay measures main-thread per-frame work directly, in any
engine, with no threshold. Calibrated against a deliberate 12ms/frame burn: it
reported 12.06ms of a 12.08ms frame.

Read it as: `main ≈ frame` → main-thread bound, build the JS/CSS branches.
`main << frame` → the frame is waiting on raster, GPU or vsync instead.

### ⚠ RETRACTED — every LoAF and longtask number so far is void (Firefox)

**The runs were taken in Firefox. Firefox supports neither `longtask` nor
`long-animation-frame`.**

The capability check was a `try/catch` around `observe()`. But
`observe({type})` with an unsupported type does **not** throw — per the
Performance Timeline spec it aborts quietly, with a console warning at most. So
the flag reported `lt-obs: yes` on a browser that had silently registered
nothing, and both counters then read a clean, entirely fictional zero.

Which means the central conclusion — *"LoAF = 0 at 80 ms frames, therefore the
main thread is idle, therefore the cost is off-thread"* — was reading an
instrument that was never connected. **It is withdrawn.** So is everything built
on it:

- The four JS branches are **NOT** killed. `perf/pan-hover-gate`,
  `perf/pan-raf-coalesce`, `perf/minimap-color-cache` and `perf/hot-path-logs`
  go back to untested.
- `perf/flatten-3d` was built on the raster-scale reasoning that followed. It is
  still a reasonable probe, but it is no longer the *indicated* one.

**What survives, because it does not depend on those APIs:** fps, frame times,
stalls, `pan px`, zoom and LOD are all rAF- and DOM-derived and engine-agnostic.
So these still stand:

- collapse does not help (the original symptom)
- LOD on/off does not help, +7.5% zoom-adjusted
- `perf/node-zindex-drop` does not help, +4.3%, inside noise
- cost scales roughly as 1/zoom²

Fixed by checking `PerformanceObserver.supportedEntryTypes` instead of relying
on a throw. Rows now also carry an **engine** column (`ff` / `cr`), because a
Firefox row and a Chrome row are not the same measurement and must not be
compared column-for-column.

### Turning LOD back on changes nothing — and that is a finding

`perf/measure-window`, zoom 0.084, LOD `raw`: median **11.58 fps / 86.35 ms mean
/ 175.62 ms p99**, pan travel 4695–5716 px.

Against the LOD-`high` runs at zoom 0.090 (12.37 fps), adjusted for the extra
content in view at the lower zoom — (0.090/0.084)² = 1.148×, so 10.78 fps
expected if LOD did nothing — the observed 11.58 is **+7.5%**, well inside the
spread of the LOD-`raw` set itself (11.32–17.37).

**LOD is not a lever on a collapsed graph, because collapse already removed
everything LOD hides.** The two mitigations are redundant with each other, and
neither touches the cost. That squares with the earlier session's "box-only ~4×"
note: that gain came from hiding widgets and labels, which a collapsed card does
not have in the first place.

So, ruled out by measurement so far: card **contents** (collapse), **detail
layers** (LOD), and **main-thread work** (LoAF). What is left is the card box
itself — ~200 plain rounded rectangles — costing 80 ms/frame off-thread. That is
absurdly expensive for the drawing involved, which points at raster *scale* or
layer *size* rather than raster complexity.

### Provenance correction (2026-08-31)

Nothing has been measured on `perf/node-zindex-drop`. An earlier attribution of
the first three runs to that branch was wrong — almost certainly because the git
tree was checked out to one branch while the running studio had been started
from another. **Do not check out branches while a measurement session is live.**

Those first six runs are marked superseded regardless: they predate `pan px` and
`LoAF`, so neither their provenance nor their validity can be recovered. The
zoom-0.09 and zoom-0.084 sets are the only trustworthy data.

### DECISIVE — zoom 0.09, 3 runs (2026-08-31)

Median **12.37 fps / 80.81 ms mean / 150.1 ms p99**, 62–66 stalls per 5 s,
pan travel 5313–7455 px.

**The pan is real.** 5–7 k px of travel over 5 s. The clamp worry is dead, and
these runs measure actual panning.

**The main thread is idle. LoAF = 0 across every run, with `loafObs` reporting
supported.** LoAF fires on any animation frame whose main-thread work reaches
50 ms. These frames average 80 ms and hit 150 ms at p99. If the main thread were
doing that work, LoAF would fire on nearly every frame. It fires on none.

So the frame time is **off the main thread** — compositor, raster, GPU. Unlike
the retracted `longtask` argument in §2 below, this is the right instrument for
the claim.

**Four branches are dead on this evidence** — all of them main-thread JS, which
LoAF proves is not where the time goes:

- `perf/pan-hover-gate` — handlers and restyle would appear as LoAF script/s+l
- `perf/minimap-color-cache` — a forced style flush happens inside a script task
- `perf/edge-node-index` — JS
- `perf/hot-path-logs` — JS

**Cost scales with visible node count.** 26.07 fps at zoom 0.15 → 12.37 at 0.09.
Content area in view goes as 1/zoom²: (0.15/0.09)² = 2.78 against an fps ratio of
2.1. Close enough to say the cost is roughly **per visible node, per frame**,
paid off-thread. That is the signature of **raster** — as the viewport moves,
newly exposed tiles must be rastered, and at lower zoom a single tile covers far
more nodes.

It also explains why collapse did not help: a collapsed card keeps its full
chrome (border, radius, shadow, background). If raster of the card chrome is the
cost, removing the card's *contents* changes nothing.

**`lod_enabled` is OFF.** That is why LOD reads `high` at zoom 0.09 when
`_lodLevelFor` says `raw`. The setting defaults to **True**, and its own
description calls it a diagnostic toggle for isolating LOD stutter — so it was
turned off during some earlier investigation and left off. **Every run so far has
been taken with the shipped mitigation disabled.** At `raw` the LOD rules
`display: none` everything but the card box, which an earlier session measured at
roughly 4× on the box-only case.

Next actions, in order:

1. **Turn `lod_enabled` back on and re-run.** No branch, no code. If fps jumps,
   the pan problem is substantially "LOD is switched off".
2. Confirm `grid_enabled` — it defaults to False, so there should be no
   background image to raster, but if it was switched on the 12000×11000 tiled
   data-URI is a raster cost worth removing at low zoom.
3. Only then build a raster-side branch. The candidate is card chrome
   (`box-shadow` / gradients / `border-radius` flattened at low zoom), not
   anything on the main thread.

Anything the numbers do not capture — visual regressions, a branch that felt
different from what it measured, a hypothesis the data killed.

### `perf/node-zindex-drop`, 3 runs (2026-08-31)

Median **26.07 fps / 38.36 ms mean / 82.56 ms p99**, 16–24 stalls per 5s.

**No baseline yet, so nothing can be said about the probe itself.** These are
the first numbers taken, and they are from the branch with the stacking contexts
already removed. Everything below is about the *scene*, not about whether the
probe helped.

What the baseline will decide, once run:

- **Baseline ≈ 26 fps too** → the paint-chunk hypothesis is dead. 200 stacking
  contexts were not the cost, and the off-main-thread time (see 2) belongs to
  something else: rastering the 8000×8000 dot background, the full-canvas
  connection SVG, or layer memory.
- **Baseline much worse** → the probe won, and the shipping question (pins
  escaping the container, see the branch note) becomes worth solving.

**1. Frame times are exact multiples of a 120 Hz display frame.** 8.33 ms is one
refresh, and the numbers land on 74.98 = 9×, 83.32 = 10×, 91.68 = 11×,
108.4 = 13×, 66.34 = 8×. The mean of 38.36 ms is ~4.6×. So this is not a renderer
running slightly late — it is missing 4 to 12 consecutive vsyncs per presented
frame. Work per frame is 35–40 ms against a 8.33 ms budget.

**2. ~~Zero long tasks proves the main thread is idle.~~ WRONG — retracted.**

The observation is real (0 long tasks against 16–24 stalls, and `lt-obs: yes`
confirms the observer was running). The inference drawn from it was not.

`longtask` attributes the *script* portion of a task. Style, layout and paint
inside the frame update go largely unreported — which is exactly why the
`long-animation-frame` API was added afterwards. So 80 ms frames with no long
tasks is equally consistent with main-thread **rendering**, and says nothing
about compositor versus main thread.

Nothing was ranked on this. The recorder now observes LoAF and reports
`LoAF (ms)` and its `style+layout` share per run, which does settle it:

- **LoAF ≈ 0 while frames are 75–85 ms** → genuinely off the main thread.
  Compositor / raster / GPU. The four JS branches are pointless.
- **LoAF accounts for most of the frame, mostly `s+l`** → main-thread style and
  layout. The CSS-side candidates (hover churn, LOD restyle) are live.
- **LoAF significant but mostly script** → main-thread JS after all, and the
  minimap / edge-sweep / hover-handler branches are live.

LoAF only reports frames ≥ 50 ms, which is below the frames of interest, so
silence here is a finding rather than a sampling gap.

**3. LOD is `high` at zoom 0.150, where it should be `raw`.** `_lodLevelFor`
returns `raw` at ≤ 0.3, so `high` means `lod_enabled` is **off** in
EditorPanZoomSettings. Consequences:

- Nothing is `display: none`, so the `hw-lod-hover` re-admission cost — a chunk
  of the hover hypothesis — is not in play at all. Only the `:hover`
  stacking-context churn and the edge-map sweeps remain of it.
- Every node draws full detail at every zoom. The collapse is still doing its
  job, but this is a heavier scene than the protocol assumed.

This is not wrong to measure — it is the setting the symptom was reported
under — but it must stay **identical across every branch**. Do not toggle
`lod_enabled` mid-experiment.

**4. Rows came through as `(unset)`.** Set `window.__hwPerfBranch` in the console
after each checkout, or the rows stop being self-describing once there are five
branches in the table. The countdown now warns when it is unset.

### Second set of 3 runs — branch unconfirmed

Median 26.76 fps / 75.32 ms p99, against the z-index set's 26.07 / 82.56.

**A 0.69 fps difference between the sets, against a 9.7 fps spread within one of
them.** Whatever these two sets are, they are indistinguishable. If the second
set is the baseline, the paint-chunk hypothesis is dead as tested and
`perf/node-zindex-drop` is a drop.

The 36 fps outlier is the protocol's known weak point: pan speed and distance
are not pinned down, so a slower or shorter sweep reads as a faster renderer.
Hence the new `pan px` column.

**5. Pan may be clamped to nothing at the test zoom.** `_clampPanValues`
*centers* an axis whose scaled canvas is smaller than the viewport and refuses
to move it. Nodes span x 338..11609, y 1970..10943, so the canvas is auto-grown
past its 8000 default and the exact clamp cannot be worked out on paper — but at
zoom 0.09 the whole canvas is roughly 1000 px on screen, which is narrower than
a typical window. A vigorous trackpad sweep may then move the transform by zero
pixels, and a run that measured a static transform is not measuring panning at
all.

`pan px` (Manhattan path length over the window) settles it, and the HUD flags
`⚠ BARELY MOVED` under 200 px. **If it fires, every number above is measuring
the wrong thing** and the target zoom has to come back up until the content
actually moves.

### `image-rendering: optimizeSpeed` re-measurement, post-flatten-3d (2026-09-02)

One run each, `graphs/10x200nodes.haywire`, zoom 0.090, LOD off, Firefox — not
the full 3-run protocol, so treat this as directional rather than decisive.

| scenario | fps | mean ms | p95 ms | p99 ms | max ms | stalls | main ms | pan px |
|---|---|---|---|---|---|---|---|---|
| with `image-rendering`, pins linked only | 33 | 30.3 | 41.68 | 42.54 | 50 | 0 | 28.25 | 3637 |
| with `image-rendering`, full | 15.49 | 64.54 | 75.9 | 150 | 150 | 78 | 249.11 | 3245 |
| without `image-rendering`, pins linked only | 31.2 | 32.05 | 42.38 | 58.34 | 66.66 | 3 | 24.14 | 2092 |
| without `image-rendering`, full | 18.51 | 54.03 | 75 | 100 | 100 | 54 | 59.94 | 2264 |

**FULL detail: removing the rule looks better** — 15.49 → 18.51 fps (+19.5%),
p99 150 → 100 ms, pan px close enough (3245 vs 2264) that the comparison is not
obviously confounded by a shorter sweep.

**Pins-linked-only: removing the rule looks worse** — 33 → 31.2 fps (−5.5%) —
but `pan px` differs by 42% (3637 vs 2092), which the protocol's own guidance
(§5, "pan px is not a controlled input... it only answers did the content
move") flags as exactly the confound that invalidates a direct fps comparison
here. This pair is inconclusive, not evidence the rule helps.

**Verdict: no regression from removing it, and a directional gain at FULL** —
the rank where the card actually has enough raster content (labels, widgets)
for a downscale filter choice to matter. One run per cell is thin evidence by
this protocol's own "3 runs, judge on median" standard, but nothing here
supports keeping the rule, and the FULL-detail result (the less confounded
pair) points the other way. Removed from `pan.vue`.
