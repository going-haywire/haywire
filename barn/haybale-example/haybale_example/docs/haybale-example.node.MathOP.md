# Math Operation

`haybale-example:node:MathOP` · kind: node

Node that outputs a constant value.

> **Deprecated:** This node will be moved to the math library

## Ports

| id | direction | type | description |
|---|---|---|---|
| `operator` | inlet | `haybale-example:type:MathOPSelector` | Simple mathematical operations for one or two float values |
| `value_a` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `value_b` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `result` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

Node that outputs a constant value
