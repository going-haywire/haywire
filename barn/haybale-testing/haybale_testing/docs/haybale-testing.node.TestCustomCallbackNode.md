# Test Custom Callback

`haybale-testing:node:TestCustomCallbackNode` · kind: node

Test version of CustomCallback — listens for named callbacks

## Ports

| id | direction | type | description |
|---|---|---|---|
| mode_switch | config | haybale-core:type:GROUP | Inlet group |
| custom_callback_name | config | haywire-core:type:STRING | Text data |
| thread_mode | config | haywire-core:type:STRING | Text data |
| queue_mode | config | haywire-core:type:STRING | Text data |
| listen_callback | outlet | haybale-core:type:CALLBACK | Signal for callback execution between nodes |
| triggered | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| payload | outlet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

Test-only event node that listens for custom callbacks.
