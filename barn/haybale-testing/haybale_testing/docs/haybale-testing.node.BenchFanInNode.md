# Bench Fan In Node

`haybale-testing:node:BenchFanInNode` · kind: node

FROZEN: data node adding two inputs, for measuring a fan-in in data-flow evaluation.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `a` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `b` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `y` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

FLOAT inlets `a` and `b`, FLOAT outlet `y = a + b`.
