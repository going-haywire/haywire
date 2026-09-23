# A Subgraph on a different scheduler than its host deadlocks

Fixed 2026-09-23. `BaseGraph.add_subgraph` now makes the definition adopt the
host's `validation_scheduler`. Read this before changing that line, before
constructing a `SubgraphDefinition` outside `add_subgraph`, or when a test
hangs rather than fails.

## The symptom

A run **hangs** and dies at the 120s pytest-timeout, instead of failing.
Roughly 1 parallel (`-n 4`) run in 13, never serially, landing in
`tests/core/test_undo/` or a macro test — a different one each time. It reads
exactly like xdist flakiness, which is why it went unnoticed: the suite had
never been run in parallel before.

## Why it happened

`ValidationManager` falls back to `ThreadingTimerScheduler` when given no
scheduler. Four of the five `SubgraphDefinition(...)` construction sites passed
none, so **a Subgraph of a `SyncScheduler` graph validated on a background
timer** — silently, and against the host fixture's stated intent ("`SyncScheduler`
so validation runs inline"). Only the deserialization path in `base.py` got it
right, and its comment says why.

That leaves two threads holding the same two locks in opposite orders:

```text
main thread (host, SyncScheduler)
  mark_node_dirty  -> host._validation_lock           HELD
    _schedule_validation -> SyncScheduler runs _validate_batch INLINE
      _housekeeping  -> wants card NodeWrapper._lock   BLOCKS

timer thread (Subgraph, ThreadingTimerScheduler)
  redraw()         -> card NodeWrapper._lock          HELD
    _on_definition_validated -> self.wrapper._graph is the HOST
      mark_node_dirty -> wants host._validation_lock   BLOCKS
```

Both locks are `RLock`, which is what makes this hard to see: re-entering
either from one thread is fine, and every single-threaded path works. The cycle
needs two graphs on two different schedulers.

The hinge is the `GraphNode` card. It is subscribed to the **Subgraph's**
validation but writes to the **host's** (`self.wrapper._graph`) — it is, as its
docstring says, "the only thing spanning both graphs". That span is the feature;
running the two ends on different threads is the bug.

## The rule

**A Subgraph validates on the same scheduler as the graph hosting it.**
`add_subgraph` enforces it for every caller, and recursively — it sets
`definition.validation_scheduler` as well as calling
`ValidationManager.adopt_scheduler`, so a nested definition reads the corrected
value from its own host.

Do not construct a `SubgraphDefinition` and use it without `add_subgraph`. If
you ever need to, give it the host's scheduler yourself.

Pinned by `tests/core/test_graph/test_validation_scheduler.py::test_a_subgraph_adopts_its_host_s_scheduler`,
which fails without the fix. A second test pins the other half: adopting must
not force a scheduler onto a host that never chose one.

## The general lesson

A hang is not a flake. The suite going parallel did not introduce this — it
made an existing interleaving likely enough to observe, in code that ships on
`ThreadingTimerScheduler` by default. The same cycle could hang a real studio
session with a Group open.
