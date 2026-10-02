# Callback Signal

`haywire-core:type:CALLBACK` · kind: type

Signal for callback execution between nodes

## Details

- **flow_type**: `callback`
- **default**: `{'value': ''}`
- **color**: `#ff3c00`

## Notes

Callback signal: the name a listener subscribes under.

It travels like a `STRING`, has no widget, and a port stores it only when its
node set it. An empty name means no subscription: an emitter drops it.
