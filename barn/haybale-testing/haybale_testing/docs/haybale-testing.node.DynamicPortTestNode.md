# Dynamic Port TestNode

`haybale-testing:node:DynamicPortTestNode` · kind: node

## Ports

| id | direction | type | description |
|---|---|---|---|
| bool_inlet | inlet | haybale-testing:type:TEST_BOOL | True or False |
| port_count | inlet | haybale-testing:type:TEST_INT | Whole number |
| dynamic_inlet_0 | inlet | haybale-testing:type:TEST_INT | Whole number |
| dynamic_inlet_1 | inlet | haybale-testing:type:TEST_INT | Whole number |
| bool_outlet | outlet | haybale-testing:type:TEST_BOOL | True or False |
| dynamic_outlet_0 | outlet | haybale-testing:type:TEST_INT | Whole number |
| dynamic_outlet_1 | outlet | haybale-testing:type:TEST_INT | Whole number |

## Notes

Node with dynamically configurable ports for testing
the validation pipeline (push/pop, hot reload, edge survival).

Static ports (always present):
- bool_inlet, bool_outlet

Dynamic ports (controlled by port_count config):
- dynamic_inlet_0..N  (TEST_INT)
- dynamic_outlet_0..N (TEST_INT)
