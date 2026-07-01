# Haywire benchmark suite

A drift-tracking performance suite for node execution. Two flavours of case —
**graph** (nodes running in a real assembled graph) and **micro** (one isolated
operation) — measured the same way and logged to a commit-stamped file so you can
watch numbers move across the codebase's development.

Run it via the skill:

```
haywire-benchmark               # all cases
haywire-benchmark graph_loop    # only cases whose name contains "graph_loop"
```

or directly:

```
uv run python benchmarks/run.py [name-filter]
```

Each run appends rows to `results/results.jsonl` and prints a table comparing each
case to its last comparable prior run. **The runner never commits** — fold the new
rows into whatever commit you were measuring.

## Why it's measured the way it is

These choices are deliberate; they're what make the recorded numbers trustworthy
enough to call a move a "regression" instead of noise.

### Min-of-N, not mean

Each case runs `N` times after warmup; we record the **minimum** per-operation
time. For deterministic CPU-bound work the fastest sample is the one with the
least scheduler/GC/background interference — i.e. closest to the true cost. Mean
and median drag in whatever else the machine was doing. We still store `median`
and `p90` as *spread* fields so a reader can tell when a row is too jittery to
trust — but the headline, and the thing drift is computed against, is `min`.

### Absolute per case, never deltas

We log each scenario as its own absolute case (`graph_loop`,
`node_execute_bare`, …) and **never** store a derived delta (e.g. "with X −
without X"). A delta is a small difference of two large noisy numbers; we watched one
such delta swing **330 → 754 → 1119 ns across three identical runs** while the
absolute per-case numbers it was derived from stayed stable to ~±2%. To compare
two scenarios, add both as cases and read them side by side in the log — each is
independently stable, so each drifts honestly.

### Stable inputs

Every graph and node a case touches is held **stable** so a moved number means the
*framework* moved, not the fixture:

- graphs are **built fresh** each run from an explicit node-key + edge list in
  [`cases.py`](cases.py) (`_LOOP_NODES` / `_LOOP_EDGES`). Same nodes, same edges,
  same loop bound every time — deterministic, but tracking the live registry so a
  node/type moving library can't silently break the load (a frozen `.haywire` file
  did exactly that when the primitive types were hoisted into the `builtin`
  library and the serialized port type keys went stale).
- nodes live in `barn/haybale-testing/haybale_testing/nodes/benchmark/` and are
  marked *DO NOT EDIT*.

If a benchmark reused a general testbed node and someone added a port to it, the
number would "drift" for a reason that has nothing to do with framework
performance — which is why the case builds an explicit, fixed topology.

### Host + dirty filtering

Absolute timings are only comparable within the same machine and from a clean
tree. So every row records `host` and `dirty`, and the drift comparison only ever
baselines against rows with the **same `host`** and **`dirty=false`**. A run from
a dirty working tree is still recorded (marked `dirty=true`) but never used as a
baseline and never masquerades as a clean, commit-attributable datapoint.

## Result schema (`results/results.jsonl`)

One JSON object per line, one line per (run × case):

| field | meaning |
|---|---|
| `timestamp` | UTC ISO-8601 of the run |
| `commit` | short hash of `HEAD` at run time |
| `dirty` | was the working tree dirty? (if so, not a valid baseline) |
| `branch` | current branch |
| `host` | machine name (only same-host rows are comparable) |
| `python` | interpreter version |
| `case` / `category` | case name and `graph` \| `micro` |
| `min` / `median` / `p90` | per-operation time; `min` is the headline, the others are spread |
| `n` | number of timed repeats |
| `unit` | `ns` per operation (one node execution for graph cases, one call for micro) |

Append-only and long-format, so tracking one case over time is a one-liner:

```
jq 'select(.case=="graph_loop" and .host=="<your-host>" and .dirty==false) | .min' \
   benchmarks/results/results.jsonl
```

## Adding a case

1. If it needs a node or graph, add a **frozen** one (new file in
   `nodes/benchmark/`, or a copy under `graphs/`) — never reuse a mutable one.
2. Add a `_prepare_*()` returning a `Prepared(run, ops, repeats, warmup)` and an
   entry in `CASES` in [`cases.py`](cases.py). `ops` is how many operations one
   `run()` performs (node execs for a graph run, inner-loop count for a micro).
3. The smoke test (`tests/core/test_execution/test_benchmarks_smoke.py`) picks it
   up automatically and asserts it produces a positive number.
