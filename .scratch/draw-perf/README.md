# draw-perf — large-graph load timing harness

Measures, in headless Chromium at 1600x900, how long it takes from clicking a graph in the Haystack until every
node card and edge is drawn (metric A), and how long one full `_relayoutEdges()` takes (metric B). Built on
2026-10-16 to bisect the draw-performance regression; see `internals/handoff/draw_performance_regression_fix.md`.

- `start.sh <worktree>`: starts a studio from `<worktree>` on port 8191. HOME is `./home`, so your real auth and
  settings stay untouched. It wraps `UINode._apply_write_gates` to time it (`run_studio.py`, which writes `gate_<name>.json`).
- `runall.sh <cN> <graph> <runs>`: expects a worktree at `./<cN>`, built with
  `git worktree add --detach .scratch/draw-perf/<cN> <sha>`, then `uv sync` inside it. It does a warm-up run, then
  `<runs>` timing runs, then 2 runs with id-lookup instrumentation.
- `bis.sh <sha>`: re-uses worktree `./c2`, checks out `<sha>`, and does one timing measurement (3 runs). Use it for bisecting.
- `setup.py <graph>`: loads the graph into the Haystack once, as warm-up.
- `measure.py`: does the measuring. The node and edge counts for each graph are hard-coded in `NODES, EDGES`.
- `res_c1.txt`…`res_c6.txt`: raw results from 2026-10-16 (see the handoff for which commit each one is).

The two probes below need a studio already running on 8191 with the graph loaded:
`./start.sh ./c2 > c2.log 2>&1 &`, wait for "ready to go" in `c2.log`, then `setup.py 10x512n_5x448e`.

- `profile_edges.py <out.json>`: Chrome's sampling CPU profiler over the edge phase only (from all 512 cards on
  screen to all 2688 edges drawn); writes the top self-time functions. Found the layout thrash in the edge batch
  (2026-10-20: 2.4 s of a 5.9 s edge phase in `getBoundingClientRect`).
- `browser_probe.py <firefox|chromium> <out.json>`: times and counts DOM calls (`querySelector`,
  `getBoundingClientRect`, `getScreenCTM`, `setAttribute`, …) and the longest frame gap over the whole load, in
  either engine. Found Firefox's `[id="…"]` subtree scans (2026-10-20: 34 s of a 52 s load). Time every
  DOM-lookup change in both engines; Chrome alone hides this class of cost.

Remove the worktrees afterwards with `git worktree remove --force .scratch/draw-perf/<cN>`.
