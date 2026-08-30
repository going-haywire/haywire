# Dissolve Reroute

`haybale-graph-editor:panel:DissolveRerouteMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **order**: `15`

## Notes

Collapse a reroute node back into a direct connection.

Only visible when the right-clicked node is a reroute node.
Bridges the upstream outlet directly to every downstream inlet,
then removes the reroute — all as one undoable operation.
