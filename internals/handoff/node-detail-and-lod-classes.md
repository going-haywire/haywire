---
name: node-detail-and-lod-classes
description: Handoff — two open design decisions on node detail and the LOD classes, with the measurements that constrain them; the pan performance work they came out of is landed
metadata:
  type: project
  status: open
---

# Node detail and the LOD classes: two decisions to make

The zoomed-out pan problem is **solved and landed**. What is left is a design
question it uncovered: `NodeDetail` is a construction gate, and it measured
3.07x on pan — but the cheap fix (make it a CSS filter) changes what the rank
*means*, not just what it costs.

This file is the brief for that design session. Numbers here are from
`.scratch/pan-perf/RESULTS.md`, which holds the full run table and protocol.

---

## Decision A — should `NodeDetail` become a CSS filter?

Today `NodeDetail` is a **construction gate**: at COMPACT a skin does not build
what the rank excludes. `enums.py` says so explicitly — *"a construction gate,
not a CSS one"* — and names that as what separates it from the zoom-driven LOD
system (ADR-0006), which only decides what is *painted* of what already exists.

**The performance case is proven.** Three variants of the same visible result,
Firefox, flat cards, LOD off:

| variant | pan fps | sweep fps |
|---|---|---|
| FULL built | 18.64 | 72.32 |
| COMPACT built | 57.20 | 99.35 |
| **FULL + CSS-hidden** | **56.11** | **101.43** |

CSS-hidden lands at **0.98x / 1.02x of constructed COMPACT** — indistinguishable
— and 3.01x / 1.40x over constructed FULL. `display: none` takes elements out of
layout and paint, which is where the cost was. The DOM residue costs nothing per
frame, **including NiceGUI's per-element VNode rebuild**, which was the specific
risk that run existed to test.

The payoff: a detail change becomes a class flip (~1s for 200 nodes, and
**staggerable** — 20 nodes/frame turns one freeze into ~20 imperceptible frames)
instead of a server re-render (~5s).

**What the measurement does NOT settle, and why this is a design question.**

1. **COMPACT would stop meaning "these widgets do not exist."** As a CSS filter
   they exist, hold state, and take binding traffic while invisible. That is a
   decision about what the rank *means*. No measurement is pending on it.
2. **Non-per-frame costs are untested.** An earlier session measured node
   selection latency at multi-second on 200 nodes, and app-wide sluggishness
   from NiceGUI's full-tree render walk. Those are not per-frame costs, and the
   table above is per-frame. A CSS-filtered COMPACT graph keeps FULL's element
   count, so that risk is **unchanged and unmeasured**.
3. It reverses documented intent in `enums.py:187-189` and touches ADR-0032.
   Deliberate if chosen, but ADR-shaped.

**Gate before building: select a node on a 200-node FULL graph and see if it is
still slow.** One manual measurement, still unrun. If it is slow, construction
gating may still earn its place — for a different reason than the one the pan
work eliminated.

**The mapping, if it proceeds** (from
`packages/haywire-core/src/haywire/ui/skin/visibility.py`): COMPACT drops
exactly three things — port **labels** (FULL), inline **widgets** (STANDARD+),
and inline **diagnostics detail** (FULL). The diagnostics BADGE is drawn at
every rank and must stay. The **port set is identical at both ranks**; detail
changes what is drawn per port, not which ports exist. Labels and widgets both
already carry `zoom-pan-lod2`, so one selector covers exactly what COMPACT
omits. A working rule is on `perf/detail-via-css`.

---

## Decision B — what happens to the LOD classes?

**LOD's zoom coupling is a net loss.** Full 6-cell matrix, Firefox:

| mode | LOD | detail | fps | p99 |
|---|---|---|---|---|
| sweep | on | all | 24.71 | **566 ms** |
| sweep | off | all | 53.24 | 167 ms |
| sweep | on | none | 68.60 | 83 ms |
| sweep | off | none | 68.57 | 91 ms |
| pan | on | none | 10.80 | 134 ms |
| pan | on | all | 10.82 | 117 ms |

- **Crossings cost 2.15x**, and p99 566ms is a visible half-second freeze mid-zoom.
- **The collapsed sweep is the control and it is flat** (68.60 vs 68.57, 0.04%) —
  with nothing to hide, LOD costs nothing. So the 2.15x is the crossing itself,
  not a harness artefact.
- **LOD buys nothing during pan**: 10.80 vs 10.82 fps. Hiding every widget and
  label on 200 nodes changed the framerate by 0.2%.

A 2.15x penalty to buy a 0.2% gain. The mechanism: pan cost is card-chrome
raster, which LOD does not touch.

**Do not try to make crossings cheap.** Measured by hand: the CSS toggle for 200
nodes is ~1s, a re-render ~5s. Both are hangs. Three rounds of selector
optimisation are already recorded in `pan.vue`'s comment block (opacity ->
`display:none`, killing `var()` indirection, `:hover` -> JS class); each won an
order of magnitude and the crossing still costs 566ms. The remaining cost is
layout, not restyle.

**The open question:** what happens to `zoom-pan-lod0/1/2/3` and
`data-lod-level`. The cheap reading is *drop the `display:none` rules, keep the
attribute* — the attribute flip is free, and it is what any future zoom-tiered
paint-only change would hang off. Touches ADR-0006 and the skin-authoring
contract (`docs/components/skins/skin-canon.md`). Skins outside this repo do not
exist yet, so breaking that contract is acceptable.

**Decisions A and B belong in one session.** They touch the same selectors, the
same skin contract, and both ADR-0006 and ADR-0032.

---

## Constraints on whatever gets designed

**Ruled out, with numbers. Do not re-investigate:**

| Ruled out | By |
|---|---|
| Card contents | collapse — the original symptom |
| Detail layers via LOD | +7.5% zoom-adjusted, inside spread |
| Stacking contexts / paint chunks | `perf/node-zindex-drop`, +4.3%, noise |
| Layer promotion (`will-change`) | `perf/no-promotion`, overlapping spreads, worse in Chrome |
| All main-thread JS and style/layout | `main ms` 2-5% of the frame, both engines |
| Viewport culling by unmount | at the zoom where the symptom appears, nothing is off-screen |

**Do not build these** — all five optimise a thread that is 2-5% of the frame:
hover gating, rAF-coalescing the pan, caching the minimap's `getComputedStyle`
reads, indexing edges by node, and stripping hot-path `console` calls.

---

## If you need to measure

`debug_overlay.vue` has a fixed-window recorder (`record 5s`), a zoom `sweep`
mode, a `zoom` preset, and a clipboard-able markdown result row. Protocol is in
`.scratch/pan-perf/RESULTS.md`.

**Three instrument bugs were found by getting wrong answers. Do not reintroduce:**

1. **Capability detection must use `PerformanceObserver.supportedEntryTypes`,
   never a try/catch.** `observe({type})` with an unsupported type does *not*
   throw — per spec it aborts quietly. Firefox implements neither `longtask` nor
   `long-animation-frame`, so a try/catch reports "supported" while counting
   nothing, and the resulting clean zeros read as "the main thread is idle". Two
   conclusions were published and retracted on this.
2. **`main ms` discards samples that span frames.** A MessageChannel reply that
   lands a frame late measures the wait for the main thread, not one frame's
   work — and replies are delayed precisely when the thread is busy. A run once
   reported `main 269ms` against a 52ms frame. Cross-frame samples are dropped
   and counted in a `dropped` column; **a high drop count means `main ms` is a
   floor, not a measurement**, and floors with different drop counts cannot be
   compared to each other.
3. **`longtask` does not attribute rendering work** — that is why LoAF exists.
   And LoAF only reports frames >= 50ms, so it is blind to a 40ms frame. Neither
   can answer the main-thread question for this workload; `main ms` can.

**Reading the columns:**

- **`stalls` is confounded** — it counts frames over 50ms, so a *faster* build
  records *more* of them. It rose 63 -> 74 while everything else improved. Ignore it.
- **`pan px` is not a controlled input** — it spans 1977-7636 across runs and
  correlates *positively* with fps. It only answers "did the content move".
- Judge on **fps median with disjoint spreads**. Within-branch spread reached 52%
  of the median; that is how `node-zindex-drop` (+4.3%) was correctly called a
  drop and `flatten-3d` (+19.5%, disjoint) a merge.

**Known and unfixed: a warm-up effect.** A fresh page pans at under 20 fps; after
one or two sweeps the same pan is 2-3x faster, with nothing else changed. Cause
not diagnosed — likely raster/texture cache warming, possibly NiceGUI settling
traffic (the HUD's rolling `measure N/s` line distinguishes them: non-zero means
still settling). **The protocol has no warm-up step**, so early pan runs in the
existing table may be cold. It does not plausibly explain the large effects
(1.9x, 2.15x, 3.07x, all consistent across matched sets) but it is inside the
range of the small verdicts. **Add a discarded warm-up sweep after every page
load.**

---

## Already done — do not redo

The original symptom (a 200-node graph pans badly zoomed out even with every
node **collapsed**) had three independent causes, all in the card BOX rather
than its contents — which is why collapsing changed nothing. Two are landed on
`perf/flatten-3d-merge`; the third is decision A above.

| Cause | Effect | Where |
|---|---|---|
| `backdrop-filter: blur(10px)` hardcoded on every card | 1.90x pan | landed — now the `--hw-node-backdrop-blur` token |
| 3D compositing hints on the pan layer | +19.5% Firefox, free in Chrome | landed — removed from `.zoom-pan-content` |
| Detail rank (labels + widgets) | 3.07x pan | **open — decision A** |

Reasoning for both landed changes lives in the code comments, the commit
messages, `docs/components/themes/theme-canon.md` and
`docs/reference/design-guide.md`. Two things worth knowing without going there:

- **The blur is still on for the light theme, deliberately** — its `node_bg` is
  translucent so the blur is visible there, while the dark theme's opaque card
  made it invisible and pure cost. A theme opts out by setting `"none"`; there
  is no kill switch.
- **`image-rendering: optimizeSpeed` is still in `pan.vue`**, flagged in a
  comment. It looks like a leftover symptom of the raster problem that was
  removed, but the verified +19.5% was measured with it present, so it was left
  alone rather than riding an unmeasured change on a verified one. Worth its own
  measurement if someone is in there.

**Probe branches.** `perf/lod-sweep-instrument`, `perf/flat-cards-always`,
`perf/chrome-ladder` and `perf/detail-via-css` are probes, not merge candidates:
they use `!important` overrides against the ADR-0030 token cascade, and
`flat-cards-always` also removes the selection ring (a box-shadow) and hover
outlines. `perf/detail-via-css` carries the working rule for decision A and is
the only one likely to be useful. `perf/chrome-ladder`'s 8-step chrome ladder
was **built and never run** — it is spent as a diagnostic now that the pan
question is answered. **Delete all four once decision A lands.**

Related: `.insights/project_css_var_theme_silent_failures.md` (silent cascade
failures), `.insights/feedback_css_containment_node_floor.md` (node size floor),
`.scratch/pan-perf/RESULTS.md` (all runs and the protocol).
