# Merge Callback

`example:node:MergeCallbackNode` · kind: node

Listens for a specified number of callbacks from other flows

## Ports

| id | direction | type | description |
|---|---|---|---|
| custom_callback_count | config | builtin:type:INT | Whole number |
| listen_callback_1 | outlet | core:type:CALLBACK | Signal for callback execution between nodes |
| triggered | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| payload_1 | outlet | builtin:type:FLOAT | Decimal numberer |

## Notes

Listens for a specified number of callbacks from other flows.

Config:
    callback_name: Name of the callback to listen for

Outputs:
    triggered: Control flow when callback received
    payload: Data from callback
