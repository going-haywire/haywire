# Carry queue mode on the EventSource so a flow can drop stale triggers (realtime)

A live `camera → estimator → annotate` pipeline lags behind realtime: the camera emits frames faster than synchronous inference consumes them, and the displayed frame falls progressively behind. The frames are not buffered in any node — they queue in the **flow scheduler's** trigger queue. The scheduler already supports two queue modes (`QueueMode.BLOCK`, `QueueMode.DROP`), but `queue_mode` was **hardcoded to `BLOCK`** at the one place schedulers are built (`Interpreter._register_flow`, `interpreter.py:218`), so no node, library, or setting could select DROP. This ADR makes the mode selectable **per EVENT node**, carried on the node's `EventSource`, defaulting to `BLOCK` everywhere except the camera `Frame Event` node.

## The problem the hardcoded BLOCK caused

Per emitted frame: the producer (an EMIT node's capture thread) calls `context.emit_callback(name, payload)` → `CallbackManager.emit_callback` builds a `Trigger` and enqueues it into the subscribing flow's scheduler (`callback_manager.py:98`). In `BLOCK` mode the scheduler's `enqueue_trigger` does `put(block=True, timeout=5.0)` against a `Queue(maxsize=100)` (`scheduler.py:72,118`). So while inference is mid-frame, up to 100 frames pile up and are processed in order — the displayed frame is whatever was captured up to 100 frames ago. That backlog *is* the lag.

`QueueMode.DROP` already does the desired thing — when the flow is executing, an incoming trigger is dropped instead of queued (`scheduler.py:111-113`) — it was simply unreachable.

## Why the decision lives on the EVENT node, not the graph run or the EMIT node

A scheduler is owned by exactly one **Flow**, and a Flow is assembled from exactly one **EVENT node** (`flow_assembly_manager.py:190-214`). Queue mode is a property of *that scheduler's* relationship to its triggers, so the EVENT node is where ownership naturally sits — the resource owner decides.

Two alternatives were rejected:

- **Per-graph-run** (a single toggle on `GraphRunSettings`, threaded through `GraphEntry.build()`). Too coarse: one graph can hold both a camera flow (wants DROP) and a batch/data flow (must keep BLOCK — every trigger matters). A graph-wide switch cannot express that.
- **EMIT node owns it** (the producer declares "my frames are droppable"). The intuition is real — a camera *knows* its frames are stale-able — but one EMIT node fans out to many EVENT nodes (`tick_emit.py:116-121`), so "emit decides" means a producer reaching across to set N consumers' scheduler modes, with conflicts when two emitters target one event node. Ownership must follow the resource (the scheduler), which is the EVENT node.

## Why the value rides on `EventSource`, not a separate node config surface

`_assemble_flow` already reads `event_node.event_subscription` (an `EventSource`) and that object already governs scheduler wiring through `get_subscription_key()`. Queue mode is the *same category of fact* — "how the scheduler should treat this subscription" — so co-locating it on `EventSource` means the assembly path reads **one** object for everything scheduler-related, rather than reading the subscription for the key and a separate config port for the mode.

This also cleanly separates two roles:

- **The node author** decides *how the value is set* — a `SwitchWidget`/`SelectWidget` config port, a `NodeSettings` field, a fixed literal, or computed state — and writes the result into the `EventSource` it constructs in `post_init`.
- **The framework** only ever reads typed fields off `EventSource`. It does not care how the author decided. Assembly becomes a dumb passthrough: `EventSource` → `Flow` → `FlowScheduler`.

The fields are declared on **`CallbackEvent`** (the callback-driven subscription cameras/ticks use), **not** the base `EventSource`. Putting defaulted fields on the base would force the base to become a `@dataclass` and collide with `CallbackEvent.event_name`, which has no default (Python forbids a non-default field after a defaulted one without `kw_only`). On `CallbackEvent` the field ordering is naturally legal. `SystemEvent`/`ExternalEvent` do not carry the fields; `_assemble_flow` reads them with a `getattr(..., QueueMode.BLOCK)` fallback, which is exactly the safe default for `shutdown`/`begin_play`.

```python
@dataclass(frozen=True)
class CallbackEvent(EventSource):
    event_name: str
    queue_mode: QueueMode = field(default=QueueMode.BLOCK, compare=False)
    max_queue_size: int = field(default=100, compare=False)
```

The fields are `compare=False` so backpressure is *carried* by the frozen `EventSource` without participating in its identity/hash — two Frame Event nodes differing only in queue mode must still produce key-stable, hashable subscriptions (the subscription key is `callback:{node_id}`, already unique, so routing is unaffected).

## Why DROP carries `max_queue_size`, and why the author sets the pair

`_is_executing` is set *inside* `_execute_flow`, after the thread pulls from the queue. DROP therefore drops triggers only *while a frame is mid-execution*; in the gap between finishing frame N and the next blocking `get()`, `_is_executing` is briefly clear and DROP's `put(block=False)` will enqueue into a queue of `max_queue_size` (default 100). **DROP alone does not guarantee "always newest"** — it needs a shallow queue. So the camera node ships `DROP` with `max_queue_size=1`.

Both `queue_mode` and `max_queue_size` are carried as independent fields (mirroring `FlowScheduler.__init__`, `scheduler.py:54-55`) rather than the framework *deriving* size from mode. The footgun of two independent knobs (an operator picking `DROP` + `100` and reconstructing the lag) is closed by **who sets them**: the *node author* sets the pair in `post_init` as one deliberate, tested combination; the operator never sees `max_queue_size`. This keeps assembly a pure passthrough and lets a different node legitimately choose `DROP` + a 2-deep jitter buffer without fighting a hardcoded rule.

## Why BLOCK is left exactly as-is (and is not made lossless)

Today's `BLOCK` is *block up to 5 s, then drop and warn* (`scheduler.py:118,128-130` — `queue.Full` after the timeout returns `False`). It is **not** a lossless "process every frame" guarantee. The temptation was to redefine `BLOCK` as unbounded backpressure (no timeout) so it never drops, giving offline pipelines a completeness guarantee.

Rejected. True offline completeness is met by a **separate, demand-driven pattern** — the EVENT flow's completion signal (`trigger.payload["_on_complete"]`, `scheduler.py:251-258`) triggers the EMIT node to produce the next frame: one frame in flight, no queue, lossless by construction. That is a *node behavior*, not a scheduler queue mode, and it is out of scope here. Consequently `BLOCK` and its 5 s timeout are untouched, and this change defines exactly two modes with honest meanings: **DROP** = newest-only, lossy by design; **BLOCK** = best-effort, 5 s-then-drop.

## Why the camera `Frame Event` node defaults to DROP

`BLOCK` remains the default for *every other* event source — flipping the global default to DROP would silently start dropping triggers in every batch/data flow, which is unacceptable. The exception is `NumpyFrameEventNode` (`Frame Event`), whose entire reason to exist is realtime camera work; its author default is `DROP` + `max_queue_size=1`. The every-frame camera case (recording/capture) is explicitly redirected to the demand-driven pattern above, not to BLOCK on this node.

This means existing graphs using `NumpyFrameEventNode` change behavior on upgrade (they begin dropping). That is the intended fix for the node's primary use; graphs that need every frame move to the demand-driven pattern.

## When and by whom the value is read

Once, at **graph-assembly time** — not per frame. `Interpreter.load_and_assemble_graph` calls `assemble_graph` (→ `_assemble_flow` per event node, `flow_assembly_manager.py:190`) and *then* `_register_flow` per flow (`interpreter.py:126-132`):

- `_assemble_flow` reads `getattr(event_node.event_subscription, "queue_mode", QueueMode.BLOCK)` (and `max_queue_size`) and stores them on the `Flow` it builds.
- `_register_flow` passes `flow.queue_mode` / `flow.max_queue_size` into `FlowScheduler(...)`, replacing the hardcoded `QueueMode.BLOCK` / implicit 100.

The scheduler never reads the node; nothing reads the value per-frame. Changing the mode in the UI takes effect on the next assembly (graph restart / reassembly), which is correct — a scheduler's queue mode is fixed for its lifetime.

## Considered alternatives

- **Per-graph-run toggle on `GraphRunSettings`.** Too coarse for mixed camera+batch graphs. Rejected (see above).
- **EMIT node owns the mode.** Producer→N-consumer fan-out creates conflicting opinions over a scheduler the producer does not own. Rejected.
- **A config port / `NodeSettings` field as the storage of record.** Workable, but scatters scheduler config across the node surface; `EventSource` already owns the scheduler relationship. The config/settings surface remains the author's *choice of input mechanism*, feeding the `EventSource`, not the canonical store.
- **Derive `max_queue_size` from mode in the framework.** Bakes one node's tuning into core and forbids legitimate variants (DROP + small jitter buffer). Rejected in favor of author-set pairs.
- **Redefine BLOCK as unbounded/lossless.** Offline completeness belongs to the demand-driven emit↔event handshake, not to a queue mode. Rejected; BLOCK untouched.
- **A latest-wins / coalescing queue** (new queue type that overwrites the pending trigger). Strictly correct "always newest," but the largest blast radius in the hottest concurrency path; `DROP` + `max_queue_size=1` is close enough without a new queue type. Deferred.

## Consequences

- `CallbackEvent` gains `queue_mode` and `max_queue_size` (both `compare=False`); omitting them preserves prior behavior (`BLOCK` / 100) exactly. Subscription keys and hashing are unchanged.
- `Flow` carries `queue_mode` / `max_queue_size`; `_assemble_flow` populates them, `_register_flow` consumes them. The hardcoded `QueueMode.BLOCK` at `interpreter.py:218` is removed.
- `NumpyFrameEventNode` now defaults to realtime DROP; existing graphs using it drop stale frames after upgrade.
- BLOCK semantics (5 s-then-drop) are unchanged; true offline completeness remains a future demand-driven pattern, out of scope.
- `QueueMode` stays where it is (`scheduler.py:31`); `event_source.py` imports it directly. **Verified no import cycle**: `scheduler.py`'s only haywire imports are `TYPE_CHECKING`-only (no runtime edge back to `event_source`), and the package `__init__.py` imports `scheduler` *before* `event_source`, so `QueueMode` is fully defined by the time `event_source` loads. (Confirmed empirically by adding the real top-level import and loading the module — clean.) No neutral-module relocation needed.
