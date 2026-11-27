# Clip Callback

`haybale-audio:type:CLIP_CALLBACK` · kind: type

Subscription for emitters that deliver whole audio clips

## Details

- **wire_type**: `haywire-core:wire:CallbackWire`
- **color**: `#2f7fb0`

## Notes

Subscription value: the callback name a Clip Event registers under.

Independent of `AUDIO_CALLBACK`: a clip emitter (Clip Segmenter) connects only to Clip Event
nodes, and an audio emitter only to Audio Event nodes.

The emitter's payload for each clip:
`{"clip": AudioBlock, "timestamp": float, "clip_number": int}`.

Attributes:
    name: Callback event name used for dispatch routing.
