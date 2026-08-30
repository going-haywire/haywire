# Begin Player

`haybale-core:node:BeginPlayNode` · kind: node

Triggered once when execution starts

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| timestamp | outlet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

Triggered once when execution starts.

Outputs:
    exec: Control flow
    timestamp: Time when execution began
