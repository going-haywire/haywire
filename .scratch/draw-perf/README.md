# draw-perf — large-graph load timing harness

Measures, in headless Chromium or Firefox at 1600x900, how long it takes from clicking a graph in the Haystack until
every node card and edge is drawn. Built 2026-10-16 to bisect a draw-performance regression (resolved 2026-10-20; the
bisect scripts and raw results were removed afterwards and live in git history). Findings about load cost:
`.insights/project_browser_rendering_cost.md`.

- `start.sh <worktree>`: starts a studio from `<worktree>` (the repo itself, or a `git worktree`) on port 8191. HOME
  is `./home`, so your real auth and settings stay untouched. It wraps `UINode._apply_write_gates` to time it
  (`run_studio.py`, which writes `gate_<name>.json`). Wait for "ready to go" in its log.
- `setup.py <graph>`: loads the graph into the Haystack once, as warm-up.

With a studio on 8191 and the graph loaded:

- `measure_engine.py <label> time <runs> <graph> <chromium|firefox>`: time until fully drawn. The node and edge counts
  for each graph are hard-coded in `NODES, EDGES`. Time every change in both engines.
- `browser_probe.py <firefox|chromium> <out.json>`: times and counts DOM calls (`querySelector`,
  `getBoundingClientRect`, `getScreenCTM`, `setAttribute`, …) and the longest frame gap over the whole load. Found
  Firefox's `[id="…"]` subtree scans (2026-10-20: 34 s of a 52 s load). Chrome alone hides this class of cost.
- `breakdown.py <out.json>`: Chromium CPU profile over the whole load, by script (`(idle)` is mostly waiting on the
  server) and by stack (`renderRecursively` is the Vue page walk), plus websocket message counts and bytes.
- `ws_kinds.py <engine>`: the load's websocket messages grouped by kind and, for `run_javascript`, by the JS they run.
- `elements.py`: after a load, the page's NiceGUI elements by tag with their JSON size; writes `elements.json`.

Remove any worktree afterwards with `git worktree remove --force .scratch/draw-perf/<name>`.
