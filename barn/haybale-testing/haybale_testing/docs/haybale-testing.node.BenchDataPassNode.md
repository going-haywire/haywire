# Bench Data Pass Node

`haybale-testing:node:BenchDataPassNode` · kind: node

FROZEN: data node passing x + 1 on, for measuring data-flow evaluation.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `x` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `y` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

One FLOAT inlet `x`, one FLOAT outlet `y = x + 1`.
