# Record Emit Probe

`haybale-testing:node:RecordEmitProbeNode` · kind: node

Test control node emitting to every dataclass subscription in its pool

## Ports

| id | direction | type | description |
|---|---|---|---|
| `execute` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `subscriptions` | inlet | `haybale-core:type:POOLED` | Multi-source aggregation |
| `exec` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `size` | backlog | `16` | How many events wait while every pooled listener is busy. |
| `full` | backlog | `'Drop oldest'` | Drop oldest makes room by losing the oldest waiting event. Wait holds the emitter up to 5 s for room, then loses the new event. |

## Notes

Test-only emitter collecting `TEST_RECORD_CALLBACK` subscriptions in a pooled inlet.

One emit reaches every subscription, so pooled Record Event Probes share it. The payload
is `{"weights": {name: weight}}`, each listener's weight under its name.
