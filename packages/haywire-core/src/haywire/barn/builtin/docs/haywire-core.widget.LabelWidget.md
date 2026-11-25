# LabelWidget

`haywire-core:widget:LabelWidget` · kind: widget

Label for display only

## Details

- **min_width**: `120`

## Notes

Read-only label widget that displays the port value as text.

Text and numbers show as they are; any other value, such as a path, shows in
its text form (`scans:in/a.png`). The text stays on one line: when it is wider
than the node it is cut with an ellipsis, and hovering it shows all of it. So a
long status line, or one that changes while the graph runs, never sets the
node's width. No configuration options.

```python
LabelWidget.config()
```
