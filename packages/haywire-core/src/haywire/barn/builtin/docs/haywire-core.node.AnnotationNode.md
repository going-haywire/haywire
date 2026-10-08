# Annotation

`haywire-core:node:AnnotationNode` · kind: node

A box of text for diagrams; links to other annotations with styled arrows

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec | inlet | haywire-core:type:EXEC | Signal for controlling execution flow between nodes |
| top_0 | swinglet | haywire-core:type:ADD | Grows a new port from whatever connects to it |
| right_0 | swinglet | haywire-core:type:ADD | Grows a new port from whatever connects to it |
| bottom_0 | swinglet | haywire-core:type:ADD | Grows a new port from whatever connects to it |
| left_0 | swinglet | haywire-core:type:ADD | Grows a new port from whatever connects to it |
| done | outlet | haywire-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

A note on the canvas, with arrows to other notes.

Write the text in the properties panel, or double-click the card to edit it
in a larger editor. Line breaks are kept.

Hover the card to show one open pin on each side. Drag from a pin on any side
to a pin on any side of another annotation: an arrow can leave or arrive at
each of them, and two pins are joined by one arrow at most. The arrow head sits
at the end you dropped on; change the heads, colour, dash and width in the
arrow's edge menu.

A pin you connect stays, and a new open pin appears after it, so a side can
hold any number of arrows. A side's pins are kept centred along it. Remove a
pin you no longer need from its pin menu.

Arrows between annotations are drawn and saved with the graph but never run.
The node also has a control inlet and outlet that pass control and its
payload straight through, so a note can sit inside a control chain. They are
drawn while linked, or always when *Show Control Pins* is on.
