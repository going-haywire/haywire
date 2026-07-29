# Bench Bare Node

`testing:node:BenchBareNode` · kind: node

FROZEN: minimal no-port control node for measuring _execute dispatch overhead.

## Notes

A control node with no ports whose worker does nothing and returns None.

The full ``_execute`` path still runs (no early-out, since it is not a data
node), so calling ``node._execute(ctx)`` in a tight loop measures dispatch.
