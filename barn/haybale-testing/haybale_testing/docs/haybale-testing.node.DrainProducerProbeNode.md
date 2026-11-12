# Drain Producer Probe

`haybale-testing:node:DrainProducerProbeNode` · kind: node

Test-only control node writing 0, 1, 2, ... to its outlet, one value per run

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec_in` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `value` | outlet | `haywire-core:type:FLOAT` | Decimal number |
| `exec_out` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Notes

Test-only producer: each run writes the next count to `value`, starting at 0.

The test reads `written`, the number of values written so far, and `threads`, the
names of the threads it ran on.
