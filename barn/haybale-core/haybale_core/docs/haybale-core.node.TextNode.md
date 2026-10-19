# Text

`haybale-core:node:TextNode` · kind: node

A text field that sends its text on Enter, and shows the text it is fed

## Ports

| id | direction | type | description |
|---|---|---|---|
| in | inlet | haywire-core:type:STRING | Text data |
| value | outlet | haywire-core:type:STRING | Text data |

## Settings

| name | bag | default | description |
|---|---|---|---|
| label_position | style | 'left' | Where the label sits: left of the control, above it, or not at all |
| max_label_width | style | None | The widest the label gets when it is on the left: it takes half the row up to this width. None is 9rem, as in the properties panel |
| label_align | style | 'left' |  |
| font | style | 'sans' |  |
| font_size | style | 14 | Size of the label in pixels |
| bold | style | False |  |
| italic | style | False |  |
| label_color | style | '' | Empty uses the theme's text color |
| background | style | '' | Fill behind the label and control; empty draws none |
| border | style | False | Draw the theme's node border around the card |

## Notes

A text field that sends its text when you press Enter or leave the field.

Nothing is sent while you type, so a consumer never sees a half-typed value. A
text arriving at *In* shows in the field and is sent on. Last write wins, so a
fed field is a display. When the feeding edge goes, the field keeps its last text.
