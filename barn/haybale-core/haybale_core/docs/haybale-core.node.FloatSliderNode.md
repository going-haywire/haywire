# Float Slider

`haybale-core:node:FloatSliderNode` · kind: node

A slider that sends a decimal number, and shows the one it is fed

## Ports

| id | direction | type | description |
|---|---|---|---|
| `in` | inlet | `haywire-core:type:FLOAT` | Decimal number |
| `value` | outlet | `haywire-core:type:FLOAT` | Decimal number |

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
| `min` | range | `0.0` | The slider's left end |
| `max` | range | `1.0` | The slider's right end |
| `step` | range | `0.01` | The smallest change the slider makes |

## Notes

A slider that sends a decimal number from Min to Max.

A value arriving at *In* moves the slider and is sent on. Last write wins, so a
fed slider is a display: dragging it sends a value that lasts until the next one
arrives. When the feeding edge goes, the slider keeps its last value.

*Min*, *Max* and *Step* can be promoted to inlets. Nothing clamps the value: one
outside the range is sent on unchanged.
