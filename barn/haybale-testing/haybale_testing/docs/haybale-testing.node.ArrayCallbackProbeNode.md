# Array Callback Probe

`haybale-testing:node:ArrayCallbackProbeNode` · kind: node

Test-only: an array-of-CALLBACK outlet and inlet.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `names_in` | inlet | `haybale-core:type:ARRAY` | Homogeneous typed array |
| `names_out` | outlet | `haybale-core:type:ARRAY` | Homogeneous typed array |

## Notes

Node with an `ARRAY[CALLBACK]` outlet and inlet; `heard` records each list the inlet receives.
