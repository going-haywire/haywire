# Callback Event

`haybale-example:node:CallbackEventNode` · kind: node

Listens for custom callbacks from other flows

## Ports

| id | direction | type | description |
|---|---|---|---|
| `custom_name` | config | `haywire-core:type:FOLD` | Hides or shows the ports inside it |
| `custom_callback_name` | config | `haywire-core:type:STRING` | Text data |
| `thread_mode` | config | `haywire-core:type:STRING` | Text data |
| `listen_callback` | outlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |
| `triggered` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `payload` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `mode` | delivery | `'Every'` | Every runs this flow for every event. Pooled shares the events with the other pooled listeners of the same emitter: the next free one runs each event. |

## Notes

Listens for custom callbacks from other flows.

Config:
    callback_name: Name of the callback to listen for
    delivery: `Every` runs for every callback; `Pooled` shares them with the emitter's other
        pooled listeners, the next free one taking each callback

Outputs:
    triggered: Control flow when callback received
    payload: Data from callback
