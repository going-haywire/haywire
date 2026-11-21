# Math Operation

`haybale-example:node:MathOperationNode` · kind: node

Applies the chosen operation (add, subtract, multiply, divide) to two float values.

> **Deprecated:** This node will be moved to the math library

## Ports

| id | direction | type | description |
|---|---|---|---|
| `operator` | inlet | `haybale-example:type:MATH_OPERATION` | Simple mathematical operations for one or two float values |
| `value_a` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `value_b` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `result` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

Applies the chosen operation to Value A and Value B; division by zero gives 0.0.
