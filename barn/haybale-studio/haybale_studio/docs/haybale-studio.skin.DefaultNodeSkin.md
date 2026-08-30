# DefaultNodeSkin

`haybale-studio:skin:DefaultNodeSkin` · kind: skin

Default skin with collapsible group support

## Notes

Default skin that provides the standard node appearance with group support.

Features:
- Ports stacked in one column, each pin sided by the node's LayoutDirection
  (inlets left / outlets right under L2R, mirrored under R2L)
- Vertical layouts (T2B / B2T) instead render inlets and outlets as bare pin
  strips on the card's top/bottom edges, leaving only configs in the body
- Collapsible groups with visual hierarchy — horizontal layouts only
- Header pins for ports a collapsed group hides but an edge still needs
- Node collapse and NodeDetail honoured through ``show_of`` (ADR 0032)
- Automatic port ordering
