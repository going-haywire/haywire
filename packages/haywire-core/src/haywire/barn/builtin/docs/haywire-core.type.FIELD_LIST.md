# Field list

`haywire-core:type:FIELD_LIST` · kind: type

Fields declared by key and type

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'entries': []}`
- **widget_key**: `haywire-core:widget:FieldListWidget`
- **color**: `#78909c`

## Notes

Fields declared by key and type, edited as a list in the Properties panel.

A key holds letters, digits and `_`, and appears once. Every change returns a
new list; write it back to the setting.

```python
class fields(NodeSettings):
    stamp = setting[FIELD_LIST](FIELD_LIST, label="Stamp", promotable=Promotable.NONE)

self.fields.stamp = self.fields.stamp.with_added("camera_timestamp", FLOAT)
```
