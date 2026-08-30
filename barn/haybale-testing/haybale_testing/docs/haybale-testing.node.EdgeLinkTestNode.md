# Edge Link TestNode

`haybale-testing:node:EdgeLinkTestNode` · kind: node

## Ports

| id | direction | type | description |
|---|---|---|---|
| callback_inlet | inlet | haybale-core:type:CALLBACK | Signal for callback execution between nodes |
| execute_inlet | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| bool_inlet | inlet | haybale-testing:type:TEST_BOOL | True or False |
| int_inlet | inlet | haybale-testing:type:TEST_INT | Whole number |
| float_inlet | inlet | haybale-testing:type:TEST_FLOAT | Decimal numberer |
| string_inlet | inlet | haybale-testing:type:TEST_STRING | Text data |
| temperature_inlet | inlet | haybale-testing:type:TEST_TEMPERATURE | Temperature in Celsius |
| pooled_bool_inlet | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| pooled_int_inlet | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| pooled_float_inlet | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| pooled_temperature_inlet | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| pooled_string_inlet | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| pooled_array_string_inlet | inlet | haybale-core:type:PooledType | Multi-source aggregation |
| callback_outlet | outlet | haybale-core:type:CALLBACK | Signal for callback execution between nodes |
| execute_out | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| bool_outlet | outlet | haybale-testing:type:TEST_BOOL | True or False |
| int_outlet | outlet | haybale-testing:type:TEST_INT | Whole number |
| float_outlet | outlet | haybale-testing:type:TEST_FLOAT | Decimal numberer |
| temperature_outlet | outlet | haybale-testing:type:TEST_TEMPERATURE | Temperature in Celsius |
| string_outlet | outlet | haybale-testing:type:TEST_STRING | Text data |
| array_bool_outlet | outlet | haybale-core:type:ArrayType | Homogeneous typed array |
| array_int_outlet | outlet | haybale-core:type:ArrayType | Homogeneous typed array |
| array_float_outlet | outlet | haybale-core:type:ArrayType | Homogeneous typed array |
| array_temperature_outlet | outlet | haybale-core:type:ArrayType | Homogeneous typed array |
| array_string_outlet | outlet | haybale-core:type:ArrayType | Homogeneous typed array |

## Notes

Node specificly to test connection behaviors
in the UI. It has a wide variety of inlet and outlet types
to test all the different connection rules.
It does not perform any actual logic in its worker,
it just serves as a testbed for connections.
