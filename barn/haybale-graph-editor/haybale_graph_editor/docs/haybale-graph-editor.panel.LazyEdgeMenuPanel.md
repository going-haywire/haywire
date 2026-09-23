# Propagation

`haybale-graph-editor:panel:LazyEdgeMenuPanel` · kind: panel

Lazy propagation pulls data on demand instead of pushing it to the target node.

## Details

- **surface**: `edge-menu`
- **order**: `0`

## Notes

Flip an edge between eager (push) and lazy (pull-on-demand) propagation.

**The row rewrites itself on click rather than closing over its state**,
for the same reason as ``CollapseSelectionMenuPanel``: ``hui.menu_row``
does not dismiss its popup, so a handler that captured ``lazy`` at draw
time would keep re-sending that value and the toggle would work exactly
once. The current state is asked for on every click
(``toggle_edge_lazy`` decides and returns the new state).

The icon and label both name the current MODE, unlike Collapse's
verb-labelled row: propagation is a standing property of the edge, not a
one-shot action, so the row reads "Propagation: Lazy/Eager" rather than a
command.
