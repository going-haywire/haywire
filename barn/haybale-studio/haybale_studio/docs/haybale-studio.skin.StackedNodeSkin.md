# Stacked

`haybale-studio:skin:StackedNodeSkin` · kind: skin

One port column, outlets over configs over inlets, with collapsible groups

## Notes

The default skin: every port type stacked in ONE column.

Named for that column. The order within it is outlets → configs → inlets,
and each pin is sided by the node's LayoutDirection rather than by which
band it is in — which is what distinguishes this from
:class:`SplitNodeSkin`, where inlets and outlets take a column each.

Features:
- Ports stacked in one column, each pin sided by the node's LayoutDirection
  (inlets left / outlets right under L2R, mirrored under R2L)
- Vertical layouts (T2B / B2T) instead render inlets and outlets as bare pin
  strips on the card's top/bottom edges, leaving only configs in the body
- Collapsible groups with visual hierarchy — horizontal layouts only
- Header pins for ports a collapsed group hides but an edge still needs
- Node collapse and NodeDetail honoured through ``show_of`` (ADR 0032)
- Automatic port ordering
