# Callback Emit Probe

`haybale-testing:node:CallbackEmitProbeNode` · kind: node

Test version of EmitCallback — emits a callback to trigger event nodes

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `sequential_mode` | inlet | `haywire-core:type:BOOL` | Sequential Mode - if multiple callbacks, emit in sequence |
| `payload` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `edge_callback` | inlet | `haybale-core:type:POOLED` | Multi-source aggregation |
| `custom_name` | config | `haywire-core:type:FOLD` | Hides or shows the ports inside it |
| `custom_callback_name` | config | `haywire-core:type:STRING` | Text data |
| `exec` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `size` | backlog | `16` | How many events wait while every pooled listener is busy. |
| `full` | backlog | `'Drop oldest'` | Drop oldest makes room by losing the oldest waiting event. Wait holds the emitter up to 5 s for room, then loses the new event. |

## Notes

Test-only control node that emits a named callback.
