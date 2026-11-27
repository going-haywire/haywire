# Pooled callback delivery — plan

Issue #281 · ADR [0097](../../docs/adr/0097-pooled-callback-delivery.md) · branch `feat/pooled-delivery`.
Decided by the owner on 2026-11-27 (clip-player plan, round 3): 11 a, 12 b, 13 a, 14 a, 15 a revised, 16 a.
This plan's decisions: 1 a (`emit_callback` takes a name or a list), 2 a (Drop oldest, Wait), 3 a (Backlog bag on Tick Emit, Run Button, the emit probe), 4 a (Delivery on every callback event node here), 5 a (`Delivery`, `DeliverySettings`, `BacklogSettings`, `BacklogFull`).

## Today

- [callback_manager.py:70](../../packages/haywire-core/src/haywire/core/execution/callback_manager.py#L70)
  `emit_callback(event_name, payload)` builds one `Trigger` and enqueues it in every Flow registered under that name.
- [interpreter.py:287](../../packages/haywire-core/src/haywire/core/execution/interpreter.py#L287) `_register_flow` builds the
  `FlowQueue` from the subscription's `queue_mode` / `max_queue_size` and registers `CallbackEvent` Flows (`:314`).
  `_cleanup_current_graph` clears them (`:344`).
- [flow_queue.py:159](../../packages/haywire-core/src/haywire/core/execution/flow_queue.py#L159) `_run_one` runs one
  frame and tells no one. `_discard_pending` (`:171`) empties the queue at stop or kill
  ([execution_group.py:203](../../packages/haywire-core/src/haywire/core/execution/execution_group.py#L203), `:279`).
- [event_source.py:119](../../packages/haywire-core/src/haywire/core/execution/event_source.py#L119) `CallbackEvent`
  carries `queue_mode` / `max_queue_size` (ADR 0010).
- Emitters loop over their names:
  [emitter.py:91](../../barn/haybale-audio/haybale_audio/emitter.py#L91) (`deliver_to_subscribers`: File Player, Device In,
  Audio Clock, Resample, Reblock), [tick_emit.py:131](../../barn/haybale-core/haybale_core/nodes/emits/tick_emit.py#L131),
  [run_button.py:111](../../barn/haybale-core/haybale_core/nodes/emits/run_button.py#L111),
  [callback_emit.py:95](../../barn/haybale-example/haybale_example/nodes/emits/callback_emit.py#L95),
  [callback_emit_probe.py:79](../../barn/haybale-testing/haybale_testing/nodes/testbed/callback_emit_probe.py#L79).
- Precedent for a core settings bag that nodes include: `ProgressSettings`
  ([progress.py:51](../../packages/haywire-core/src/haywire/barn/builtin/progress.py#L51)), exported from `haywire.api`.

## Changes

**Core.**

- `haywire/core/execution/delivery.py` (new): `Delivery` (`EVERY`, `POOLED`) and `BacklogFull` (`DROP_OLDEST`, `WAIT`).
  `QueueMode` lives in `flow_queue.py`, and this module stays as free of imports as that one.
- `event_source.py`: `CallbackEvent.delivery: Delivery = EVERY`, with `kw_only` and `compare=False`, as `queue_mode` has.
- `haywire/barn/builtin/delivery.py` (new): `DeliverySettings` (one CHOICES setting, *Delivery*: Every / Pooled,
  `promotable=CONFIG`, "applies on the next start") and `BacklogSettings` (*Backlog Size* INT 1–1024, default 16;
  *When Full*: Drop oldest / Wait). Each has a typed reader (`DeliverySettings.mode`, and for the backlog the size, the
  rule and the owning node's id). Both are exported from `haywire.api`.
- `execution_context.py:59`, `vm.py:478` and `callback_manager.py:70`: `emit_callback(event_name: str | Sequence[str],
  payload=None, backlog: BacklogSettings | None = None)`.
- `callback_manager.py`:
  - **Every.** For each name, in order: one `Trigger(source_key=f"callback:{name}")` per name enqueued in every *Every*
    Flow, as today. Statistics stay per name.
  - **Pooled.** The pooled Flows of the emit, in name order, make the pool key `(backlog owner id or None,
    frozenset(flow ids))`. The pool is created on first use and keeps its round-robin index, its backlog (a `deque` of
    `(seq, payload, timestamp)`) and its dropped count.
  - `_busy: set[Flow]` and `_pools_of: dict[Flow, list[_Pool]]`.
  - On emit, under the lock: the next free member after the last one picked is marked busy. If none is free, the
    trigger is appended to the backlog, and the full rule applies when the backlog is full. Once the lock is released,
    the trigger is enqueued in the picked member's queue.
  - `trigger_done(flow)`, called by `FlowQueue`: under the lock, take the oldest backlog head (lowest `seq`) across the
    Flow's pools, or mark the Flow free. Outside the lock, enqueue it. If `enqueue_trigger` returns `False` (the group is
    stopping), the trigger is dropped and the Flow is marked free.
  - `clear_callbacks()` also clears pools, busy Flows and backlogs, and wakes any emitter that is waiting.
  - `get_statistics()` gains `pools`: members, busy, waiting and dropped.
- `flow_queue.py`: `on_done: Callable[[Flow], None] | None`, called once for every trigger taken out of the queue: in
  `_run_one`'s `finally` after `task_done` (an error is covered too, since `_execute_flow` catches it), and from
  `_discard_pending` once per discarded trigger, after `_queue_lock` is released. `_register_flow` sets it to
  `callback_manager.trigger_done` for Flows whose `CallbackEvent.delivery` is `POOLED`. The DROP replace path never
  meets a pooled Flow, because core hands it one trigger at a time.

**How a frame's end is reported.** The runner thread ends the frame → `FlowQueue._run_one` `finally` → `on_done(flow)` →
`CallbackManager.trigger_done` → the next waiting trigger goes into that Flow's queue → `group.post` → the same runner
picks it up in FIFO order with the group's other tokens.

**Thread safety.**

- One `threading.Lock` in `CallbackManager`, and a `Condition` on it for *Wait*. It guards pools, `_busy`, `_pools_of`
  and backlogs.
- `enqueue_trigger` is never called while that lock is held, so the lock is a leaf in ADR 0064's lock order.
- Emits come from runner threads, node threads (Tick Emit, `BlockPump`) and the Run Button thread.
- *Wait* blocks only a thread that isn't a runner (`group.is_runner_thread()` of any registered group, ADR 0064 D6),
  for up to 5 s (a constructor argument, so tests can shorten it). After that the new trigger is dropped with a warning.
- Registration happens before the groups start, and `clear_callbacks` after they stop, as today.

**A full backlog.**

- *Drop oldest*: pop the head, count it as dropped, append the new trigger.
- *Wait*: off a runner thread, wait on the condition until `trigger_done` frees room, or the deadline passes, or
  `clear_callbacks` runs. Then append the trigger, or drop it. On a runner thread, drop the new trigger with a warning.
- Dropped counts show in `get_statistics()["callbacks"]["pools"]`.

**Libraries.**

- Every callback event node in this repo gains `delivery = bag(DeliverySettings)` and passes it into its
  `CallbackEvent`: Tick Event, Audio Event, Image Event, the example Callback Event and Merged Callback Event, and the
  testing Callback Event Probe and Record Callback probes.
- Every emitter here passes all its names in one emit: `deliver_to_subscribers`, Tick Emit, Run Button, Callback Emit,
  and the emit probes.
- Tick Emit, Run Button and the Callback Emit Probe gain `backlog = bag(BacklogSettings)` (decision 3).

**Docs.**

- [callbacks-arch.md](../../docs/architecture/execution/callbacks/callbacks-arch.md): a *Delivery* section and §3.2
  dispatch.
- [ports.md:331](../../docs/guides/ports.md#L331): the `emit_callback` row.
- [node-roles.md](../../docs/guides/node-roles.md): the callback event pair.
- `node-canon.md`: event nodes and `DeliverySettings`.
- Glossary: *Delivery*, *Pool*, *Backlog*.
- `uv run haywire docs --all` for the changed libraries.
- ADR 0097 goes to `accepted` with the PR.

## Tests

`tests/core/test_execution/test_pooled_delivery.py` (new):

- Unit tests on `CallbackManager` with real `FlowQueue`s and stub groups:
  - a sequence emit to *Every* listeners enqueues the same triggers, in the same order, as a loop of single emits;
  - two pooled members and four emits: two run, two wait; each frame end hands over the next; the turn alternates;
  - *Every* and *Pooled* mixed on one emit;
  - *Drop oldest* counts drops and keeps the newest;
  - *Wait* waits, then drops after the (shortened) timeout;
  - on a runner thread it never waits;
  - a Flow in two pools is busy once and takes the oldest head;
  - a frame that raises still frees its Flow;
  - discard at stop frees; enqueue refused while stopping frees;
  - `clear_callbacks` empties pools and wakes a waiter.
- Integration through the `Interpreter` with the testing probes:
  - one emitter, two pooled listeners with a slow worker, one *Every* listener, N emits: each trigger runs exactly once
    across the pool, both members run, and the *Every* listener runs N times;
  - two threads emitting concurrently: exactly once, nothing lost under *Wait*.
- `test_run_button.py`: two pooled Tick Events take one press each.
- `FlowQueue`: `on_done` is called after a raising frame and per discarded trigger.
- The existing execution, audio and image tests stay green unchanged. That is the check that *Every* doesn't change.

Commands:

- `uv run pytest tests/core/test_execution tests/audio tests/image tests/barn`
- `uv run mypy`
- `uv run ruff check`
- `uv run ruff format --check`

## Status

| Step | State |
|---|---|
| Issue #281 | filed |
| ADR 0097 | accepted with the PR |
| Plan | decided 2026-11-27: 1 a · 2 a · 3 a · 4 a · 5 a |
| Implementation | done; tests in `test_pooled_delivery.py` |
| Review (lead) | findings 1–8 fixed; owner 3 a (Record Emit Probe: one emit, Backlog bag), 4 a (Backlog bag on every emitter here, audio and Callback Emit included) |
