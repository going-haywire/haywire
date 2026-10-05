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

Its field keeps one value per source, so the inlet takes many edges (see `DataPort.takes_many_links`).

IMPORTANT:
    as_inlet() refuses a wire_type kwarg; the port travels on its element type's wire type.

Storage: PooledField stores Dict[str, T] with unwrapped values
Worker Access: Dict[str, T] or List[T]

Hooks:
- _validate_port_type: Overridden to prevent outlets
- _configure_port: takes the element's colour and refuses a control element
