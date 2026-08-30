# Tick

`haybale-core:node:TickEventNode` · kind: node

Triggered periodically by a connected TickEmitNode

## Ports

| id | direction | type | description |
|---|---|---|---|
| listen_callback | outlet | haybale-core:type:CALLBACK | Signal for callback execution between nodes |
| exec | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| delta_time | outlet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

Listens for tick callbacks from a connected TickEmitNode.

Connect the callback outlet to a TickEmitNode's callback inlet
to receive periodic tick events.

Outputs:
    exec: Control flow
    delta_time: Time since last tick (seconds)
