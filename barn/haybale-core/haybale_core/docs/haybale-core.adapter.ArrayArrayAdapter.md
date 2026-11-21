# Array to Array

`haybale-core:adapter:ArrayArrayAdapter` · kind: adapter

Transform array elements (ARRAY[X] → ARRAY[Y])

## Details

- **converts_from**: `haybale-core:type:ARRAY`
- **converts_to**: `haybale-core:type:ARRAY`
- **priority**: `0`

## Notes

Transforms ARRAY[X] → ARRAY[Y].

Uses internal adapter chain for element transformation.
Always skips None values to prevent chain failures.

Examples:
    # ARRAY[FLOAT] → ARRAY[FLOAT] (no element transformation)
    adapter = ArrayArrayAdapter()
    result = adapter.convert([1.0, 2.0, 3.0])
    # → [1.0, 2.0, 3.0]

    # ARRAY[FLOAT] → ARRAY[STRING] (with element transformation)
    float_to_str = FloatToStringAdapter()
    adapter = ArrayArrayAdapter(element_adapter=float_to_str)
    result = adapter.convert([1.5, None, 2.7])
    # → ["1.50", "2.70"]  (None skipped)
