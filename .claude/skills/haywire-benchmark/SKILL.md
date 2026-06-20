---
name: haywire-benchmark
description: >
  Run the Haywire node performance benchmark suite and report drift. Runs every
  frozen benchmark case (graph-level + isolated microbenchmarks) via
  benchmarks/run.py, records min-of-N absolute timings stamped with
  commit/host/dirty, appends one row per case to benchmarks/results/results.jsonl,
  and prints each case compared to its last clean run on this machine
  (↑ regressed / ↓ improved / ~ flat). Appends only — never commits. Supports a
  case-name filter. Use whenever the user wants to benchmark node/execution
  performance, check for a performance regression or drift, or record a baseline.
  Trigger phrases: "/haywire-benchmark", "run the benchmarks", "benchmark
  performance", "check for perf drift", "did that change regress performance".
---

# `/haywire-benchmark`

Runs the node performance benchmark suite and reports drift against past runs.
Composes the runner ([`benchmarks/run.py`](../../../benchmarks/run.py)) over the
frozen case registry; methodology and result schema are documented in
[`benchmarks/README.md`](../../../benchmarks/README.md).

## When to use

- The user says "run the benchmarks", "benchmark this", "check for perf drift /
  regression", "record a baseline", or invokes `/haywire-benchmark`.
- After a change to a hot path (execution VM, ports/pipes, edges, node dispatch)
  to see whether a case moved.

## Inputs

- **case-name filter** (optional) — substring; runs only matching cases (e.g.
  `control_edge` to iterate on one microbench). Omit to run all.

## Procedure

### Step 1 — note the working-tree state

```bash
git status --porcelain | head
```

If the tree is **dirty**, tell the user the run will be recorded as
`dirty=true` and will **not** serve as a baseline for future comparisons (it's
fine for a quick before/after on the same dirty state, but a clean-tree run is
needed to seed a durable baseline). Proceed regardless — the runner handles it.

### Step 2 — run the suite

```bash
uv run python benchmarks/run.py [name-filter]
```

The runner bootstraps the library system, warms up and times each case
(min-of-N), stamps `commit/dirty/branch/host/python/timestamp`, appends one JSONL
row per case to `benchmarks/results/results.jsonl`, and prints a table.

### Step 3 — interpret and report

Read the printed table back to the user:

- **`↑ +X%`** — regression vs the last clean run on this host. Flag it.
- **`↓ −X%`** — improvement. Note it.
- **`~ ±X%`** — within the ±2% deadband; treat as flat (noise).
- **`(no prior)`** — first run, or no clean-tree baseline exists yet on this host.
- The `median`/`p90` columns are the spread; if `p90` is far above `min`, the row
  was jittery and the drift number is less trustworthy — say so.

### Step 4 — remind about the appended rows

The runner **appends but does not commit**. Tell the user the new rows are in
`benchmarks/results/results.jsonl`, uncommitted — fold them into the same commit
as the change being measured (or `git checkout benchmarks/results/results.jsonl`
to discard an exploratory dirty run).

## Do not

- **Do not commit or push** anything. The skill measures and reports; committing
  the result rows is the user's call (matching `haywire-release`, which also hands
  git operations back to the user).
- **Do not edit frozen inputs** (`benchmarks/graphs/`,
  `barn/haybale-testing/haybale_testing/nodes/benchmark/`) to "fix" a number —
  that breaks drift comparability. See `benchmarks/README.md`.
- **Do not** treat a dirty-tree result as a baseline or compare a result from one
  `host` against another's.
