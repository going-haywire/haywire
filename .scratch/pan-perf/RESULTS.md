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
