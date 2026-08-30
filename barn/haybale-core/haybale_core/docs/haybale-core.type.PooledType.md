# Pooled

`haybale-core:type:PooledType` · kind: type

Multi-source aggregation

## Details

- **flow_type**: `none`
- **default**: `{'value': {}}`
- **color**: `#9c27b0`

## Notes

Pooled compound type for multi-source aggregation.

Pooled inlets accept connections from multiple upstream nodes
and aggregate their values into a dictionary keyed by source ID.

Usage:
    # Pooled floats
    PooledType[FLOAT].as_inlet(id='values')

    # Pooled meshes
    PooledType[MeshData].as_inlet(id='mesh_collection')

Note: Pooled is INLET-ONLY - cannot be used with outlets!

It sets the pin to allow multiple connections automatically.

IMPORTANT:
    It inherits the element type's flow_type (if it is set).
    Setting the flow type here in the
        * as_inlet() has no effect
    if the element type has a flow_type defined.

Storage: PooledField stores Dict[str, T] with unwrapped values
Worker Access: Dict[str, T] or List[T]

Hooks:
- _validate_port_type: Overridden to prevent outlets
- _configure_port: Overridden to set allow_multiple_links
