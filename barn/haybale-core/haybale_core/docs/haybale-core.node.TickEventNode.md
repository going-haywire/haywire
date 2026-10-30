# Tick

`haybale-core:node:TickEventNode` · kind: node

Triggered by a connected emitter (Tick Emit, Run Button)

## Ports

| id | direction | type | description |
|---|---|---|---|
| `listen_callback` | outlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |
| `exec` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `delta_time` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

Runs its flow each time a connected emitter triggers it.

Connect the `Listen` outlet to the `Trigger` inlet of a Tick Emit (periodic
ticks) or a Run Button (one trigger per press).

Outputs:
    exec: Control flow
    delta_time: Time since the emitter's previous trigger (seconds)
