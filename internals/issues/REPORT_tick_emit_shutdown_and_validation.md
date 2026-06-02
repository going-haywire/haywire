# Report: Tick-emitter shutdown hang, 2 s stop delay, and missing graph validation

Date: 2026-06-02
Context: A graph with two `Tick Emit` → `Tick` chains. Original symptom: stopping the
graph hung the whole app (logs kept printing, UI unresponsive). After corrections
(adding a `Shutdown` event node, chaining the 2nd emitter off the 1st), it stops —
but takes ~2 s. Three distinct issues surfaced.

---

## Issue 1 — Shutdown hang (root cause: producers outlive the queue drain)

### Mechanism
- `Tick Emit` is `NodeType.CONTROL`, not an event node. It spawns its own daemon
  thread in `_handle_start` that calls `context.emit_callback` every frame
  (~16 ms @ 60 fps). See `barn/haybale-core/haybale_core/nodes/emits/tick_emit.py`.
- `emit_callback` → `CallbackManager.emit_callback` → `enqueue_trigger` on the
  listening **Tick event flow's** scheduler queue
  (`packages/haywire-core/src/haywire/core/execution/callback_manager.py:98`).
- `Interpreter.stop_execution`
  (`packages/haywire-core/src/haywire/core/execution/interpreter.py:155`) does:
  1. `dispatch SHUTDOWN`
  2. `wait_all(timeout, stop_after=False)` → per flow `wait_for_completion` →
     `trigger_queue.join()`
  3. `_cleanup_current_graph()` → stops schedulers → scheduler thread `finally` →
     `vm.call_flow_shutdown` → node `on_shutdown` → **this is the only thing that
     stops the tick threads.**
- `Queue.join()` blocks until `unfinished_tasks == 0`. The tick threads keep
  enqueuing, so the count never settles → **`wait_all` blocks forever**. The thing
  that would stop the producers (step 3) is never reached because step 2 deadlocks.
  Circular dependency.

### Why one emitter "worked" but two hung
`join()` returns the instant the count momentarily hits zero. With one 60 fps
producer there's a ~16 ms gap per cycle where its single target queue hits zero and
`join()` slips through. With two producers feeding two queues, `wait_all` joins them
sequentially while both producers run the whole time — the slip-through window never
lines up → reliable hang. (Strictly, even one emitter is racy.)

### Secondary bug
`FlowScheduler.wait_for_completion(timeout)` **ignores its `timeout`** — it calls a
bare `self.trigger_queue.join()` (`scheduler.py:258`). So the `timeout=2.0` passed
from `stop_execution` does nothing; a stuck producer can wedge the UI indefinitely.

### Proposed fix (agreed direction: "on_shutdown before wait_all")
1. Make node shutdown idempotent (VM tracks which flows have had `on_shutdown` run,
   re-armed on `call_flow_startup`).
2. In `stop_execution`, after dispatching SHUTDOWN, call `vm.call_flow_shutdown` on
   every registered flow **before** `wait_all` — stopping emitter threads so the
   queues can actually drain.
3. Backstop: make `wait_for_completion` honour its `timeout` so stop can never hang.

Status: NOT yet implemented (paused for this report).

---

## Issue 2 — The compiler accepted an invalid graph (control fan-out)

The original graph wired one EXEC **outlet** (Begin Player.Execute) to **two**
control inlets. This should be illegal (control flow is single-successor per outlet)
but assembly accepted it.

### Where the gap is
- `FlowAssemblyManager._validate_graph` (`flow_assembly_manager.py:134`) only checks
  for **duplicate event nodes of the same subscription**. No control-topology check.
- `StructuralValidator` (`packages/haywire-core/src/haywire/core/validation/structural_validator.py`)
  has node-level and edge-level rules, but:
  - `validate_graph()` (line 354) only runs `_validate_event_nodes_graph_wide()`.
    "Control flow topology" and "data flow cycles" are explicitly marked
    `# (future: implement ...)` (lines 367–371).
  - `validate_edge` has no rule limiting a control **outlet** to a single outgoing
    control edge.
- `EXEC` type (`barn/haybale-core/haybale_core/types/specs.py:215`) does not set
  `allow_multiple_links`, so multiplicity is left to the port default / builder.

### Open question / needs deeper trace
Is single-successor control fan-out *meant* to be illegal, or is fan-out actually
supported (parallel/sequential execution) and just mis-rendered here? The
`ControlFlowBuilder` behaviour with multiple control successors was not traced.
Decide the intended semantics first, then either:
- add an outlet-multiplicity rule in `validate_edge` / `_validate_edge` for
  `FlowType.CONTROL`, or
- implement the deferred "control flow topology" check in `validate_graph`.
