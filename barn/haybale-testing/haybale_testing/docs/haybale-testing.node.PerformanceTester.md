# Performance Testing Node

`haybale-testing:node:PerformanceTester` · kind: node

Helps test performance of execution system

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| port_count | config | haywire-core:type:INT | Whole number |
| trigger | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Triggered when execution is switching control flow based on condition.
