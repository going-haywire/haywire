# Swinglet Pass Probe

`haybale-testing:node:SwingletPassProbeNode` · kind: node

Test-only: a data node whose float swinglet records each run and writes ten times it.

## Ports

| id | direction | type | description |
|---|---|---|---|
| s | swinglet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

Data node with a float swinglet `s`. Each run records `s` in `seen`, then writes `s * 10` to it.
