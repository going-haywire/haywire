# Begin Player

`core:node:BeginPlayNode` · kind: node

Triggered once when execution starts

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| timestamp | outlet | builtin:type:FLOAT | Decimal numberer |

## Notes

Triggered once when execution starts.

Outputs:
    exec: Control flow
    timestamp: Time when execution began
