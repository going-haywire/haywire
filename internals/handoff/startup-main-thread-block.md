---
name: startup-main-thread-block
description: Handoff — the renderer main thread is unavailable for ~800ms after a large graph loads; it hijacks browser zoom and stalls the first gesture. Cause not yet attributed, instruments committed.
metadata:
  type: project
  status: open
---

# The ~800ms main-thread block after a graph loads

Opening `graphs/10x300nodes.haywire` leaves the renderer's main thread
unavailable for roughly **0.8 seconds** after the page has been handed over.
Two user-visible symptoms come out of it, and neither is fixable from the
canvas code — the thread simply is not free to run anything.

This is **pre-existing**. It measured identical with and without every change
made during the 2026-09-04 pan-performance session, which is how it was
separated from the causes that were fixed.

---

## Do this first: re-confirm the symptom

The session that found this also fixed a *different* cause with overlapping
symptoms — nested tooltip triggers making every hover crossing a websocket
round trip (`5ec72505`). That fix removed a ~0.5s freeze at the start of a pan
in Firefox.

**Some of what was originally reported as "the first gesture after load
freezes" was that.** Before designing anything here, load a large graph and
check whether a first pan still stalls. The block itself is measured and real;
how much of it the user actually feels, post-fix, is not.

---

## Symptom 1 — an early gesture hijacks BROWSER zoom

A pinch or ctrl+wheel begun during the block zooms the *page*, not the canvas,
and only `View > Zoom > Actual Size` undoes it.

Canvas zoom depends on `@wheel.prevent` on `.zoom-pan-container` (`pan.vue`).
Chrome does not wait indefinitely for a non-passive wheel listener; with the
main thread blocked, it applies its own default.

**An earlier-registered listener does not fix this.** The listener is not
missing — the thread that would run it is blocked. Anything short of shortening
the block only moves the problem.

## Symptom 2 — the first gesture stalls, then it is fine

Worst frame gaps during one short pan, run twice against the same page — once
as early as the canvas allows, once after a settling period (Chrome,
`10x300nodes`, ms):

    EARLY    [555, 539, 118,  95]
    SETTLED  [ 78,  66,  65,  62]

Repeated ~500ms stalls early, clean afterwards. Users describe this as "freezes,
then the graph jumps, then it is smooth", and "gone after about a minute" —
which matches the graph-load work finishing rather than any warm-up.

---

## What is measured, and what is not

| | |
|---|---|
| Main thread unavailable after hand-over | **769-1015 ms** across runs |
| Same, with the session's canvas changes reverted | **776-778 ms** — unchanged |
| Browser | **Chrome only.** No Firefox numbers were taken for the block |
| Cause | **Not attributed.** No trace has been windowed on it |

Candidates, none tested:

- 300 nodes arriving over the websocket and being built by Vue/Quasar
- the measurement write-back cycle (`ResizeObserver` → `nodesMeasured` → server
  → `width`/`height` props → relayout), which is known to keep running after the
  last node lands
- the initial fit/centering pass
- first raster of a large canvas at low zoom

---

## Instruments (committed, `4b946be6`)

    uv run python .scratch/pan-perf/startupgap.py

Times how long a trivial `page.evaluate` takes to return — it runs ON the main
thread, so the wall clock around it *is* the block. Also polls for what is not
yet wired (container, `_zoomPanControls`, canvas-ready) and dispatches a probe
`ctrl`+wheel each tick to report whether anything would have called
`preventDefault`.

    uv run python .scratch/pan-perf/earlyfreeze.py --settle 60

Runs the same short pan early and again after settling, reporting the worst
frame gap and the long tasks in each.

For attribution, trace it: `panperf.py --trace` then `analyze_trace.py`, and
window on the first seconds rather than a steady-state pan.

---

## Traps, all paid for once already

**Measure the browser the user is in.** The whole harness defaults to
`channel="chrome"` (`session.launch`). A day of this session's work was spent
optimising Chrome while the reported symptom was in Firefox, where the cause
was different. Pass `--engine firefox` where a probe supports it, and add it
where one does not.

**The EARLY column looks the same in every configuration**, because graph load
dominates it. Only the SETTLED column separates a cost you introduced from one
that was always there. A cost that survives settling is yours.

**Averages cannot see this.** It is a stall at the START of a gesture; mid-
gesture framerate, mean frame time and fps all look correct. Read worst frame
gap, not fps.

**A probe driving a live studio mutates the graph it measures.** Any probe that
presses a mouse button can commit an edge, move a node or stamp a manual size
into the fixture file — `eventcensus.py` grew `--skip-wire` for exactly this,
after writing four real edges into `10x300nodes.haywire`. Check `git status`
after a run.

**`ensure_studio` reuses whatever is already on :8124**, including the
developer's own interactive session. Measurements then share a server with a
human clicking around. Start a dedicated instance for anything load-bearing.

---

## Related

- `.insights/project_chrome_layerize_3d_transform.md` — the layerize cliff, and
  why adding an element over the canvas is expensive in Chrome. Reached while
  chasing this; the "cost that survives settling is yours" rule lives there too.
- `.scratch/pan-perf/RESULTS.md` — the run table and protocol for the pan work.
- `5ec72505` — the tooltip-trigger fix, i.e. the cause that was NOT this one.
