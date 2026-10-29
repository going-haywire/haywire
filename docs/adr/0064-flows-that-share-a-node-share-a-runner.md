---
name: flows-that-share-a-node-share-a-runner
description: Flows that share a control node run on one runner thread (an execution group); a data node executed by several groups runs under its wrapper's exec lock; structural batches wait for the frame barrier; a stop that times out kills the run, and stuck runners are abandoned
status: accepted
see-also: ADR-0002, ADR-0010, ADR-0043
level: framework
---

# Flows that share a node share a runner

**Context.**

- Every Flow ran on its own scheduler thread, but nodes are shared by reference: a control node reachable from two EVENT nodes sits in both Flows' control graphs, and a data node feeding a control node in each Flow sits in both localized data flows.
- A reproduction proved that two threads ran one node's `_execute` at the same instant, in five ways: a shared control node on two threads; a worker reading the *other* flow's EXEC payload (pushed through the eager pipe mid-frame); two threads draining `_has_dirty_ports` (one `popitem` raises); a BeginPlay frame overlapping the Shutdown frame at stop, with `on_startup`/`on_shutdown` called once per Flow; a shared data node evaluated by two Flows at once. The shared-node concurrency report recorded the evidence.

**Decision.**

- **D1** Execution stays one thread per unit; the unit is the **execution group**, not the Flow.
- **D2** Assembly refuses no cross-flow link: Flows that share a control node are merged into one group instead (ADR 0043: defuse, don't refuse).
- **D3** Grouping rule: Flows that share a control node form a group, transitively, counting each Flow's entry EVENT node. Data nodes, data edges and callback/subscription edges never group Flows.
- **D3a** A **shared data node** is a data node in the localized data flows of more than one group. Its `_execute`, `on_frame_start` and `on_frame_end` run under its wrapper's `exec_lock`. The first group to reach it in a frame computes it; a group arriving later waits, finds it clean and reads the fresh outlet. Its state advances once per frame of whichever group reaches it first. Its frame hooks run in every frame of every group that executes it; calls never overlap but may interleave between groups, so start and end need not pair.
- **D3b** Values cross groups asynchronously through data edges, as written. A value object must not be mutated in place once written to an outlet.
- **D4** One runner thread per group (`FlowExec-group_<first flow id>`), one merged FIFO of its Flows' triggers, system events included.
- **D5** DROP keeps the **newest** pending trigger: a full DROP queue replaces its oldest trigger. Every Flow gets this, since a one-Flow group is the same machinery. Amends ADR 0010.
- **D6** A callback emitted from inside a group's own frame never blocks: it is enqueued without waiting, and dropped with a warning when that Flow's queue is full.
- **D7** Value writes from outside a frame (UI, edit route, Farmhand, node-owned threads) apply immediately. Node authors guard state an `on_change` or settings handler shares with `worker()`.
- **D8** A validation batch that may change structure (`ChangeReason.mutates_structure()`) first parks every group of the graph tree at the **frame barrier**, and leaves them parked when the batch requires reassembly, until stop. It waits at most 2 s for running frames: a frame still running then (a stuck worker) overlaps the batch, with a warning, so a stuck node never freezes the thread that validates — under `LoopScheduler`, the UI's event loop.
- **D9** Stop and autorestart after a reassembly run outside the validation lock, through `ValidationManager.call_soon`.
- **D10** Lifecycle is reference-counted on the wrapper (`retain()`/`release()` under `exec_lock`): before its first frame each group retains every node it executes, and the first retain calls `on_startup`; after its last frame it releases them, and the last release calls `on_shutdown`. A node starts twice in one run only if one group fully stops before another starts.
- **D11** A stop whose running frame outlasts its timeout **kills** the run: queued triggers are discarded, the frame ends at its next control node, and `on_shutdown` still runs. A runner that does not exit even then is **abandoned**; `GraphEntry.compile()` refuses while one is alive. There is no separate user-facing kill: stop already bounds every hang, and a kill cannot end a stuck worker either (Python cannot kill a thread).
- **D12** No UI shows Flows or groups.
- **D13** Node-owned threads (TickEmit's tick loop, capture loops) may emit callbacks and read inputs, guard state shared with `worker()` and the lifecycle with the node's own lock, and write ports only through `BaseNode.post_value`, which applies the write on the validation scheduler's thread.

**Lock order.** Group hold → `NodeWrapper.exec_lock` → validation lock → `NodeWrapper._lock`. A runner thread never waits for a hold (a hold requested from a runner, or by a thread already inside the validation lock, is not taken); a holder never holds the validation lock while waiting for runners; a thread holds at most one `exec_lock` (only the VM calls `_execute`, and a data node's worker never executes another node); validation never takes an `exec_lock`.

**Considered.**

- *Sorted per-node locks over a frame's nodes.* A frame's node set is only known as it runs (branches, loops), so locks cannot be taken up front, and taking them as the frame goes needs an order the control graph does not give.
- *A per-node `_execute` lock for control nodes.* Refuted by the payload-swap reproduction: the eager pipe writes the other Flow's payload into the inlet before the lock is reached, so serializing `_execute` still runs a worker on the wrong payload.
- *Grouping on any shared node, data nodes included.* The rule needs explaining (a read-only data source silently welds two camera flows into one thread) and forbids asynchronous data sharing between groups.
- *One thread per graph.* Simple and safe, but serializes independent camera flows that run in parallel today.
- *Refusing cross-flow links at assembly.* Breaks existing graphs whose shared node is harmless (ADR 0043).

**Consequences.**

- DROP keeps the newest pending trigger instead of discarding the incoming one.
- A shared data node's state advances per frame of the first-arriving group, so two groups never both see "their own" update of it in the same round.
- Two Flows sharing a control node no longer run in parallel; Flows that share only data stay parallel.
- After an edit that requires reassembly the graph is parked until the haystack restarts it; that stop skips the Shutdown flow, which would run on the outdated assembly, and relies on `on_shutdown`.
- Several event nodes may share one event subscription (two `BeginPlay` nodes, two `Shutdown` nodes): each roots its own Flow and one dispatch triggers them all; the Shutdown grace period is one deadline for all Shutdown flows.
- A stuck worker no longer hangs stop: the group is killed, then abandoned, and the graph cannot start again until the stuck thread returns.
