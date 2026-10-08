# Swinglet Control Probe

`haybale-testing:node:SwingletControlProbeNode` · kind: node

Test-only: a control node with an exec swinglet that counts its runs.

## Ports

| id | direction | type | description |
|---|---|---|---|
| flow | swinglet | haywire-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Control node with an `EXEC` swinglet `flow`. Each run increments `runs` and returns `flow`.
