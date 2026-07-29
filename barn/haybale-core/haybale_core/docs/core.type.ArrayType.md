# Array

`core:type:ArrayType` · kind: type

Homogeneous typed array

## Details

- **flow_type**: `none`
- **default**: `{'value': []}`
- **color**: `#d8e91e`

## Notes

Homogeneous typed array compound type.

Arrays store lists of elements of a specific type.
All elements must be the same type (or compatible via adapters).

Usage:
    # Array of floats
    ArrayType[FLOAT].as_inlet(id='numbers', default=[1.0, 2.0, 3.0])

    # Array of meshes
    ArrayType[MeshData].as_outlet(id='meshes')

Storage: ArrayField stores List[T] with unwrapped elements
Transfer: List of unwrapped values (primitives or instances)

IMPORTANT:
It inherits the element type's flow type (if it is set).
!!Setting the flow type in the decorator or as_inlet/as_outlet has no effect!!

Hooks: Uses default implementations from IType
- _validate_port_type: Allows all port types (inlet, outlet, config)
- _configure_port: Sets flow type based on element type
