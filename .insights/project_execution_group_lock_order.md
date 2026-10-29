# Execution groups: lock order and the deferred restart

Execution runs one runner thread per **execution group** (flows sharing a control node). Four locks meet on those threads and on the validation thread; ADR 0064 has the design.

## The order

**group hold → `NodeWrapper.exec_lock` → validation lock → `NodeWrapper._lock`**

- **A runner never waits for a hold.** `Interpreter.hold_for_batch()` returns `False` on its own runner threads, and `ValidationManager._validate_batch` takes no hold when the current thread already owns the validation lock (a `SyncScheduler` validates inline inside `mark_*_dirty`; `force_immediate_validation` runs under the lock). Both cases would wait for a frame that may need the very lock being held — a worker marking a node dirty takes the validation lock.
- **A holder never holds the validation lock while it waits.** `_validate_batch` checks "is this structural?" under the lock, *drops* it, holds the groups, then re-enters. Don't fold the hold inside the `with self._validation_lock:` block.
- **One `exec_lock` per thread at a time.** Only the VM calls `_execute`, and a data node's worker never executes another node. `call_startup`/`call_shutdown` take one node's `exec_lock` at a time. Validation never takes an `exec_lock`.

## Why stop/restart is deferred (`call_soon`)

Validation subscribers run *inside* the batch, under the validation lock. Haystack's autorestart used to call `stop_execution()` there; stopping waits for runner threads, and a running frame may need the validation lock → deadlock. `_on_entry_validation` now schedules the restart with `graph._validation.call_soon(...)`, which runs after the batch returns. A test that drives `_on_entry_validation` with a `MagicMock` graph must make `call_soon` run inline (`side_effect = lambda fn: fn()`), or it sees no stop at all.

## A stop's kill and the shared data node

A stop that times out kills its group (`ExecutionGroup.stop` → `kill`). A group killed while another group is stuck inside a shared data node must not block on that node's `exec_lock` — not in its frame (`_exclusive` gives up when `exec_ctx.cancel` is set) and not in `call_shutdown` (the node is skipped and stays retained, so it gets no `on_shutdown`). Symptom of getting it wrong: stopping abandons *both* groups instead of only the stuck one.
