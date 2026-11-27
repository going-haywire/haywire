---
name: pooled-callback-delivery
description: an event node's Delivery setting chooses Every (broadcast) or Pooled; one emit carries all subscriber names, core forms a pool from that emit's pooled listeners, the next free member takes the next trigger, the emitter's Backlog bag sets the waiting room, and a frame's end frees its flow
status: accepted
see-also: ADR-0010, ADR-0064
level: framework
---

# Pooled callback delivery

**Context.**

- A callback is a broadcast. An emitter calls `emit_callback` once per subscriber name, and each listening Flow queues the trigger in its own `FlowQueue` (ADR 0010).
- Slow work can't be shared. A segmenter wired to two Transcribe flows gives both of them every clip, but the user wants each clip transcribed once, by whichever flow is free.
- Core can't tell that two emits belong to one event, because each emit names one listener (each event node listens under its own node id).
- No one outside `FlowQueue._run_one` knows when a frame ends.
- Issue #281. The owner decided this in the clip-player plan, round 3 (11 a, 12 b, 14 a, 15 a revised, 16 a), on 2026-11-27.

**Decision.**

- **D1** Pooled delivery is a delivery mode in core. It is not a callback type, so it works for every callback type (`CALLBACK`, `AUDIO_CALLBACK`, …).
- **D2** **The event node chooses.** `CallbackEvent` carries `delivery`, either `Delivery.EVERY` (the default, today's broadcast) or `Delivery.POOLED`. Like `queue_mode` it uses `kw_only` and `compare=False`. The node author sets it from core's `DeliverySettings` bag (one setting, *Delivery*), the same way ADR 0010 sets the queue mode. The emitter doesn't know how its events are distributed.
- **D3** **One emit carries all subscriber names.** `emit_callback` takes one name or a sequence of names. With a sequence, core splits the emit:
  - every *Every* listener gets the trigger in its own flow queue, exactly as a loop of single emits does today;
  - the *Pooled* listeners of that emit form its **pool**.
  
  Subscriptions, wiring and saved graphs don't change.
- **D4** **A pool's identity** is the emitter (the node that owns the Backlog bag passed with the emit) plus the set of its pooled listeners. Nobody declares a pool, and two emitters never share one. An emit without a Backlog bag forms its pool from the names alone, with the default backlog.
- **D5** **Busy and free are tracked per Flow, not per pool.** A pooled Flow is busy from the moment core hands it a trigger until that trigger's frame ends. A Flow that belongs to two pools still counts as busy once. On an emit, core gives the trigger to the next free member, in turn, in the emitter's subscriber order. When no member is free, the trigger waits in the pool's backlog. So a pooled Flow's own queue never holds more than the one trigger it runs, and its *Queue Mode* and *Max Queue Size* have no effect.
- **D6** **The emitter owns the backlog.** Core's `BacklogSettings` bag, which an emitter includes and passes with its emit, sets the backlog's **size** (default 16) and its **full rule**:
  - *Drop oldest* (default): the oldest waiting trigger makes room.
  - *Wait*: the emitting thread waits up to 5 s for room, then the new trigger is dropped, with a warning. The runner thread of a member's group never waits (ADR 0064 D6): its wait would hold the member it waits for, so it drops the new trigger at once. The runner of any other group waits like any other thread, as a `BLOCK` enqueue into another group does.
  
  A dropped trigger counts on the queue of the member whose turn it was, so the Flow meter shows it.
  
  An emitter with no pooled listeners ignores the bag.
- **D7** **A frame tells the pool when it ends.** `FlowQueue` reports every trigger it takes out of its queue to the callback manager: one that ran, one that failed, and one discarded at a stop or kill. The Flow then takes the oldest waiting trigger across its pools, or becomes free. A trigger the Flow's queue refuses, because its group is stopping, is dropped and the Flow becomes free.
- **D8** **Thread safety.** One lock in the callback manager guards pools, busy Flows, backlogs and the clearing of registrations. Core never calls into a `FlowQueue` while it holds that lock, so the lock order of ADR 0064 gains only a leaf.
- **D9** Stopping and recompiling drop every pool and backlog, together with the callback registrations.
- **D10** Execution groups don't change (ADR 0064). Pooled Flows that share a control node are in one group, and they still run one after the other.

**Considered.**

- *A pooled callback type* (11 b): every callback type would need a pooled twin, and a single listener could no longer choose.
- *The emitter chooses* (12 a): it can't express a mix, such as two Transcribe flows that share clips next to a Recorder that keeps every clip.
- *The callback named after the emitter* (16 b): it would change the subscription mechanism for every emitter and event node, `POOLED[...]` inlets and saved graphs included.
- *Backlog from the members' queue settings* (15 b): members could disagree, so a compile warning would be needed. The emitter is also the one that knows how fast it produces events and how much it can lose.
- *No shared backlog, shortest queue wins*: a trigger could wait behind a long frame while another member sits idle.
- *A pool name* (14 b): one emitter could feed several separate pools. It can be added later without breaking anything.

**Consequences.**

- Existing graphs behave as before. *Every* is the default, and a sequence emit to *Every* listeners enqueues the same triggers in the same order as the loop it replaces.
- An emitter that still emits one name at a time gives each pooled listener a pool of its own. Delivery stays correct, but no work is shared until the emitter passes all its names in one emit.
- Pooled triggers lose their order across members: two members finish in whatever order their frames take.
- A pooled listener's *Queue Mode* and *Max Queue Size* don't apply while it is pooled.
