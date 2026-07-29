# Test Custom Callback

`testing:node:TestCustomCallbackNode` · kind: node

Test version of CustomCallback — listens for named callbacks

## Ports

| id | direction | type | description |
|---|---|---|---|
| mode_switch | config | core:type:GROUP | Inlet group |
| custom_callback_name | config | builtin:type:STRING | Text data |
| thread_mode | config | builtin:type:STRING | Text data |
| queue_mode | config | builtin:type:STRING | Text data |
| listen_callback | outlet | core:type:CALLBACK | Signal for callback execution between nodes |
| triggered | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| payload | outlet | builtin:type:FLOAT | Decimal numberer |

## Notes

Test-only event node that listens for custom callbacks.
