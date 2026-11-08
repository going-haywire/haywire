# Callback Image

`haybale-image:type:CALLBACK_IMAGE` · kind: type

Subscription for emitters that deliver single images

## Details

- **wire_type**: `haywire-core:wire:CallbackWire`
- **color**: `#3f8fd2`

## Notes

Subscription value: the callback name a listener registers under.

A `BaseType` on `CallbackWire`, deliberately not a subclass of the core `CALLBACK`
(or of any other callback type): only an emitter whose pooled inlet is
`PooledType[CALLBACK_IMAGE]` connects to an Image Event node.

The emitter's payload for each image:
`{"image": ImageValue, "timestamp": float, "frame_number": int}`.

Attributes:
    name: Callback event name used for dispatch routing.
