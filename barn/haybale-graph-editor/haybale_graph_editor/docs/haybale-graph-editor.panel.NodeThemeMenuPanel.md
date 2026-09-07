# Theme

`haybale-graph-editor:panel:NodeThemeMenuPanel` · kind: panel

## Details

- **surface**: `selection-edit`
- **order**: `30`

## Notes

The node theme colouring this card, as a row opening its source.

``props.node_theme`` resolves the graph < node chain like ``skin`` does,
but has no registry-default substitute: an empty value means the card
takes its colours from the workbench theme, and there is no node theme to
open. The row polls false rather than pointing at something arbitrary.
