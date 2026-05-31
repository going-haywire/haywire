# Inject the validation debounce scheduler instead of hardcoding `threading.Timer`

`ValidationManager` (haywire-core) debounces graph validation: a burst of `mark_*_dirty` calls (a drag emitting many `NODE_MOVED`, a multi-node delete) is coalesced into a single `_validate_batch` pass. That debounce was implemented with a raw `threading.Timer`. This ADR replaces the hardcoded timer with an injected `ValidationScheduler`, so the *application* — not pure core — decides which thread the validation pass runs on. The default stays the legacy timer; the studio injects an event-loop scheduler.

## The problem the timer caused

`_validate_batch` runs on whatever thread fires the timer. With `threading.Timer` that is a background daemon thread, ~50 ms after the mutation. But `_validate_batch` notifies its subscribers inline, and those subscribers touch the UI:

- the graph canvas redraw (`visual_layer.on_validated`), and
- `HaystackState._on_entry_validation`, which sets `entry.unsaved = True` and **broadcasts `GraphDataMutated`** through the session signal bus.

The signal bus is documented as main-thread-only (*"Not thread-safe by design — all session work runs on the NiceGUI event loop's main thread"*). So the dirty-state broadcast that drives the header dirty dot and the undo/redo button enablement was being emitted from a thread the UI layer says it cannot be emitted from.

In practice NiceGUI tolerates this: building elements off-loop lands in the no-task slot stack (`Slot.stacks[0]`), and `element.update()` enqueues into the outbox, which the main-loop poll flushes within ≤1 s. So the canvas visibly updated and nothing crashed — which is exactly why the off-thread-ness went unnoticed. But the tolerance is fragile and adds up to ~1 s of latency, because the cross-thread `asyncio.Event.set()` that *should* wake the outbox immediately is not called thread-safely.

The key realization: **the timer was never a concurrency mechanism — it was only a debounce.** `_validate_batch` is pure synchronous CPU work (`build()`, `link()`, `_housekeeping()`) with no `await`, no I/O, and no concurrency requirement. Validation is triggered *only* by user edits, which originate on the main loop (the execution interpreter does not mark the graph dirty during a run). Running it on a background thread bought nothing and cost the thread-safety hazard above.

## Why injection, not "just marshal the broadcast"

The narrow fix would have been to wrap the one off-thread emitter (`HaystackState._broadcast_data_mutated`) in `loop.call_soon_threadsafe`. Rejected as the primary fix because it treats a symptom:

- it leaves `_validate_batch` and the canvas redraw on the timer thread, so the *next* off-thread subscriber re-introduces the same class of bug;
- it scatters event-loop awareness into `HaystackState`, which has no business knowing about asyncio loops;
- it fixes the signal path but not the canvas path.

Moving the debounce onto the event loop fixes the root cause once, for every current and future subscriber, and keeps loop-awareness in exactly one place.

## Why inject, not import NiceGUI into core

`ValidationManager` lives in `haywire-core`, which is deliberately framework-free — it has **zero** NiceGUI imports today. The alternative of importing `nicegui.core` directly into `ValidationManager` (to call `call_soon_threadsafe` / `ui.timer`) would invert that dependency: pure graph-validation logic would depend on the web UI framework.

Injection preserves the boundary. Core defines a tiny protocol and a default; the application supplies the loop-aware implementation:

- **`ValidationScheduler`** protocol (core): `schedule(delay_seconds, fn) -> handle`, where the handle has an idempotent `cancel()`. Re-scheduling is the caller's job — `ValidationManager` cancels the previous handle and schedules a fresh one on every dirty mark, which is what produces the debounce.
- **`ThreadingTimerScheduler`** (core): the legacy daemon-`threading.Timer` behavior, kept as the **default** so every construction site that does not inject behaves exactly as before. This change is therefore behavior-preserving by default.
- **`SyncScheduler`** (core): runs the callback inline. Deterministic; intended for tests and headless use, where it removes the need to call `force_immediate_validation()` after a mutation.
- **`LoopScheduler`** (haybale-studio, where NiceGUI is permitted): debounces on `nicegui.core.loop`. The live graph factory (`HaystackState._make_graph_and_editor`) injects it, which is what moves validation and the `GraphDataMutated` broadcast onto the main thread in the running app.

## Why `LoopScheduler` lives in `haybale-studio`

It needs `nicegui.core.loop`, so it cannot live in core. `haybale-haystack` (which owns the live graph factory) already depends on `haybale-studio` and already imports NiceGUI, so placing the scheduler there is reachable from the one construction site that matters without adding a new dependency edge.

`LoopScheduler` handles two realities the protocol implies:

- **Off-loop callers.** `schedule` may be invoked from a non-loop thread (a hot-reload watcher marking nodes dirty via `NODE_HOT_RELOADED`). `call_later` is loop-affine, so it hops via `call_soon_threadsafe` first. The returned handle is cancellable from any thread, and cancellation that races the deferred arming is resolved under a lock.
- **No loop yet.** During pre-`ui.run` startup (workspace rehydrate constructs graphs before the loop exists) it runs the callback inline. Safe, because validation is pure CPU work; it only forgoes debouncing for that early window.

## The synchronous-reentrancy subtlety

`SyncScheduler.schedule` runs `_validate_batch` *inside* the `schedule()` call, re-entrant under the manager's `RLock`. That batch clears `_pending_handle`, but then `_schedule_validation` would overwrite it with the (inert) handle the scheduler returned — leaving `pending_validation` reporting `True` when nothing is pending. `ValidationManager` guards this with a monotonic `_batch_generation` counter: it snapshots the generation before scheduling and only adopts the returned handle if the generation did not advance during `schedule()` (i.e. no inline batch ran). This keeps the synchronous path honest without special-casing scheduler types.

## Considered alternatives

- **Marshal only `_broadcast_data_mutated` with `call_soon_threadsafe`.** Smallest diff, but symptom-level — see "Why injection, not just marshal the broadcast" above.
- **Import `nicegui.core` directly into `ValidationManager`.** Couples pure-core validation to the web framework, inverting a boundary the codebase otherwise holds (core has no NiceGUI imports). Rejected.
- **Replace the debounce with a loop-native `ui.timer` everywhere, no abstraction.** Forces a NiceGUI dependency on every `BaseGraph` construction, breaking headless/test/CI use that has no running loop.
- **Move the debounce up to the edit layer (coalesce drag deltas before they reach the graph) and make validation purely synchronous.** Arguably the cleanest end state, but a larger rethink of the edit→graph boundary; deferred.

## Consequences

- `BaseGraph(..., validation_scheduler=None)` and `ValidationManager(..., scheduler=None)` gain an optional parameter; omitting it preserves the prior `threading.Timer` behavior exactly.
- The live app (graphs created through `HaystackState`) now validates on the event-loop thread, so the header dirty dot and undo/redo enablement update promptly and on the correct thread. This pairs with the `GraphEditor` change that adds `@react_on(GraphDataMutated)` — the scheduler delivers the signal safely; the `react_on` handler is what makes the editor chrome listen for it.
- Tests may construct graphs with `SyncScheduler()` for deterministic, inline validation. Existing tests that call `force_immediate_validation()` to flush the timer continue to work; sweeping them onto `SyncScheduler` is possible follow-up cleanup, intentionally not done here.
- `ValidationManager.get_statistics()["pending_validation"]` now means "a debounced run is pending" derived from the handle, not from `threading.Timer.is_alive()`.
