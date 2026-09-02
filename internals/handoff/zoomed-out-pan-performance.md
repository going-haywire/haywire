---
name: zoomed-out-pan-performance
description: Handoff — zoomed-out pan on a 200-node graph was hardware-limited by three independent causes; two are now landed, the third (detail rank) is proven but needs design, and LOD's zoom coupling measured as a net loss
metadata:
  type: project
  status: open
---

# Zoomed-out pan performance: what was measured, what to build

Investigated 2026-08-31/09-01. The starting symptom: a 200-node graph with every
node **collapsed** still panned badly once zoomed out far enough to see nearly
all of them — even though a collapsed card is nearly empty.

Every number below is from `.scratch/pan-perf/RESULTS.md`, which holds the full
run table, the protocol, and the wrong turns. **Read this file first; go there
for detail.** You should not need the session transcript.

**Status, 2026-09-02.** Two of the three causes are landed on
`perf/flatten-3d-merge`. What is left is decision 3 (detail rank), which is
proven as a mechanism but needs design, and is gated on one unrun measurement.
Decisions 1 and 2's sections below record what was actually built, including
where it departed from the design sketched during the investigation.

---

## The headline

Collapse didn't help because **collapse removes the card's CONTENTS and leaves
every expensive thing about the BOX**. Three independent causes, all in the box:

| Cause | Effect | Status |
|---|---|---|
| `backdrop-filter: blur(10px)` hardcoded on every card | **1.90x pan** | **LANDED** |
| 3D compositing hints on the pan layer | **+19.5% Firefox**, free in Chrome | **LANDED** |
| Detail rank (labels + widgets) | **3.07x pan** | mechanism proven, needs design |

They stack. And separately: **LOD's zoom coupling is a net loss** — 2.15x slower
on the case it exists for, buying nothing.

---

## Branch to continue from

Decisions 1 and 2's causes are **landed on `perf/flatten-3d-merge`** (3 commits
off master): the 3D-hint removal, the instrument + `RESULTS.md`, and the
backdrop-blur token. Only decision 3 is left.

```
master
 └── perf/flatten-3d-merge      LANDED  (3D hints, instrument+docs, blur token)
 └── perf/flatten-3d            ab449c23  SUPERSEDED by the above
      └── perf/lod-sweep-instrument  c2eeb4b1  sweep mode + LOD matrix
           └── perf/flat-cards-always 5c5d1891  unscoped chrome probe + main-probe fix
                ├── perf/chrome-ladder  be803bcd  console-switchable chrome ladder
                └── perf/detail-via-css 0be88032  the CSS-filter proof (decision 3)
```

`perf/flatten-3d-merge` took three of `perf/flatten-3d`'s four commits. The
fourth — the fixture rewrite opening `graphs/10x200nodes.haywire` collapsed plus
a `haystacks/haystack.toml` that deletes three graphs from the haystack — is
workspace state and was left behind. The fix's comments were rewritten from
probe narration to shipped prose; the code is byte-identical to what was
measured.

Every remaining branch is a **probe**, not a merge candidate — they use
`!important` overrides against the ADR-0030 token cascade, and
`flat-cards-always` additionally removes the selection ring (drawn as a
box-shadow) and hover outlines. Read them for the rules and the reasoning; do
not ship them.

**These four probe branches are to be deleted once decision 3 lands.** They
were diagnostics for a problem that is now resolved; their only remaining value
is informing decision 3's implementation, if it turns out to need them.

**The chrome ladder was built and never run.** `perf/chrome-ladder` carries an
8-step console-switchable ladder (`document.documentElement.dataset.hwChrome =
'3'`) intended to split the card-chrome cost one property at a time, but
`RESULTS.md` holds no ladder rows. It is spent as a diagnostic — backdrop-filter
was 71% of the available chrome gain and is now handled on its own. Do not
re-run it to re-answer the pan question.

**Do not build these** — all five optimise a thread that is 2-5% of the frame:
hover gating, rAF-coalescing the pan, caching the minimap's `getComputedStyle`
reads, indexing edges by node, and stripping hot-path `console` calls.

---

## Decision 1 — `backdrop-filter` (LANDED)

**The finding.** All three skins hardcode `backdrop-filter: blur(10px)` into the
card style:

- `barn/haybale-studio/haybale_studio/skins/stacked_skin.py:62`
- `barn/haybale-studio/haybale_studio/skins/split_skin.py:72`
- `barn/haybale-studio/haybale_studio/skins/error_skin.py:99`

It is a 10px Gaussian blur of everything behind each card, recomputed per card
per frame — 200 backdrop blurs per frame. Worth **1.90x on pan** (34.68 -> 66.00
fps at zoom 0.241), **71% of all available chrome gain**, and it halves p99 from
50ms to 25ms.

It is also hardcoded rather than tokenised, so no theme or tier can override it —
which is itself the cascade anti-pattern `.insights/project_css_var_theme_silent_failures.md`
warns about.

**What was built** — this departs from the design sketched during the
investigation on four points, all decided with the user:

1. `node_backdrop_blur` -> `--hw-node-backdrop-blur` in
   `WorkbenchTheme._CSS_TOKEN_MAP`
   (`packages/haywire-core/src/haywire/ui/themes/workbench.py`). `BaseTheme`
   declares no values, so **the `none` default is the `var()` fallback in the
   skins**, not a base-class attribute.
2. **The shipped themes split rather than both keeping `blur(10px)`.** A
   backdrop blur behind an OPAQUE card is composited underneath it and cannot be
   seen — so on the dark theme (`node_bg = #1e1e2e`) the blur was paying full
   cost for zero visible pixels. Dark sets `"none"`, light
   (`rgba(255,255,255,0.3)`, genuinely translucent) keeps `"blur(10px)"`. Dark
   users get the 1.90x with **no visual change at all**; light is untouched.
   Both state their value explicitly so the asymmetry reads as deliberate.
3. **`error_skin` drops `backdrop-filter` entirely and does not read the token.**
   It hardcodes an opaque `var(--hw-warning)` background rather than
   `--hw-node-bg`, so a blur is unobservable there in *either* theme. Giving it
   the token would be a var that is set, accepted, and does nothing — the exact
   silent no-op `.insights/project_css_var_theme_silent_failures.md` catalogues.
   `stacked_skin` and `split_skin` read `var(--hw-node-backdrop-blur, none)`.
4. **No kill switch.** The token is the control surface: a theme sets `"none"`.
   The `[data-hw-no-backdrop]` + `!important` escape hatch and its
   `NodeSkinSettings` entry were dropped as unnecessary machinery once the
   default became "off unless a translucent theme asks".
5. Tested at the **theme layer** (`tests/studio/test_theme_backdrop_blur.py`, in
   the shape of `test_theme_active_tokens.py`): both shipped themes emit the
   token, dark is `none`, light is `blur(10px)`. That covers ADR-0030's silent
   failure — a field missing from `_CSS_TOKEN_MAP` emits no var and raises
   nothing. A browser-tier computed-style assertion was considered and skipped:
   this token has no precedence subtlety left without the kill switch, and no
   sibling token (`--hw-node-bg` included) is guarded that way.

`docs/components/themes/theme-canon.md` and `docs/reference/design-guide.md`
both carry the cost and the opaque-card rule now; the design guide previously
recommended `backdrop-filter` for frosted-glass node effects with no cost
attached.

---

## Decision 2 — LOD's zoom coupling is a net loss (settled, unbuilt)

Full 6-cell matrix, Firefox, `perf/lod-sweep-instrument`:

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
  with nothing to hide LOD costs nothing, so the 2.15x is the crossing itself,
  not a harness artefact.
- **LOD buys nothing during pan**: 10.80 vs 10.82 fps. Hiding every widget and
  label on 200 nodes changed the framerate by 0.2%.

A 2.15x penalty to buy a 0.2% gain. The mechanism: pan cost is card-chrome
raster, which LOD does not touch.

**Do not try to make crossings cheap.** Measured by hand: the CSS toggle for 200
nodes is ~1s, a re-render ~5s. Both are hangs. There is no cheap way to change
200 nodes' detail mid-gesture, so nothing should try. The three rounds of
selector optimisation already recorded in `pan.vue`'s comment block (opacity ->
display:none, killing `var()` indirection, `:hover` -> JS class) each won an
order of magnitude and the crossing still costs 566ms. The remaining cost is
layout, not restyle.

**Open, needs design:** what happens to `zoom-pan-lod0/1/2/3` and
`data-lod-level`. The cheap reading is *drop the `display:none` rules, keep the
attribute* — the attribute flip is free, and it is what any future zoom-tiered
paint-only change would hang off. Touches ADR-0006 and the skin-authoring
contract (`docs/components/skins/skin-canon.md`). The user has said skins outside
this repo do not exist yet, so breaking that contract is acceptable.

---

## Decision 3 — NodeDetail from construction gate to CSS filter (proven, needs design)

**The measurement that settles it.** Three variants of the same visible result,
Firefox, flat cards, LOD off:

| variant | pan fps | sweep fps |
|---|---|---|
| FULL built | 18.64 | 72.32 |
| COMPACT built | 57.20 | 99.35 |
| **FULL + CSS-hidden** | **56.11** | **101.43** |

**CSS-hidden lands at 0.98x / 1.02x of constructed COMPACT** — indistinguishable
— and 3.01x / 1.40x over constructed FULL. `display: none` takes elements out of
layout and paint, which is where the cost was. The DOM residue costs nothing per
frame, **including NiceGUI's per-element VNode rebuild**, which was the risk that
run existed to test.

So `NodeDetail` can become a CSS filter: a detail change costs a class flip
(~1s for 200 nodes, and **staggerable** — 20 nodes/frame turns one freeze into
~20 imperceptible frames) instead of a server re-render (~5s).

**The mapping, from `packages/haywire-core/src/haywire/ui/skin/visibility.py`.**
COMPACT drops exactly three things: port **labels** (FULL), inline **widgets**
(STANDARD+), and inline **diagnostics detail** (FULL). The diagnostics BADGE is
drawn at every rank and must stay. The **port set is identical at both ranks** —
detail changes what is drawn per port, not which ports exist. Labels and widgets
both already carry `zoom-pan-lod2`, so one selector covers exactly what COMPACT
omits. The probe rule is on `perf/detail-via-css`.

**Not settled by any of this**, and the reason to check before committing: the
earlier session measured **node selection latency** (multi-second on 200 nodes)
and **app-wide sluggishness** from NiceGUI's full-tree render walk. Those are not
per-frame costs, and this measured per-frame cost. A CSS-filtered COMPACT graph
keeps FULL's element count, so that risk is unchanged and untested. **One check
before building: select a node on a 200-node FULL graph and see if it is still
slow.** If it is, construction gating may still earn its place for a different
reason than the one that was eliminated.

Also note `enums.py:187-189` documents NodeDetail as *"a construction gate, not a
CSS one"* and names the CSS approach as what separates it from LOD. This reverses
that — deliberate, but it is an ADR-shaped change.

---

## The 3D compositing hints (LANDED)

Verified in both engines: **+19.5% fps and -38.6% p99 in Firefox, free in
Chrome** (-2.8%, spreads overlap).

Removed five 3D compositing hints from `.zoom-pan-content` — `translateZ(0)`,
`backface-visibility`, `-webkit-perspective`, `preserve-3d`, and a `matrix3d`
transform branch that applied only below zoom 0.5, exactly where the framerate
collapsed. They were `-webkit-` prefixed and labelled "Chrome optimizations"; by
now they did nothing for Chrome while costing Firefox a fifth of its framerate.

Caveat carried in the commit message and the code comment: five things changed
at once, so the group is worth 19.5% but individual contributions are unknown.

**One loose end left in the code, deliberately.** The original commit message
claimed `image-rendering: optimizeSpeed` went with them; the diff kept it. It
asks for a cheaper downscale filter, which only matters while downscaling a
large raster — so it reads as a symptom of the problem that was removed rather
than a fix. It stays because the +19.5% was measured with it present and
dropping it would ride an unmeasured change on a verified one. Flagged in
`pan.vue` as worth its own measurement.

---

## The instrument

`debug_overlay.vue` gained a fixed-window recorder (`record 5s`), a zoom `sweep`
mode, a `zoom` preset, and a clipboard-able markdown result row. Protocol is in
`.scratch/pan-perf/RESULTS.md`.

**Three instrument bugs were found by getting wrong answers. Do not reintroduce:**

1. **Capability detection must use `PerformanceObserver.supportedEntryTypes`,
   never a try/catch.** `observe({type})` with an unsupported type does *not*
   throw — per spec it aborts quietly. Firefox implements neither `longtask` nor
   `long-animation-frame`, so the try/catch version reported "supported" while
   counting nothing, and the resulting clean zeros were read as "the main thread
   is idle". Two conclusions were published and retracted on this.
2. **`main ms` discards samples that span frames.** A MessageChannel reply that
   lands a frame late measures the wait for the main thread, not one frame's
   work — and replies are delayed precisely when the thread is busy. A run once
   reported `main 269ms` against a 52ms frame. Cross-frame samples are now
   dropped and counted in a `dropped` column; **a high drop count means `main ms`
   is a floor, not a measurement**, and floors with different drop counts cannot
   be compared to each other.
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
table may be cold. It does not plausibly explain the large effects (1.9x, 2.15x,
3.07x, all consistent across matched sets) but it is inside the range of the
small verdicts. **Add a discarded warm-up sweep after every page load.**

---

## What was ruled out, with numbers

Do not re-investigate these:

| Ruled out | By |
|---|---|
| Card contents | collapse — the original symptom |
| Detail layers via LOD | +7.5% zoom-adjusted, inside spread |
| Stacking contexts / paint chunks | `perf/node-zindex-drop`, +4.3%, noise |
| Layer promotion (`will-change`) | `perf/no-promotion`, overlapping spreads, worse in Chrome |
| All main-thread JS and style/layout | `main ms` 2-5% of the frame, both engines |
| Viewport culling by unmount | at the zoom where the symptom appears, nothing is off-screen |

---

## What is left

Steps 1 and 2 of the original order are done (`perf/flatten-3d-merge`). What
remains:

1. **Check node-selection latency on a 200-node FULL graph** — one measurement,
   by hand, and it gates decision 3. Still unrun.
2. **`/design` on NodeDetail-as-CSS-filter and the fate of the LOD classes**,
   together. They touch the same token cascade and skin contract, and ADR-0006 /
   ADR-0032 both need revisiting. The open question with no measurement pending:
   as a CSS filter, COMPACT stops meaning "these widgets do not exist" — they
   would exist, hold state, and take binding traffic while invisible. That is a
   decision about what `NodeDetail` *means*, not about frame cost.
3. **Delete the four probe branches** once decision 3 lands.

Related: `.insights/project_css_var_theme_silent_failures.md` (silent cascade
failures), `.insights/feedback_css_containment_node_floor.md` (node size floor),
`.scratch/pan-perf/RESULTS.md` (all runs and the protocol).
