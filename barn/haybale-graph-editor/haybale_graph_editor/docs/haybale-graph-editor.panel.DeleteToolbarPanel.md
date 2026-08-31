# Delete

`haybale-graph-editor:panel:DeleteToolbarPanel` · kind: panel

## Details

- **surface**: `toolbar`
- **order**: `20`

## Notes

Delete the selection — hidden when a locked node is in it.

Unlike Copy, which stays unconditional because copying a locked node harms
nothing. Gated on :func:`selection_has_locked` rather than
``locked_bag``: this verb applies to any selection size, so it must not
inherit the Lock button's single-node rule.
