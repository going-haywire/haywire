# Callback Event Probe

`haybale-testing:node:CallbackEventProbeNode` · kind: node

Test version of CustomCallback — listens for named callbacks

## Ports

| id | direction | type | description |
|---|---|---|---|
| `custom_name` | config | `haywire-core:type:FOLD` | Hides or shows the ports inside it |
| `custom_callback_name` | config | `haywire-core:type:STRING` | Text data |
| `thread_mode` | config | `haywire-core:type:STRING` | Text data |
| `queue_mode` | config | `haywire-core:type:STRING` | Text data |
| `listen_callback` | outlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |
| `triggered` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `payload` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `mode` | delivery | `'Every'` | Every runs this flow for every event. Pooled shares the events with the other pooled listeners of the same emitter: the next free one runs each event. |

## Notes

Test-only event node that listens for custom callbacks.
