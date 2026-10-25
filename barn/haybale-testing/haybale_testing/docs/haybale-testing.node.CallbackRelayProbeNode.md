# Callback Relay Probe

`haybale-testing:node:CallbackRelayProbeNode` · kind: node

Test-only: copies a callback inlet's value to its outlet on write, with a suffix.

## Ports

| id | direction | type | description |
|---|---|---|---|
| `in` | inlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |
| `out` | outlet | `haywire-core:type:CALLBACK` | Signal for callback execution between nodes |

## Notes

Copies each value written to `in` onto `out` at once, with `suffix` appended.

An empty `suffix` relays the value unchanged; absence is relayed as absence.
`heard` records every value `in` reported.
