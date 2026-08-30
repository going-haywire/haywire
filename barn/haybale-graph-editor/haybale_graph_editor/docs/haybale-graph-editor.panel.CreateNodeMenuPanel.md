# Create Node

`haybale-graph-editor:panel:CreateNodeMenuPanel` · kind: panel

## Details

- **surface**: `graph-body`
- **order**: `0`

## Notes

The hierarchical node-creation menu, search and tree together.

Kept whole in the prime area: ``NodeMenuBuilder`` couples search and tree
through mutable element handles on one instance, so splitting them across
two panels needs its own design. Moving the tree into the "…" flyout is a
follow-up.
