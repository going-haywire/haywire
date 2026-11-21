# String Map

`haybale-example:type:STRING_MAP` · kind: type

Map with key type string

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': []}`
- **color**: `#39f55f`

## Notes

Maps string keyed typed array compound type.

Arrays store lists of elements of a specific type.
All elements must be the same type (or compatible via adapters).

Usage:
    # STRING_MAP of floats
    STRING_MAP[FLOAT].as_inlet(id='numbers', default=[1.0, 2.0, 3.0])

    # STRING_MAP of meshes
    STRING_MAP[MeshData].as_outlet(id='meshes')

Storage: STRING_MAP stores Map[str, T] with unwrapped elements

Hooks: Uses default implementations from IType
- _validate_port_type: Allows all port types (inlet, outlet, config)
- _configure_port: No special configuration needed
