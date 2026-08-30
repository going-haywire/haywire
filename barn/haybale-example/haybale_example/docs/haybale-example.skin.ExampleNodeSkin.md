# ExampleNodeSkin

`haybale-example:skin:ExampleNodeSkin` · kind: skin

Custom skin for nodes with special styling

## Notes

Custom skin for nodes with special styling.

Two-band layout rather than the default skin's single stack: config ports
span the full card width on top, then inlets and outlets sit side by side
beneath. Ports are rendered through ``render_port``, which places each pin
on the card edge its direction implies — so the left column's pins straddle
the card's left border and the right column's its right.

Configs get the full width precisely *because* they carry no pin: with no
edge to attach to, nothing anchors them to a side, and their widgets are
the ones that actually need room. Squeezing them into a third column made
every config widget unusably narrow.
