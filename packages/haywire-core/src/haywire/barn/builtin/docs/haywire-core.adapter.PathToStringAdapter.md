# PathToStringAdapter

`haywire-core:adapter:PathToStringAdapter` · kind: adapter

Convert a path to text: the volume's name and the path inside it

## Details

- **converts_from**: `haywire-core:type:PATH`
- **converts_to**: `haywire-core:type:STRING`
- **priority**: `0`

## Notes

Convert a path to its display form, `volume name:relative`, the same on every machine.

For the location on this machine, use the Resolve Path node.
