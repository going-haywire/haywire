# Reset Node Detail

`haybale-graph-editor:panel:ResetNodeCardsMenuPanel` · kind: panel

## Details

- **surface**: `graph-more`
- **order**: `10`

## Notes

Make every node in the graph follow the graph's detail rank again.

The graph tier is only as useful as its reach, and "unset tracks, set
ignores" means it loses reach every time a user re-ranks one node by hand.
This is the way back — the graph-wide counterpart to the selection-scoped
reset on the node menu (ADR 0032). Collapse is out of scope: it is no
longer inherited from the graph, so a node's own collapse state has
nothing to reset back to.

It lives behind the "…" rather than in the prime area because it is a
correction, not a routine command: reached when the graph-level detail
stops covering everything, which is rare and puzzling enough to be worth
hunting for.
