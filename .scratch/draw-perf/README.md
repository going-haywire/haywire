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

Remove the worktrees afterwards with `git worktree remove --force .scratch/draw-perf/<cN>`.
