# Edit Source

`haybale-graph-editor:panel:EditEdgeMenuPanel` · kind: panel

The "Edit Source" row — a submenu over the adapters behind this edge.

## Details

- **surface**: `edge-menu`
- **hosts**: `['edge-edit']`
- **order**: `300`

## Notes

The "Edit Source" row — a submenu over the adapters behind this edge.

A hosting panel: it draws only the row and the flyout, piping the
``EdgeActions`` host one hop further, exactly as
``EditSelectionMenuPanel`` does for a node's Skin/Theme submenu. Mirrors
that UX for the edge's adapter chain instead.
