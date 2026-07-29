# Bench Exec Node

`testing:node:BenchExecNode` · kind: node

FROZEN: minimal EXEC in→out conduit for measuring control-edge payload forwarding.

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec_in | inlet | core:type:EXEC | Signal for controlling execution flow between nodes |
| exec_out | outlet | core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Single EXEC inlet/outlet pass-through. Worker only advances.
