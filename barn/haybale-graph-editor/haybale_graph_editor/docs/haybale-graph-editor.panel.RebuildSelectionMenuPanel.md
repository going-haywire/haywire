# Rebuild

`haybale-graph-editor:panel:RebuildSelectionMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **hosts**: `['selection-rebuild']`
- **order**: `40`

## Notes

The "Rebuild" row — a submenu over redraw / revalidate / reset.

A hosting panel, so it draws only the arrangement: the row and the flyout
it expands into. It pipes — the three commands inside reach the same
``SelectionActions`` host one hop further without either side naming it.
