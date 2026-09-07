# Skin

`haybale-graph-editor:panel:NodeSkinMenuPanel` · kind: panel

## Details

- **surface**: `selection-edit`
- **order**: `20`

## Notes

The skin that drew this node's card, as a row opening its source.

``props.skin`` already resolves the graph < node chain, so it holds the
key actually in effect. It is None when the node defers entirely to the
registry's default, which ``ui_node`` substitutes at render time — so the
same fallback is applied here, or the row would vanish on every node that
never overrode its skin (which is most of them).
