# Reset Detail

`haybale-graph-editor:panel:ClearDetailOverridesMenuPanel` · kind: panel

## Details

- **surface**: `selection-detail`
- **order**: `20`

## Notes

Drop each selected node's own detail rank, inside the Detail submenu
it undoes — beside the ranks it resets, not on the top-level menu.

Without this a node that has ever been re-ranked by hand is pinned for
good, and a graph-wide detail change silently skips it — "unset tracks,
set ignores", per hop. That makes this the counterpart to the graph-tier
setting, not a tidy-up: without a way back, the tier stops being able to
reassert over anything the user has touched.

Collapse is NOT reset here: it is no longer inherited from the graph, so
there is nothing for a node's own collapse state to fall back to — see
``SelectionDetailMenu``.
