# Tick Event

`haybale-core:node:TickEventNode` · kind: node

Triggered by a connected emitter (Tick Emit, Run Button)

## Ports

| id | direction | type | description |
|---|---|---|---|
| `listen_callback` | outlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |
| `exec` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `delta_time` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `mode` | delivery | `'Every'` | Every runs this flow for every event. Pooled shares the events with the other pooled listeners of the same emitter: the next free one runs each event. |

## Notes

Runs its flow each time a connected emitter triggers it.

Connect the `Listen` outlet to the `Trigger` inlet of a Tick Emit (periodic
ticks) or a Run Button (one trigger per press).

Delivery: `Every` runs the flow for every trigger. `Pooled` shares the triggers
with the emitter's other pooled listeners: the next free one runs each trigger,
and the emitter's Backlog holds them while all are busy.

Outputs:
    exec: Control flow
    delta_time: Time since the emitter's previous trigger (seconds)
