# A large graph's load blocks the browser in a few multi-second tasks, and batching does not fix it

Opening a graph of several hundred nodes stalls the browser's main thread for
1–3 s at a time while the cards arrive. A gesture started then waits for the
stall to end. The cost is per element, not per message, so changing how the
server batches node mounts does not help, and the code that shows up on top of
a profile is not the code that adds the cost.

## Measured (2026-10-28)

Worst single main-thread wait after the first node lands, fresh studio, graph
restored as the only open tab, three runs each:

| | 256 nodes (`10x256n_5x224e`) | 512 nodes (`10x512n_5x448e`) |
|---|---|---|
| Chrome | 1.1 / 1.5 / 1.1 s | 3.0 / 2.2 / 2.3 s |
| Firefox | 2.5 / 2.1 / 1.8 s | 2.9 / 2.0 / 3.4 s |

The thread is free when the page is handed over (3–31 ms). The stalls start
when nodes arrive, 4–8 s in, and come in bursts; 512 nodes has a second burst
at 16–35 s. They grow with node count, and Firefox is worse at 256.

## What a stall is made of

Chrome trace of the 512-node load: six tasks over 200 ms, 6.4 s in total.

| Work | Time |
|---|---|
| Vue mounting and patching (`RunMicrotasks`) | ~3.1 s |
| of which NiceGUI's full-page render walk (`renderRecursively`) | 1.67 s, over four walks of 0.6–0.8 s |
| style recalculation of the new DOM | 1.6 s |
| layout | 0.8 s |

One style pass and one layout pass per task: no thrashing. Each task is one
delivered message: mount the cards, walk the whole render tree, recalculate
style, lay out.

## Traps

**Batching node mounts does not help.** The server mounts node by node
(`sync_with_graph_chunked`, `asyncio.sleep(0)` between), but NiceGUI's outbox
bundles whatever was queued between two flushes, so the browser still receives
a handful of large messages. Mounting in fixed batches was tried and reverted
(`99478c54a`, reverted in `b07adc60a`): time until the 512-node graph was
fully drawn was 13.7 s node by node, 23 s in batches of 5, 14.7 s in 25,
14.4 s in 50, and a batch only delayed the first card on screen. Pacing the
delivery to shorten each stall trades total load time for responsiveness;
that trade was never measured for responsiveness, only for total time.

**The top of the JS profile is not the cause.** `_edgeGeometryLooksWrong`
(canvas.vue, `getBoundingClientRect` / `getScreenCTM`) and the minimap's
`_getThemeColor` (`getComputedStyle`) lead the self-time list. Each forces the
pending style and layout pass, and its sampled time equals that pass to the
millisecond (1049 vs 1048 ms, 736 vs 735 ms). The frame would pay the same
pass anyway: rewriting either only moves the cost.

**The levers are element count and the render walk.** A 512-node page carries
12,800 `[data-node-id]` elements, about 25 per card; style, layout and Vue
patching all scale with that. The render walk is NiceGUI's unmemoized
whole-page walk ([[project_nicegui_component_vs_native_tag]]).

**What the user feels.** A gesture begun during a stall freezes, then the
graph jumps, then it is smooth; reported as "gone after about a minute",
which is the load finishing, not a warm-up. A pinch or ctrl+wheel begun during
a stall can zoom the *page* instead of the canvas (only View > Actual Size
undoes it): canvas zoom is `@wheel.prevent` on `.zoom-pan-container`, and
Chrome does not wait for a blocked non-passive listener. Registering the
listener earlier does not help; only a shorter stall does. Whether this still
happens is open: a synthetic wheel dispatched from a probe only runs once the
thread is free, so it cannot see the case.

**Measuring it.** Read the worst main-thread wait or frame gap, never fps or
averages: the stall is at the start of a gesture, and mid-gesture framerate
looks fine. Measure in the engine the user is in; Firefox and Chrome differ
here. A run early in the load looks the same in every configuration, because
the load dominates it; compare a run after settling to tell a cost you added
from one that was always there. A probe that presses a mouse button can
commit edges or move nodes in the fixture graph; check `git status` after a
run. `studioctl start` reuses whatever studio holds the port, including your
own interactive one.

## Instruments

All in `.scratch/pan-perf/`, driving a dedicated studio. A graph is restored
only if it is listed in the active haystack (`last_haystack_name` in
`.haywire/settings.json`); snapshot that file and `workspace_state.json`
before a run and restore both after.

```sh
uv run python .scratch/pan-perf/startupgap.py --engine firefox   # per-tick main-thread wait
uv run python .scratch/pan-perf/loadtrace.py --out /tmp/load.json --seconds 35
uv run python .scratch/pan-perf/loadtrace_analyze.py /tmp/load.json --app-only
```

Time until fully drawn, in either engine: `.scratch/draw-perf/measure_engine.py`
(see its README). `earlyfreeze.py --settle 60` runs the same short pan early
and after settling.

Related: [[project_nicegui_component_vs_native_tag]], [[project_multi_canvas_dom_globals]].
