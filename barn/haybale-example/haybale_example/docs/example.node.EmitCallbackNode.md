# Emit Callback

`example:node:EmitCallbackNode` · kind: node

Emits a callback to trigger event nodes in other flows

## Ports

| id | direction | type | description |
|---|---|---|---|
| execute | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| sequential_mode | inlet | builtin:type:BOOL | Sequential Mode - if multiple callbacks, emit in sequence |
| payload | inlet | builtin:type:FLOAT | Decimal numberer |
| edge_callback | inlet | core:type:PooledType | Multi-source aggregation |
| mode_switch | config | core:type:GROUP | Inlet group |
| custom_callback_name | config | builtin:type:STRING | Text data |
| exec | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Emits a callback to trigger event nodes in other flows.

Inputs:
    execute: Control flow in
    callback_name: Name of callback to emit
    payload: Data to send with callback

Outputs:
    exec: Control flow out
