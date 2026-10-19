# Widget Node

`haybale-core:skin:WidgetNodeSkin` · kind: skin

The control alone, with the node label on its left — for widget nodes on a stage

## Notes

Draws a widget node as its control, with the node label on the left and no frame.

It draws the widget of each outlet the node itself declares, never that of a
setting promoted to a port. Rename the node to change the caption.

The node's *style* settings set the label's font, size, weight, colour and
alignment, the card's background and border, and where the label sits: left of
the control (half the row, up to *Max Label Width*), above it, or nowhere.

Widget nodes use it on the stage, where they draw no pins. A skin tagged
`special`, `stage-only` and `widget-node` is offered in the same list.
