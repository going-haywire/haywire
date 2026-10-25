# Swinglet Echo Probe

`haybale-testing:node:SwingletEchoProbeNode` · kind: node

Test-only: a data node whose float swinglet records an arrival and writes it plus one.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `s` | swinglet | `haywire-core:type:FLOAT` | Decimal number |

## Notes

Data node with a float swinglet `s`. `on_change` records each arriving value in `changes`,
then writes that value plus one to `s`.
