# Carrier

`haywire-core:type:CARRIER` · kind: type

Any value that can hold fields, such as an image or a bundle.

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': {}}`
- **color**: `#78909c`

## Notes

Any value that can hold named fields: an image, a depth map or a bundle.

An inlet of this type accepts every type derived from it. To make a type a
carrier, derive from `CARRIER`, set `element_type_cls` to a value class derived
from `CarrierValue`, and pass `hidden=False` to `@type`. The value is never saved.

```python
@type(label="Mesh", default={"value": {}}, hidden=False)
class MESH(CARRIER):
    element_type_cls = MeshValue

    @classmethod
    def empty_value(cls):
        return MeshValue()
```
