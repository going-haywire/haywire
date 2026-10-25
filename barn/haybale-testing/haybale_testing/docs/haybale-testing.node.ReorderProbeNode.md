# Reorder Probe

`haybale-testing:node:ReorderProbeNode` · kind: node

Tests user-driven port ordering

## Ports

| id | direction | type | description |
|---|---|---|---|
| `a` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `b` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `c` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `dyn_a` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `dyn_b` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `dyn_c` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `out` | outlet | `haywire-core:type:STRING` | Text data |

## Notes

Test-only.

Static inlets `a`, `b`, `c` and outlet `out`, plus the dynamic inlets
`dyn_a`, `dyn_b`, `dyn_c` that `rebuild()` re-adds through `rejig()`.
