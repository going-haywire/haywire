# MapsString to Array

`example:adapter:MapsStringArrayAdapter` · kind: adapter

Transform MapsString elements (MapsStringType[str, X] → ArrayType[Y])

## Details

- **converts_from**: `example:type:MapsStringType`
- **converts_to**: `core:type:ArrayType`
- **priority**: `0`

## Notes

Transforms MapsStringType[str, X] → ArrayType[Y].

Uses internal adapter chain for element transformation.
Always skips None values to prevent chain failures.

Examples:
    # MapsStringType[FLOAT] → ArrayType[FLOAT] (no element transformation)
    adapter = MapsStringArrayAdapter()
    result = adapter.convert({"a": 1.0, "b": 2.0, "c": 3.0})
    # → [1.0, 2.0, 3.0]

    # MapsStringType[FLOAT] → ArrayType[STRING] (with element transformation)
    float_to_str = FloatToStringAdapter()
    adapter = MapsStringArrayAdapter(_chain=float_to_str)
    result = adapter.convert({"a": 1.5, "b": None, "c": 2.7})
    # → ["1.50", "2.70"]  (None skipped)
