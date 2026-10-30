# Bench Sink Node

`haybale-testing:node:BenchSinkNode` · kind: node

FROZEN: control node with one data inlet, ending the branch.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec_in` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `x` | inlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

EXEC inlet `exec_in` and FLOAT data inlet `x`; the worker ends the branch.
