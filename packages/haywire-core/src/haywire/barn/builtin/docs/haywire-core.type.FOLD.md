# Fold

`haywire-core:type:FOLD` · kind: type

Hides or shows the ports inside it

## Details

- **flow_type**: `data`
- **default**: `{'value': True}`
- **color**: `#90a4ae`

## Notes

Fold data type.

Minted by `NodeData.fold()`; never declared directly. Its value is the
fold's open state — `True` while open — which a node may read like any
port, or hook with `on_change=` to reconfigure itself when the user folds.

Pass `description=` to `fold()` to replace the default shown in the fold
header's hover tooltip.
