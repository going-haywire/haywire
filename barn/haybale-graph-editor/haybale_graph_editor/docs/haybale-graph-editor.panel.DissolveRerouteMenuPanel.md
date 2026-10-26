# Dissolve Reroute

`haybale-graph-editor:panel:DissolveRerouteMenuPanel` · kind: panel

Collapse a reroute node back into a direct connection.

## Details

- **surface**: `selection`
- **order**: `230`

## Notes

Collapse a reroute node back into a direct connection.

Only visible when the right-clicked node is a reroute node.
Bridges the upstream outlet directly to every downstream inlet,
then removes the reroute — all as one undoable operation.
