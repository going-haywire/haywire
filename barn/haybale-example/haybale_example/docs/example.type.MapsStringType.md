# Array

`example:type:MapsStringType` · kind: type

Map with key type string

## Details

- **flow_type**: `data`
- **default**: `{'value': []}`
- **color**: `#39f55f`

## Notes

Maps string keyed typed array compound type.

Arrays store lists of elements of a specific type.
All elements must be the same type (or compatible via adapters).

Usage:
    # MapsStringType of floats
    MapsStringType[FLOAT].as_inlet(id='numbers', default=[1.0, 2.0, 3.0])

    # MapsStringType of meshes
    MapsStringType[MeshData].as_outlet(id='meshes')

Storage: MapsStringType stores Map[str, T] with unwrapped elements

Hooks: Uses default implementations from IType
- _validate_port_type: Allows all port types (inlet, outlet, config)
- _configure_port: No special configuration needed
