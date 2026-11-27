# Audio Clip

`haybale-audio:type:AUDIO_CLIP` · kind: type

A whole audio clip, such as one utterance, as one block. Never saved with the graph.

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'value': {}}`
- **color**: `#2f7fb0`

## Notes

A whole clip as one `AudioBlock`; the value is never saved with the graph.

The value is the same as `AUDIO`'s, but the two ports never connect: a clip travels on control
flow (Collect Clip's Done, Clip Event's Clip Ready), a block on an audio flow. The nodes between
them are Collect Clip and Clip Segmenter (blocks to clips) and Clip Player (a clip to blocks).
