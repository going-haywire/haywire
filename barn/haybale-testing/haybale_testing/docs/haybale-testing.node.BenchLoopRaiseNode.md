# Bench Loop Raise Node

`haybale-testing:node:BenchLoopRaiseNode` · kind: node

FROZEN: data node raising on odd input, for measuring a loop with failures.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `x` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `y` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

FLOAT inlet `x`, FLOAT outlet `y = x`; raises when `x` is odd.
