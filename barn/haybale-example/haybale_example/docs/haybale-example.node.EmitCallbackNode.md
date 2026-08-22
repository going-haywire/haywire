# Emit Callback

`haybale-example:node:EmitCallbackNode` · kind: node

Emits a callback to trigger event nodes in other flows

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| sequential_mode | inlet | haywire-core:type:BOOL | Sequential Mode - if multiple callbacks, emit in sequence |
| payload | inlet | haywire-core:type:FLOAT | Decimal numberer |
| edge_callback | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| mode_switch | config | haybale-core:type:GROUP | Inlet group |
| custom_callback_name | config | haywire-core:type:STRING | Text data |
| exec | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Emits a callback to trigger event nodes in other flows.

Inputs:
    execute: Control flow in
    callback_name: Name of callback to emit
    payload: Data to send with callback

Outputs:
    exec: Control flow out
