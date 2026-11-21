# Performance Probe

`haybale-testing:node:PerformanceProbeNode` · kind: node

Helps test performance of execution system

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `port_count` | config | `haywire-core:type:INT` | Whole number |
| `trigger` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Notes

Triggered when execution is switching control flow based on condition.
