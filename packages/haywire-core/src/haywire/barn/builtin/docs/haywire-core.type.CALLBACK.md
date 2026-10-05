# Callback Signal

`haywire-core:type:CALLBACK` · kind: type

Signal for callback execution between nodes

## Details

- **wire_type**: `haywire-core:wire:CallbackWire`
- **color**: `#ff3c00`

## Notes

Callback signal: the name a listener subscribes under.

It travels like a `STRING`, has no widget, and a port stores it only when its
node set it. An absent value means no subscription: an emitter's pool drops it.
