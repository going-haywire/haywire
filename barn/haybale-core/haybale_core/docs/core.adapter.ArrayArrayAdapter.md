# Array to Array

`core:adapter:ArrayArrayAdapter` · kind: adapter

Transform array elements (ArrayType[X] → ArrayType[Y])

## Details

- **converts_from**: `core:type:ArrayType`
- **converts_to**: `core:type:ArrayType`
- **priority**: `0`

## Notes

Transforms ArrayType[X] → ArrayType[Y].

Uses internal adapter chain for element transformation.
Always skips None values to prevent chain failures.

Examples:
    # ArrayType[FLOAT] → ArrayType[FLOAT] (no element transformation)
    adapter = ArrayArrayAdapter()
    result = adapter.convert([1.0, 2.0, 3.0])
    # → [1.0, 2.0, 3.0]

    # ArrayType[FLOAT] → ArrayType[STRING] (with element transformation)
    float_to_str = FloatToStringAdapter()
    adapter = ArrayArrayAdapter(element_adapter=float_to_str)
    result = adapter.convert([1.5, None, 2.7])
    # → ["1.50", "2.70"]  (None skipped)
