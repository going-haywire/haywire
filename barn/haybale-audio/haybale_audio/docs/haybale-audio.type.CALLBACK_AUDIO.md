# Callback Audio

`haybale-audio:type:CALLBACK_AUDIO` · kind: type

Subscription for emitters that deliver audio blocks

## Details

- **wire_type**: `haywire-core:wire:CallbackWire`
- **color**: `#4ab0d9`

## Notes

Subscription value: the callback name a listener registers under.

A `BaseType` on `CallbackWire`, independent of the core `CALLBACK` and of every other callback
type: only an emitter whose pooled inlet is `PooledType[CALLBACK_AUDIO]` connects to an
Audio Event node.

The emitter's payload for each block:
`{"audio": AudioBlock, "timestamp": float, "block_number": int}`.

Attributes:
    name: Callback event name used for dispatch routing.
