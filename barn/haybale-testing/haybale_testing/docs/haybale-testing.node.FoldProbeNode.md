# Fold Probe

`haybale-testing:node:FoldProbeNode` · kind: node

Tests fold minting, lanes and open state

## Ports

| id | direction | type | description |
|---|---|---|---|
| `inputs` | inlet | `haywire-core:type:FOLD` | Hides or shows the ports inside it |
| `a` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `b` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `solver` | config | `haywire-core:type:FOLD` | How the solver steps through time. |
| `substeps` | config | `haywire-core:type:FLOAT` | Decimal number |
| `advanced` | config | `haywire-core:type:FOLD` | Hides or shows the ports inside it |
| `epsilon` | config | `haywire-core:type:FLOAT` | Decimal number |
| `out` | outlet | `haywire-core:type:STRING` | Text data |

## Notes

Test-only.
