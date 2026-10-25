# Menu

`haybale-core:node:MenuNode` · kind: node

A drop-down that sends the item picked, and shows the item it is fed

## Ports

| id | direction | type | description |
|---|---|---|---|
| `in` | inlet | `haywire-core:type:STRING` | Text data |
| `value` | outlet | `haywire-core:type:CHOICES` | A string constrained to a set of options (options live per-use in widget_config) |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `label_position` | style | `'left'` | Where the label sits: left of the control, above it, or not at all |
| `max_label_width` | style | `None` | The widest the label gets when it is on the left: it takes half the row up to this width. None is 9rem, as in the properties panel |
| `label_align` | style | `'left'` |  |
| `font` | style | `'sans'` |  |
| `font_size` | style | `14` | Size of the label in pixels |
| `bold` | style | `False` |  |
| `italic` | style | `False` |  |
| `label_color` | style | `''` | Empty uses the theme's text color |
| `background` | style | `''` | Fill behind the label and control; empty draws none |
| `border` | style | `False` | Draw the theme's node border around the card |
| `options` | menu | `['One', 'Two', 'Three']` | The items the menu offers, in order |

## Notes

A drop-down that sends the text of the item picked.

Edit the items in *Options*; they can also be promoted to an inlet. A text
arriving at *In* is shown and sent on, even one that is not among the options.
Last write wins, so a fed menu is a display. When the feeding edge goes, the
menu keeps its last item.
