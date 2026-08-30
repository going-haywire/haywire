# More

`haybale-graph-editor:panel:SelectionOverflowPanel` · kind: panel

## Details

- **surface**: `toolbar`
- **hosts**: `['selection']`
- **order**: `999`

## Notes

The ⋯ — a panel that hosts the selection right-click menu.

It renders ``SelectionMenu`` itself rather than round-tripping a
synthetic event through the canvas to reopen it, so the batch ops live in
one place: the flyout shows the *same panel classes* the right-click menu
yields, not a duplicated curated set, and nothing moved off the menu.

It pipes — the default. ``SelectionToolbarProvider`` satisfies
``SelectionActions``, so the host it received travels one hop further.
