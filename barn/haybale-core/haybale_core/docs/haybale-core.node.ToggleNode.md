# Toggle

`haybale-core:node:ToggleNode` · kind: node

An on/off switch that sends true or false, and shows the value it is fed

## Ports

| id | direction | type | description |
|---|---|---|---|
| `in` | inlet | `haywire-core:type:BOOL` | True or False |
| `value` | outlet | `haywire-core:type:BOOL` | True or False |

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

## Notes

An on/off switch that sends true or false.

A value arriving at *In* flips the switch and is sent on. Last write wins, so a
fed switch is a display: flipping it sends a value that lasts until the next one
arrives. When the feeding edge goes, the switch keeps its last value.
