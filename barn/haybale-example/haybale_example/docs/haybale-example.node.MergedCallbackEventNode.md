# Merged Callback Event

`haybale-example:node:MergedCallbackEventNode` · kind: node

Listens for a specified number of callbacks from other flows

## Ports

| id | direction | type | description |
|---|---|---|---|
| `custom_callback_count` | config | `haywire-core:type:INT` | Whole number |
| `listen_callback_1` | outlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |
| `triggered` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `payload_1` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `mode` | delivery | `'Every'` | Every runs this flow for every event. Pooled shares the events with the other pooled listeners of the same emitter: the next free one runs each event. |

## Notes

Listens for a specified number of callbacks from other flows.

Config:
    callback_name: Name of the callback to listen for

Outputs:
    triggered: Control flow when callback received
    payload: Data from callback

Delivery: `Every` runs for every callback; `Pooled` shares them with the emitter's other
pooled listeners, the next free one taking each callback.
