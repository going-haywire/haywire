# Chip Field Probe

`haybale-testing:node:ChipFieldProbeNode` · kind: node

Hosts a chip select whose root is the select, beside a plain select

## Ports

| id | direction | type | description |
|---|---|---|---|
| `chips` | config | `haywire-core:type:STRING` | Text data |
| `plain` | config | `haywire-core:type:STRING` | Text data |
| `passthrough` | outlet | `haywire-core:type:STRING` | Text data |

## Notes

A chip field (all twelve choices chosen) and a plain single select.
