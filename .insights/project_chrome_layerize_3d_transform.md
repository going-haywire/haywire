# A 3D transform on a per-widget element is a Chrome-only performance cliff

**Symptom.** `graphs/10x300nodes.haywire` (300 nodes × 11 number widgets) panned
at **6 fps in Chrome** while Firefox managed 19. Node cards drew half-finished,
whole columns were missing, and the app shell (top bar, tabs, sidebar) went
unpainted mid-pan — read as "strong flickering throughout the UI".

**Cause.** `.number-drag::after` — the focus underline on every number widget —
used `transform: scale3d(0, 1, 1)`.

A 3D transform gives the element its own transform node in Blink's paint
property tree and blocks the paint-chunk merging that
`PaintArtifactCompositor::Update` — `Layerize` in a devtools trace — depends on.
One widget costs nothing. **3300 of them cost ~500 ms per Layerize**, 86.5% of
the main thread. The compositor was then too starved to raster tiles in time,
which is where the **unpainted app shell** came from — top bar, tabs and sidebar
going blank mid-pan.

> **The blank NODE regions are a different bug** — `will-change` promotion, see
> the companion file `project_chrome_paint_completeness.md`. This one was
> initially reported as fixing both, on the strength of a before/after
> screenshot. It does not. Restoring `scale3d` via CSS and measuring gives 49.7%
> of cards unpainted against 50.7% with the fix: unchanged.

Fixed by using the 2D `scaleX(0)`. The animation is identical — it only ever
scaled on X. **6.05 → 87.19 fps**, p99 525 ms → 25.6 ms, main thread 159 → 7 ms.

## Why it looked like a Firefox-vs-Chrome story and wasn't

Firefox measured **18.94 fps with the fix and 18.99 with `scale3d` injected
back** — it does not care, because WebRender has no Layerize step. So the
Firefox-side work (`perf/flatten-3d`, which removed 3D compositing hints from
`.zoom-pan-content`) improved Firefox and left this untouched, and Chrome —
which had been the *faster* engine at 200 nodes — fell off a cliff the moment
the graph had enough widgets. Two unrelated problems that looked like one
regression.

## Rules

- **Never `scale3d` / `translate3d` / `translateZ` / `matrix3d` on anything that
  appears once per widget, per pin or per node.** Use the 2D form. The canonical
  underline animation in `docs/reference/design-guide.md` §8.25 is `scaleX`.
- Judge these by *how many* elements carry them, not by how heavy one looks. The
  same declaration is free at 1× and pathological at 3300×.
- `canvas.vue:3389` still has `translateZ(0)` on `.dragging-node`. That is one
  element at a time, so it is fine — but it is the same anti-pattern, so do not
  copy it onto a selector that matches every node.

## How to check it again

`.scratch/pan-perf/` automates the whole measurement (see its README). The
decisive move is a trace, not a framerate:

```sh
uv run python .scratch/pan-perf/panperf.py --runs 1 --trace /tmp/t.json
uv run python .scratch/pan-perf/analyze_trace.py /tmp/t.json --last 5
```

`Layerize` dominating `CrRendererMain` self time is this bug's signature. Then
bisect with `--css '<hypothesis> !important'`, which needs no source edit and no
studio restart.

Two traps met on the way:

- **`display: none` on the children misled the bisect.** Hiding the widget's
  arrows scored 6.98 and hiding its centre scored 7.06, so neither child looked
  guilty — yet `visibility: hidden` on their shared container scored 113. The
  cost was the container's *own* paint (that pseudo-element), which no
  child-hiding probe can reach. When part-by-part probes all come back flat but
  the whole is huge, suspect the container.
- **Hiding pins made it *worse*** (6.05 → 2.16 fps): they sit in a grid, so
  removing them reflows every card. A `display: none` probe changes layout;
  `visibility: hidden` is the one that isolates paint.
