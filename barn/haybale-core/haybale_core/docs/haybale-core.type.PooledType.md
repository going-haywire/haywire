# Pooled

`haybale-core:type:PooledType` · kind: type

Multi-source aggregation

## Details

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
    It travels on the element type's wire type; a wire type declared in as_inlet() has no effect.

Storage: PooledField stores Dict[str, T] with unwrapped values
Worker Access: Dict[str, T] or List[T]

Hooks:
- _validate_port_type: Overridden to prevent outlets
- _configure_port: Overridden to set allow_multiple_links
