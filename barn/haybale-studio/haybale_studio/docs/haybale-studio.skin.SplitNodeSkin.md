# Split

`haybale-studio:skin:SplitNodeSkin` · kind: skin

Configs across the top, inlets and outlets in columns side by side

## Notes

Two-band skin: configs span the card, inlets and outlets split beneath.

Named for that split. Where :class:`StackedNodeSkin` puts every port type
in one column, this gives config ports the full card width on top and then
sets inlets and outlets side by side underneath. Ports are rendered through
``render_port``, which places each pin on the card edge its direction
implies — so the left column's pins straddle the card's left border and the
right column's its right.

Configs get the full width precisely *because* they carry no pin: with no
edge to attach to, nothing anchors them to a side, and their widgets are
the ones that actually need room. Squeezing them into a third column made
every config widget unusably narrow.

Groups are not rendered as a hierarchy here — a two-column split has no
place to put an indented, collapsible subtree without one column growing
past the other. Use the stacked skin on nodes whose ports are grouped.
