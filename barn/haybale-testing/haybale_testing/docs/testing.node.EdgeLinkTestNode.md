# Edge Link TestNode

`testing:node:EdgeLinkTestNode` · kind: node

## Ports

| id | direction | type | description |
|---|---|---|---|
| callback_inlet | inlet | core:type:CALLBACK | Signal for callback execution between nodes |
| execute_inlet | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| bool_inlet | inlet | testing:type:TEST_BOOL | True or False |
| int_inlet | inlet | testing:type:TEST_INT | Whole number |
| float_inlet | inlet | testing:type:TEST_FLOAT | Decimal numberer |
| string_inlet | inlet | testing:type:TEST_STRING | Text data |
| temperature_inlet | inlet | testing:type:TEST_TEMPERATURE | Temperature in Celsius |
| pooled_bool_inlet | inlet | core:type:PooledType | Multi-source aggregation |
| pooled_int_inlet | inlet | core:type:PooledType | Multi-source aggregation |
| pooled_float_inlet | inlet | core:type:PooledType | Multi-source aggregation |
| pooled_temperature_inlet | inlet | core:type:PooledType | Multi-source aggregation |
| pooled_string_inlet | inlet | core:type:PooledType | Multi-source aggregation |
| pooled_array_string_inlet | inlet | core:type:PooledType | Multi-source aggregation |
| callback_outlet | outlet | core:type:CALLBACK | Signal for callback execution between nodes |
| execute_out | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| bool_outlet | outlet | testing:type:TEST_BOOL | True or False |
| int_outlet | outlet | testing:type:TEST_INT | Whole number |
| float_outlet | outlet | testing:type:TEST_FLOAT | Decimal numberer |
| temperature_outlet | outlet | testing:type:TEST_TEMPERATURE | Temperature in Celsius |
| string_outlet | outlet | testing:type:TEST_STRING | Text data |
| array_bool_outlet | outlet | core:type:ArrayType | Homogeneous typed array |
| array_int_outlet | outlet | core:type:ArrayType | Homogeneous typed array |
| array_float_outlet | outlet | core:type:ArrayType | Homogeneous typed array |
| array_temperature_outlet | outlet | core:type:ArrayType | Homogeneous typed array |
| array_string_outlet | outlet | core:type:ArrayType | Homogeneous typed array |

## Notes

Node specificly to test connection behaviors
in the UI. It has a wide variety of inlet and outlet types
to test all the different connection rules.
It does not perform any actual logic in its worker,
it just serves as a testbed for connections.
