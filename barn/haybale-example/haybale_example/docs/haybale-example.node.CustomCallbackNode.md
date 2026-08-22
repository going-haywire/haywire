# Custom Callback

`haybale-example:node:CustomCallbackNode` · kind: node

Listens for custom callbacks from other flows

## Ports

| id | direction | type | description |
|---|---|---|---|
| mode_switch | config | haybale-core:type:GROUP | Inlet group |
| custom_callback_name | config | haywire-core:type:STRING | Text data |
| thread_mode | config | haywire-core:type:STRING | Text data |
| listen_callback | outlet | haybale-core:type:CALLBACK | Signal for callback execution between nodes |
| triggered | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| payload | outlet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

Listens for custom callbacks from other flows.

Config:
    callback_name: Name of the callback to listen for

Outputs:
    triggered: Control flow when callback received
    payload: Data from callback
