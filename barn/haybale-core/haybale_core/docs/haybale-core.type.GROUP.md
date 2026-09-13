# Group

`haybale-core:type:GROUP` · kind: type

Inlet group

## Details

- **flow_type**: `data`
- **default**: `{'value': False}`
- **widget_key**: `haywire-core:widget:SwitchWidget`
- **color**: `#ebff0f`

## Notes

Group data type.

Superseded by ``NodeData.fold()``, which mints a `FOLD` port of its own.
Kept for graphs saved before the change; new nodes use ``fold()``.
