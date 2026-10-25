# Swinglet Stop Probe

`haybale-testing:node:SwingletStopProbeNode` · kind: node

Test-only: a data node whose float swinglet records each run and passes nothing on.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `s` | swinglet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

Data node with a float swinglet `s`. Each run records `s` in `seen` and writes nothing.
