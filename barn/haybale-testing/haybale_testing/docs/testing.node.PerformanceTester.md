# Performance Testing Node

`testing:node:PerformanceTester` · kind: node

Helps test performance of execution system

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| port_count | config | builtin:type:INT | Whole number |
| trigger | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Triggered when execution is switching control flow based on condition.
