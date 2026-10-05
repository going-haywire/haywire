# Array Exec Probe

`haybale-testing:node:ArrayExecProbeNode` · kind: node

Test-only: an array-of-EXEC outlet and inlet on a control node.

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec_in | inlet | haywire-core:type:EXEC | Signal for controlling execution flow between nodes |
| exec_list_in | inlet | haybale-core:type:ArrayType | Homogeneous typed array |
| exec_list_out | outlet | haybale-core:type:ArrayType | Homogeneous typed array |

## Notes

Control node with an `ArrayType[EXEC]` outlet and inlet.

Set `emit` to a list and the worker writes it to `exec_list_out` and fires
that outlet. The worker stores what arrived on `exec_list_in` in `received`.
