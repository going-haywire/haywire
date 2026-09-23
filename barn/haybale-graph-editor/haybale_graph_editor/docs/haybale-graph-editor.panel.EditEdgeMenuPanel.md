# Edit

`haybale-graph-editor:panel:EditEdgeMenuPanel` · kind: panel

## Details

- **surface**: `edge-menu`
- **hosts**: `['edge-edit']`
- **order**: `25`

## Notes

The "Edit…" row — a submenu over the adapters behind this edge.

A hosting panel: it draws only the row and the flyout, piping the
``EdgeActions`` host one hop further, exactly as
``EditSelectionMenuPanel`` does for a node's Skin/Theme submenu. Mirrors
that UX for the edge's adapter chain instead.
