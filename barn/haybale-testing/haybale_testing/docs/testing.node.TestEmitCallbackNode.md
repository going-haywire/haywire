# Test Emit Callback

`testing:node:TestEmitCallbackNode` · kind: node

Test version of EmitCallback — emits a callback to trigger event nodes

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

Test-only control node that emits a named callback.
