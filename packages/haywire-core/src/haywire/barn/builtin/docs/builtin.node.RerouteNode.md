# Reroute

`builtin:node:RerouteNode` · kind: node

Pass-through node for bending wires. Supports DATA and CONTROL edges.

## Notes

Forwards its single inlet value to its single outlet.

Ships port-less; the split action adds the typed inlet/outlet. The port ids
are chosen by the split action, so this node discovers its ports by
introspection rather than naming fixed ids.
