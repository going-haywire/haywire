# Array Callback Probe

`haybale-testing:node:ArrayCallbackProbeNode` · kind: node

Test-only: an array-of-CALLBACK outlet and inlet.

## Ports

| id | direction | type | description |
|---|---|---|---|
| names_in | inlet | haybale-core:type:ArrayType | Homogeneous typed array |
| names_out | outlet | haybale-core:type:ArrayType | Homogeneous typed array |

## Notes

Node with an `ArrayType[CALLBACK]` outlet and inlet; `heard` records each list the inlet receives.
