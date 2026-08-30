# Node Errors

`haybale-graph-editor:panel:NodeErrorsSelectionMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **order**: `0`

## Notes

Node errors panel for the unified selection context menu.

Scoped to the primary (active) node's errors via _node_has_errors, which
reads EditState.active_node — set by on_selection_context to the
selection's primary. Display-only; calls no action verb.
