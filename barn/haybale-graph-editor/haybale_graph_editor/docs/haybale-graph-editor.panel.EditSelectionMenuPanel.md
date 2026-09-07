# Edit

`haybale-graph-editor:panel:EditSelectionMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **hosts**: `['selection-edit']`
- **order**: `35`

## Notes

The "Edit…" row — a submenu over the components behind this node.

A hosting panel: it draws only the row and the flyout, piping the
``SelectionActions`` host one hop further, exactly as
``DetailSelectionMenuPanel`` does. The pin menu carries the same row over
its own subjects, so the gesture reads identically on either target.

Single-node only: skin and theme resolve per node, and a mixed or
multi-node selection has no one answer to give.

The node row always draws for a single node (a wrapper carries its
registry key by construction), so unlike the pin menu's Edit row this one
cannot end up hosting an empty body — and a hosting panel that polls true
over nothing would cost this menu its popup, since a hosting panel is
excluded from the leaf count (ADR-0029). Copy/Delete draw beside it
regardless, so the risk is theirs to absorb; the single-node rule is
still what keeps the row honest.
