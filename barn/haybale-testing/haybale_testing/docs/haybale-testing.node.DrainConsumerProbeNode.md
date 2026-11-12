# Drain Consumer Probe

`haybale-testing:node:DrainConsumerProbeNode` · kind: node

Test-only control node taking everything queued on its drain inlet, once per run

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec_in` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `queue` | inlet | `haybale-core:type:DRAIN` | Every value its edge delivers, queued until the node takes them |
| `exec_out` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Notes

Test-only consumer: each run takes the `queue` drain inlet.

The test reads `taken`, every value taken in order, `batches`, how many values each
run took, `dropped`, the total the inlet discarded to its limit, and `threads`, the
names of the threads it ran on.
