# Fold

`haybale-graph-editor:panel:CollapseToolbarPanel` · kind: panel

One button that folds or unfolds the selection.

## Details

- **surface**: `toolbar`
- **order**: `100`

## Notes

One button that folds or unfolds the selection (ADR 0032).

The same verb as the context menu's Fold row, on the toolbar because
folding is the gesture a user repeats while reading a graph — the
code-folding idiom — and a repeated gesture should not cost a right-click.

Like that row, it decides nothing at draw time: ``toggle_selection_collapsed``
reads the current state per click and returns the new one, and the button
restyles itself from the answer. The toolbar usually re-renders anyway
(folding changes a node's size, which moves the selection bounds that
position it), but "usually" is not a thing to leave a toggle resting on.

The icon names the ACTION, matching the tooltip — never the current state,
which would contradict the words beside it.
