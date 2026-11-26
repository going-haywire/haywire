# LabelWidget

`haywire-core:widget:LabelWidget` · kind: widget

Label for display only

## Details

- **min_width**: `120`

## Notes

Read-only label widget that displays the port value as text.

Text and numbers show as they are; any other value, such as a path, shows in
its text form (`scans:in/a.png`). The text never sets the node's width. On a
node, hovering it shows the port's name and type with the whole text below.

By default the text stays on one line: when it is wider than the node it is
cut with an ellipsis. The node keeps its height however the text changes,
which suits a status line written while the graph runs.

Options (in `properties`):

- `wrap`: `True` breaks the text onto more lines when the node is narrower
  than it. The label grows up to 80 px tall (set `max_height` to change it);
  text past that is clipped. Suits text that rarely changes, such as a
  description or a result: a wrapped text that changes its number of lines
  changes the node's height.

```python
LabelWidget.config()                                  # one line, cut with an ellipsis
LabelWidget.config(properties={"wrap": True})         # wraps, up to 80 px tall
LabelWidget.config(properties={"wrap": True}, max_height=160)
```
