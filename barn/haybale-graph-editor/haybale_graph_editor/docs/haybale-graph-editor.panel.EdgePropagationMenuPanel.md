# Propagation

`haybale-graph-editor:panel:EdgePropagationMenuPanel` · kind: panel

Lazy propagation pulls data on demand instead of pushing it to the target node.

## Details

- **surface**: `edge-menu`
- **order**: `0`

## Notes

Show an edge's propagation mode and switch it between lazy and eager.

**The row rewrites itself on click rather than closing over its state**,
for the same reason as `CollapseSelectionMenuPanel`: the row is drawn with
`closes=False`, so the menu stays open, and a handler that captured the mode
at draw time would keep re-sending that value and the toggle would work
exactly once.
The current mode is asked for on every click (`toggle_edge_propagation`
decides and returns the new one).

The icon and label both name the current mode: propagation is a standing
property of the edge, so the row reads "Propagation: Lazy/Eager"
rather than a command. A mode the connection fixes draws a disabled row. An edge
without propagation (a callback or visual edge) does not poll, so no row is drawn.
