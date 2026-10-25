# Test Begin Play

`haybale-testing:node:TestBeginPlayNode` · kind: node

Test version of BeginPlay — triggered once when execution starts

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `timestamp` | outlet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

Test-only event node triggered when execution starts.
