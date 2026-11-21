# Nested Fold Probe

`haybale-testing:node:NestedFoldProbeNode` · kind: node

Tests that a fold declared inside another fold raises

## Ports

| id | direction | type | description |
|---|---|---|---|
| `outer` | config | `haywire-core:type:FOLD` | Hides or shows the ports inside it |
| `substeps` | config | `haywire-core:type:FLOAT` | Decimal number |
| `out` | outlet | `haywire-core:type:STRING` | Text data |

## Notes

Test-only.
