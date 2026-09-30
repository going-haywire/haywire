---
name: graph-loop-benchmark-drift
description: Handoff — graph_loop got ~8% slower between June and September 2026 (2625 → 2838 ns/op) before edge-kinds step 2; not attributed yet. Bisect it.
metadata:
  type: project
  status: open
---

# Bisect the ~8% `graph_loop` drift (June → September 2026)

`graph_loop` (the real loop graph, ~3000 node executions per run) has drifted
from **2625 ns/op** to **2838 ns/op** over three months, on the same host
(`MB-41545`), before any edge-kinds step 2 code existed. Nobody has attributed
it. `node_execute_bare` did **not** follow (330.6 → 351.1 → 320.1 ns), so the
cost is in what `graph_loop` exercises beyond bare dispatch: port reads and
writes, pipes, adapters, the VM's control-flow walk.

Clean rows from `benchmarks/results/results.jsonl`:

| date | commit | branch | `graph_loop` min | `node_execute_bare` min |
|---|---|---|---|---|
| 2026-06-21 | `3d2e9fe` | master | 2625.0 | 330.6 |
| 2026-07-04 | `adaa50b` | HEAD | 2769.3 | 351.1 |
| 2026-09-28 | `79be47e` | unlink-own-value (step 2 baseline) | 2837.8 | 320.1 |
| 2026-09-29 | `78a1b0f` | unlink-own-value (after step 2) | 2914.5 | 320.7 |

The last row is step 2's own +2.7%, already attributed: each field read
checks for a linked value (about +12 ns × 4.7 reads per node execution). See
the step 2 plan's execution notes,
`docs/superpowers/plans/landed/2026-09-28-unlink-reveals-own-value.md`. It is **not**
part of this task.

Commit counts: `3d2e9fe..adaa50b` is 28 commits (+5.5%), `adaa50b..79be47e`
is 745 commits (694 first-parent) (+2.5%). Both are ancestors of `79be47e`.

**Lead for the June → July step:** `214c7b38` (2026-07-01, inside
`3d2e9fe..adaa50b`) deleted `benchmarks/graphs/loop_bench.haywire` and
rewrote `benchmarks/cases.py` (+85 lines) to build the loop graph in code
instead of loading it. The +5.5% may be mostly a different graph, not slower
code. Check it first: compare the two harnesses' graphs (nodes, edges, lazy
or eager, `ForLoop` bound, node execs per run) and time `214c7b38^` against
`214c7b38`.

---

## Do this first: re-measure the endpoints today

The June and July rows were taken months ago. Python patch version, macOS,
thermal state and background load all move a tight loop by several percent.
Before bisecting anything, measure `3d2e9fe`, `adaa50b` and `79be47e`
**today, interleaved, several times each**. If the gap has shrunk to noise,
the drift was the machine, not the code — stop there and say so.

**Noise is large.** On 2026-09-29, back-to-back runs of the *same* commit
gave `graph_loop` min between 2796 and 3040 ns (±4%). The runner's ±2%
deadband is tighter than that. One run per commit cannot resolve a 2–3% step:
take the min over at least 3 interleaved runs per commit, and prefer
comparing two commits side by side over comparing against an old JSONL row.

---

## Traps

- **`benchmarks/cases.py` changed inside the range.** Run each commit's
  *own* harness (the case must import that commit's node classes), but know
  that the graph itself changed at these commits, which can move the number
  by itself:
  - `b52af82c` / `42234f24` (2026-07-27) — print nodes renamed, logger
    severity config added. The loop graph's `Print` node became
    `LoggerNode`: check whether the logger does more work per execution.
  - `870deca6` / `70c96d92` (2026-08-22) — `BaseGraph(name=…)` became
    `filestem`. API only, probably cost-neutral.
  - `214c7b38` (2026-07-01) — the loop graph went from a saved
    `loop_bench.haywire` file to programmatic construction (see the lead
    above).
  - `f760e780` (2026-07-18) — three lines removed from `run.py` (import
    warnings); cost-neutral.

  A step that lands exactly on one of these is a harness change, not a
  regression: confirm by running the *new* harness against the parent commit
  where it imports.
- **Worktree setup is slow** (~2 min for the first `uv sync`, since it builds a
  venv). Create **one** worktree and `git checkout <sha> && uv sync -q` inside
  it per step; incremental syncs are fast. Remove it with
  `git worktree remove --force <dir>` when done.
- **The runner appends to `benchmarks/results/results.jsonl`** in whichever
  tree it runs in. In the worktree that's harmless. In the main repo, run
  `git checkout -- benchmarks/results/results.jsonl` after exploratory runs;
  commit only deliberate baseline rows.
- **Don't trust cProfile's absolute numbers.** Its per-call overhead inflates
  small functions. It is good for two things: call counts per op, which are
  deterministic (step 2 had identical counts, 44.33 calls/op), and comparing
  self-time of the same function across two commits.
- **`tests/core/test_graph/test_base.py::test_generated_ids_are_distinct`**
  flakes about once in 800 runs (a random-id birthday collision). It is
  unrelated to perf. It's listed in the edge-kinds overview's small items.

---

## Method that worked for step 2

1. A/B two commits: one worktree at the older commit, the main repo at the
   newer one, and `uv run python benchmarks/run.py graph_loop` alternating
   between them 3× each.
2. Attribute with a deterministic profile per commit, then diff per-op call
   counts and per-function self time. The script is below; it saves JSON
   keyed by `file:function`.
3. Confirm the suspect function with `timeit` on the operation alone, run in
   both trees (for step 2 that was `FLOAT.create_field().get_value()`).

```python
# prof_ab.py — usage: uv run python prof_ab.py <repo_root> <out.json>
import cProfile, pstats, sys, json
from pathlib import Path
root = Path(sys.argv[1]); out = sys.argv[2]
sys.path.insert(0, str(root)); sys.path.insert(0, str(root / "benchmarks"))
import run as bench_run
bench_run._bootstrap_library_system(root)
import cases
prep = cases._prepare_graph_loop()
for _ in range(5): prep.run()
pr = cProfile.Profile(); pr.enable()
for _ in range(30): prep.run()
pr.disable()
rows = {}
for (f, line, fn), (cc, nc, tt, ct, _) in pstats.Stats(pr).stats.items():
    short = f.split("/src/haywire/")[-1].split("/barn/")[-1]
    rows[f"{short}:{fn}"] = [nc, tt, ct]
json.dump({"ops": prep.ops * 30, "rows": rows}, open(out, "w"))
```

Diff two outputs by `rows[k][0] / ops` (calls per op) and `rows[k][1] / ops`
(self time per op), sorted by absolute change. The harness entry points it
relies on (`run._bootstrap_library_system`, `cases._prepare_graph_loop`) may
be named differently at old commits; check `benchmarks/run.py` there.

---

## What "done" looks like

The commits (or harness changes) that account for the gap, each with a
measured before/after on today's machine, and the hot function each one
touched. Record the outcome in the edge-kinds overview's *Small items*
(`docs/superpowers/plans/2026-09-28-edge-kinds.md`) or in a new
`.insights/` file if the cause is a trap others will hit. Only fix what is
cheap and clearly safe; bring anything structural back to the user first.

---

## Suggested skills

- **`haywire-benchmark`** — how to run and read the benchmark suite
  (`benchmarks/run.py`, drift table, dirty-tree rules).
- **`using-git-worktrees`** — the baseline worktree for A/B runs.
- **`verification-before-completion`** — before claiming a commit is the
  cause, re-measure it interleaved.
- **`codemap-navigator`** — orient in `packages/haywire-core/src/haywire/core/`
  (types/port.py, types/pipe.py, execution/vm.py) once a suspect commit is
  found.
