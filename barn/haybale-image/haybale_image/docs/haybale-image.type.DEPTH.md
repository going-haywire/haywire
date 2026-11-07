# Depth

`haybale-image:type:DEPTH` · kind: type

A depth map, one value per pixel in millimetres.

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': {}}`
- **color**: `#00838f`

## Notes

A depth map: one value per pixel, in millimetres.

It is not an image, so it does not connect to image inlets. Use a node to turn it
into something viewable. The value is never saved with the graph.
