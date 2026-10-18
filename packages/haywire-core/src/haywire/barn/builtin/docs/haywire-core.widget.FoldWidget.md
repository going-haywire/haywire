# FoldWidget

`haywire-core:widget:FoldWidget` · kind: widget

Fold header

## Details


## Notes

Opens and closes a fold of ports on a node card.

Click the header to open or close the fold. The triangle points down while
the fold is open, and the checkbox at the end shows the same state as the
fold's value, which a node can read like any other port. Hover the triangle
for the fold's description.

Config options (via `FoldWidget.config(properties={...})`):

- `text` (str): The fold's label.
- `description` (str): The text under the label in the triangle's tooltip.
