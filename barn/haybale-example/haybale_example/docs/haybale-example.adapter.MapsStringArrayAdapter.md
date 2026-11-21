# MapsString to Array

`haybale-example:adapter:MapsStringArrayAdapter` · kind: adapter

Transform MapsString elements (STRING_MAP[str, X] → ARRAY[Y])

## Details

- **converts_from**: `haybale-example:type:STRING_MAP`
- **converts_to**: `haybale-core:type:ARRAY`
- **priority**: `0`

## Notes

Transforms STRING_MAP[str, X] → ARRAY[Y].

Uses internal adapter chain for element transformation.
Always skips None values to prevent chain failures.

Examples:
    # STRING_MAP[FLOAT] → ARRAY[FLOAT] (no element transformation)
    adapter = MapsStringArrayAdapter()
    result = adapter.convert({"a": 1.0, "b": 2.0, "c": 3.0})
    # → [1.0, 2.0, 3.0]

    # STRING_MAP[FLOAT] → ARRAY[STRING] (with element transformation)
    float_to_str = FloatToStringAdapter()
    adapter = MapsStringArrayAdapter(_chain=float_to_str)
    result = adapter.convert({"a": 1.5, "b": None, "c": 2.7})
    # → ["1.50", "2.70"]  (None skipped)
