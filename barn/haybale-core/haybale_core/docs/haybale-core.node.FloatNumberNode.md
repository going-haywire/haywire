# Float Number

`haybale-core:node:FloatNumberNode` · kind: node

A number box that sends a decimal number, and shows the one it is fed

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
| `min` | range | `None` | The lowest value; none is unbounded |
| `max` | range | `None` | The highest value; none is unbounded |
| `step` | range | `0.1` | How much one drag step or arrow changes it |

## Notes

A number box that sends a decimal number: drag it, or click and type.

A value arriving at *In* shows in the box and is sent on. Last write wins, so a
fed box is a display: a value typed into it lasts until the next one arrives.
When the feeding edge goes, the box keeps its last value.

*Min* and *Max* are unbounded until set. They and *Step* can be promoted to
inlets. Nothing clamps the value: one outside the range is sent on unchanged.
