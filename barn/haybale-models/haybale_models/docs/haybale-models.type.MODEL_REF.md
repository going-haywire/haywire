# Model

`haybale-models:type:MODEL_REF` · kind: type

A model, named by a catalog entry or by a file (url and sha256). Resolve Model turns it into a path on disk.

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': {}}`
- **widget_key**: `haybale-models:widget:ModelRefWidget`
- **color**: `#b07ad9`

## Notes

A model, named by a catalog entry or by a file.

The port's `filter` narrows the picker by catalog field; `prefer` is an ordered
list of tag sets used to pick a variant.
