# Annotation

`haywire-core:node:AnnotationNode` · kind: node

A box of text for diagrams; links to other annotations with styled arrows

## Ports

| id | direction | type | description |
|---|---|---|---|
| `exec` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `top_0` | swinglet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `right_0` | swinglet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `bottom_0` | swinglet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `left_0` | swinglet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `done` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `text` | annotation | `''` | What the note says; double-click the card to edit it |
| `h_align` | annotation | `'center'` |  |
| `v_align` | annotation | `'middle'` |  |
| `font` | annotation | `'sans'` |  |
| `font_size` | annotation | `14` | Size of the text in pixels |
| `bold` | annotation | `False` |  |
| `italic` | annotation | `False` |  |
| `underline` | annotation | `False` |  |
| `text_color` | annotation | `''` | Empty uses the theme's text color |
| `highlight_color` | annotation | `''` | Marker behind the text; empty draws none |
| `show_control_pins` | annotation | `False` | Draw the control pins while they are unlinked |

## Notes

A note on the canvas, with arrows to other notes.

Double-click the card to write the text in place; the properties panel sets
the font, colors and alignment. Line breaks are kept.

Hover the card to show one open pin on each side. Drag from a pin on any side
to a pin on any side of another annotation: an arrow can leave or arrive at
each of them, and two pins are joined by one arrow at most. The arrow head sits
at the end you dropped on; change the heads, colour, dash and width in the
arrow's edge menu.

A pin you connect stays, and a new open pin appears after it, so a side can
hold any number of arrows. A side's pins are kept centred along it. Deleting
an arrow removes a pin it leaves without one; undoing the delete brings the
pin back. You can also remove a pin from its pin menu.

Arrows between annotations are drawn and saved with the graph but never run.
The node also has a control inlet and outlet that pass control and its
payload straight through, so a note can sit inside a control chain. They are
drawn while linked, or always when *Show Control Pins* is on.
