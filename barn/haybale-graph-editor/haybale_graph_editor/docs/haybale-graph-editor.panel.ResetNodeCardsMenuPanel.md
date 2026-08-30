# Reset Node Cards

`haybale-graph-editor:panel:ResetNodeCardsMenuPanel` · kind: panel

## Details

- **surface**: `graph-more`
- **order**: `10`

## Notes

Make every node in the graph follow the graph's card settings again.

The graph tier is only as useful as its reach, and "unset tracks, set
ignores" means it loses reach every time a user folds one node by hand.
This is the way back — the graph-wide counterpart to the selection-scoped
reset on the node menu (ADR 0032).

It lives behind the "…" rather than in the prime area because it is a
correction, not a routine command: reached when the graph-level collapse
stops covering everything, which is rare and puzzling enough to be worth
hunting for.
