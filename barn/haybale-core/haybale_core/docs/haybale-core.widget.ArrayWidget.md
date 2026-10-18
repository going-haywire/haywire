# ArrayWidget

`haybale-core:widget:ArrayWidget` · kind: widget

List editor — one row per item, each drawn by the item type's widget

## Details


## Notes

Edits a list: one row per item, plus controls to add, remove and reorder items.

Each row is the item type's own widget: a text field for `ArrayType[STRING]`,
a number field for `ArrayType[INT]` and `ArrayType[FLOAT]`. Add appends the
item type's default (`""`, `0`, `0.0`). Drag a row by its grip to move it;
the cross on its right removes it.

`ArrayType` does not use this widget by default. Name it on the setting or
port that should show a list editor:

```python
class Settings(NodeSettings):
    options = setting[ArrayType[STRING]](
        ["One", "Two", "Three"], label="Options", widget=ArrayWidget.config()
    )

def init(self):
    self.add(
        ArrayType[FLOAT].as_inlet("weights", default={"value": [1.0]}, widget=ArrayWidget.config())
    )
```

Config options (via `ArrayWidget.config(properties={...})`):

- `item` (dict): widget properties for every row, on top of the item
  type's own. For example, commit-mode text rows that write only on Enter
  or blur:

```python
ArrayWidget.config(properties={"item": {"commit": True}})
```

An item type without a widget shows a read-only item count instead of rows.
