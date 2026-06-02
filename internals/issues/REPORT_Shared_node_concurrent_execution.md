# Report: Nodes shared across flows can be executed concurrently (no flow lock)

Date: 2026-06-02
Severity: latent data race — not currently reproduced, but exposure grows with
flow execution time. Worth fixing before graphs with long-running frames become
common.

## Summary

A CONTROL node reachable from more than one EVENT node is **shared by reference**
across the flows assembled from those event nodes (it is the same `BaseNode`
object, not a copy). Each flow runs on its **own scheduler thread**. Nothing
serializes execution of a shared node between flows, and `BaseNode._execute`
mutates per-instance state without a lock. Two flow threads can therefore enter
the **same node object** at the same time and corrupt its state.

## Why this is real (code ground truth)

1. **Shared by reference.** `ControlFlowBuilder.build` stores the live node in each
   flow's control graph: `ControlNodeInfo(node=current)` where `current` is
   `graph.get_node_wrapper(...).node`
   (`packages/haywire-core/src/haywire/core/assembly/control_flow_builder.py:71`,
   `:102`). Assembly runs once per event node
   (`flow_assembly_manager.py:107`), so a node reachable from two event nodes
   lands in two flows as the *same instance*.

2. **One thread per flow.** Each flow gets its own `FlowScheduler` with its own
   `_execution_loop` thread
   (`packages/haywire-core/src/haywire/core/execution/scheduler.py:153`,
   `:160`). Interpreter creates one scheduler per registered flow
   (`interpreter.py:218`).

3. **`_execute` mutates unguarded instance state.**
   `BaseNode._execute` (`packages/haywire-core/src/haywire/core/node/base.py:1128`)
   mutates `self._has_dirty_ports` (pops from it), lazily assigns
   `self._executor`, and the worker writes outlet values via `self.out(...)`.
   None of this is synchronized.

4. **No existing lock.** `Flow.is_locked` exists
   (`packages/haywire-core/src/haywire/core/execution/flow.py:126`) but is never
   read or written anywhere — a dead stub. There is no per-node or per-flow
   mutual exclusion.

## When it bites

The canonical shared-node pattern is graceful teardown, which we explicitly
endorse: `Begin Player → TickEmit.start` and `Shutdown → TickEmit.stop` drive the
*same* `TickEmit` instance from two flows (the BeginPlay flow and the Shutdown
flow). Today these two frames are temporally disjoint (start at boot, stop at
shutdown), so the race does not fire.

The exposure is **proportional to how long a flow frame runs**. A shared node sits
inside a flow whose frame also contains, say, a large `For Loop` (the reported
graph runs ~1500 nodes/frame). If a *second* flow is triggered to run that same
shared node while the first flow's long frame is still in progress, both threads
enter the node's `_execute` concurrently. Symptoms would be:
- corrupted `_has_dirty_ports` (pop from under another thread),
- interleaved outlet writes / wrong `self.out(...)` values,
- worker-internal instance state clobbered (unless the node guards it itself, as
  `TickEmit` does with `self._lock`).

This is distinct from the (now-fixed) shared `vm.execution_count` stat race — that
was cosmetic; this corrupts actual execution state.

## Proposed direction: per-shared-node locks, acquired sorted up-front

The unit of consistency is the **flow frame**: a node's state is only coherent at
frame boundaries, so once a flow enters a frame it must finish before any other
flow runs a node it shares. But the *locking granularity* is the **shared node**,
not the flow — this preserves parallelism between flows that happen not to share a
node.

### The model

- Every node that appears in **more than one flow's control graph** gets its own
  `threading.RLock` (the "shared-node locks"). Nodes in a single flow get no lock.
- Each flow precomputes, at assembly time, the **sorted** list of shared-node
  locks it could touch in a frame — `flow.frame_locks: list[RLock]`, sorted by a
  stable global key (the node id), deduped. Sorting is what prevents deadlock.
- A frame acquires **all** of its `frame_locks` up front, in sorted order, *before*
  running any node, and releases them all when the frame ends.

### Why this granularity (vs. connected components)

Connected components over the "flows share ≥1 node" relation would over-collapse:
if A–B share node X and B–C share node Y (A and C share nothing), components put
{A,B,C} under one lock, so A running blocks C needlessly. Per-shared-node locks let
A and C run in parallel (disjoint shared nodes), while still serializing any two
frames that touch the *same* shared node.

### Why sorted-up-front is deadlock-free

All flows acquire common locks in the *same* global order (by node id). A flow only
ever waits "upward" in that order — once it holds Lk it has already passed every
lower-ordered lock and will never request one again this frame. The wait graph
therefore has no back-edges → no cycle → no deadlock. It can *delay* but never
deadlock.

Worked example: A.frame_locks = `[L3, L5, L7]`, C.frame_locks = `[L5]`, C running
(holds L5). A's frame begins, acquires L3 (free), then **blocks on L5** — its
scheduler thread sleeps inside `RLock.acquire()`, consuming no CPU, holding L3, not
yet running any node. When C's frame ends and releases L5, A wakes, takes L5 then
L7, and runs its frame body. (A holding L3 while waiting for L5 can delay a third
flow that needs node 3 — the accepted cost of acquiring the superset up front;
still deadlock-free by the ordering argument.)

### Mechanism: stdlib only — no third-party library

We manage the *policy*; Python supplies the *primitives*:

- `threading.RLock` per shared node. `RLock` (not `Lock`) so a loopback re-entering
  the same node on the same thread within one frame does not self-deadlock.
- `contextlib.ExitStack` to acquire a variable-length, statically-known set of
  locks and guarantee release (including on exception):

  ```python
  from contextlib import ExitStack

  with ExitStack() as stack:
      for lock in flow.frame_locks:        # globally sorted, deduped
          stack.enter_context(lock)        # blocks until acquired
      # run the whole frame: on_frame_start → nodes → on_frame_end
  # all locks released in reverse order here, even on exception
  ```

The stdlib has no "acquire this set atomically" or deadlock detector — the sorted
order and the static `frame_locks` list are ours to compute and are the entire
correctness argument.

### What we own (≈ 30–40 lines, needs design — do not implement blind)

- **Shared-node detection + lock registry.** At flow registration
  (`Interpreter._register_flow` / `FlowAssemblyManager`): find node ids present in
  >1 flow's control graph; mint one `RLock` per such node into a registry
  (`dict[node_id, RLock]`).
- **Per-flow `frame_locks`.** For each flow, intersect its control-graph node ids
  with the shared set, map to locks, sort by node id, dedupe, store on the flow.
  Revive the dead `Flow.is_locked` stub
  (`packages/haywire-core/src/haywire/core/execution/flow.py:126`) as this list.
- **Acquire-all-then-run.** Wrap the frame body in `VM.execute_control_flow` with
  the `ExitStack` pattern above. A flow with no shared nodes has an empty list → the
  loop is a no-op → zero overhead on the common path (incl. the hot Tick flow).

### Rules that must hold (the subtle part)

- **Static superset, up-front.** `frame_locks` is the set the frame *could* touch,
  computed from the control graph at assembly time — NOT discovered lazily as the
  frame runs. Lazy/on-demand acquisition reintroduces ordering hazards and
  partial-acquire deadlock. Acquiring a superset (a conditional branch may skip a
  shared node) is correct, just slightly conservative.
- **Global sort key.** Every flow must sort by the *same* key (node id) or the
  no-back-edge argument breaks.

### Open questions

- Conservatism cost: a branchy frame may hold a lock for a shared node it doesn't
  end up executing. Measure whether it matters; likely negligible given shared
  nodes are rare.
- Alternative to "hold-while-waiting": acquire-all-or-back-off (try-acquire the set
  non-blocking; on any failure release all, yield, retry) never holds partial
  locks but can livelock and is more machinery. Rejected for now — blocking sorted
  acquire is simpler and contention is occasional (mainly at start/stop).
- Interaction with the node-authoring thread-safety contract: even with frame
  locks, a node that spawns its own threads (TickEmit) still needs its own guard
  for *those* threads. The frame lock only serializes flow-thread *entry* into the
  node, not the node's self-managed background threads.

## Related
- Inquisition resolution (one-event-node-per-flow holds; nodes shared by
  reference): the architecture deliberately allows shared nodes, which is exactly
  what makes this lock necessary.
- Fixed sibling bug: `vm.execution_count` shared-counter stat corruption
  (VM now returns per-frame node count via `exec_ctx.exec_count`).
