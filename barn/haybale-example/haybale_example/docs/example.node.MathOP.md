# Math Operation

`example:node:MathOP` · kind: node

> **Deprecated:** This node will be moved to the math library

## Ports

| id | direction | type | description |
|---|---|---|---|
| operator | inlet | example:type:MathOPSelector | Simple mathematical operations for one or two float values |
| value_a | inlet | builtin:type:FLOAT | Decimal numberer |
| value_b | inlet | builtin:type:FLOAT | Decimal numberer |
| result | outlet | builtin:type:FLOAT | Decimal numberer |

## Notes

Node that outputs a constant value
