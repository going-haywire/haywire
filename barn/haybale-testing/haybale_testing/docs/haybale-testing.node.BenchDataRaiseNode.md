# Bench Data Raise Node

`haybale-testing:node:BenchDataRaiseNode` · kind: node

FROZEN: data node whose worker always raises, for measuring the failure path.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `x` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `y` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

One FLOAT inlet `x`, one FLOAT outlet `y`; the worker raises every time.
