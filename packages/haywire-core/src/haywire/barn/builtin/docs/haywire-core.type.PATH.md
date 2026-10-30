# Path

`haywire-core:type:PATH` · kind: type

A file or folder inside a named volume such as the project folder or `models`. The graph stores the volume and the path within it, so it keeps working on another machine.

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': {'volume': 'haywire-core:volume:project', 'relative': ''}}`
- **widget_key**: `haywire-core:widget:PathWidget`
- **color**: `#c9a66b`

## Notes

A file or folder inside a named volume such as the project folder or `models`.

Pick the volume, then type or browse to the path within it.
