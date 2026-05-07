---
name: haywire-exec
description: Load Haywire execution engine docs into context. Use when the user wants to work on assembly, the VM, data flow, lazy propagation, edge lifecycle, or the graph-to-execution pipeline.
---

# Load Haywire Execution Engine Docs

Read the following documentation files in order and use them as the authoritative reference for any execution engine or graph internals task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/architecture/execution/assembly/assembly-arch.md` — Graph → Assembly → Flow pipeline: `FlowAssemblyManager`, event-node identification, `LocalizedDataFlow`, lazy bitmasks (`EVAL_MASK`, `LAZY_MASK`), JIT reassembly triggers
2. `docs/architecture/execution/edges/edges-arch.md` — 4-stage `EdgeWrapper.build()` pipeline, three-tier edge lifecycle (`link()` → `unlink()` → `detach()`), two-tier port storage (`_linked_edges` + `_all_edges`), asymmetric displacement, lazy propagation, `resolve_dirty_data()`, `pull_lazy()`, deferred `on_change`, `ValidationManager` priority system

Optional context (load if the task needs it):

- `docs/architecture/execution/callbacks/callbacks-arch.md` — `FlowType.CALLBACK` edges, cross-flow triggers, edge-based vs string-based mode, assembly-time wiring
- `docs/architecture/hot-reload/hot-reload-arch.md` — file watcher → registry events → wrapper rebuild → graph revalidation; how hot-reload affects edges and flows

## After reading

Summarise in 6–10 bullet points:
- The Graph → Assembly → Flow → VM pipeline and what each stage does
- `LocalizedDataFlow`: per-control-node data DAG, backpropagation from inlets, topological sort
- VM two-stack model: done-stack (prevents re-execution) and loopback-stack (loops/sequences)
- Lazy bitmasks: `EVAL_MASK` (assembly-time, per inlet) and `LAZY_MASK` (runtime, per control node); `AND` determines which data nodes run
- Three-tier edge lifecycle and the difference between `unlink()` and `detach()`
- Two-tier port storage and when each set is queried
- Asymmetric displacement: inlet informs outlet, outlet does NOT inform inlet
- Lazy vs eager pipes: eager push vs `pull_lazy()` (always-latest), `resolve_dirty_data()` deferred `on_change`
- Any gotchas called out in the docs (e.g., reassembly on lazy state change at runtime)

Then proceed with the user's task using these patterns as the guide.
