# Untyped List

`haybale-core:type:LIST` · kind: type

Ordered collection of values of any type

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': []}`
- **color**: `#e91e63`

## Notes

An ordered list whose items may be of any type and are not checked.

Use `ARRAY[T]` for a list of one item type: the port knows the item type, so pins and
adapters follow it. `LIST` is for values whose items have no single type.
