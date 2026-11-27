# Clip Segmenter

`haybale-audio:node:ClipSegmenterNode` · kind: node

Cuts a live audio flow into clips at the pauses, such as one clip per sentence

## Ports

| id | direction | type | description |
|---|---|---|---|
| `add` | inlet | `haybale-audio:type:AUDIO_EXEC` | Signal for sequencing the nodes of an audio flow |
| `cut` | inlet | `haywire-core:type:EXEC` | End the open segment now and send it |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to listen to |
| `callbacks` | inlet | `haybale-core:type:POOLED` | Connect to the Clip Event nodes that get the clips. |
| `threshold` | config | `haywire-core:type:FLOAT` | Level (RMS) above which a block counts as sound |
| `hangover_ms` | config | `haywire-core:type:INT` | Pause that ends a segment |
| `preroll_ms` | config | `haywire-core:type:INT` | Audio kept from before the first loud block |
| `min_seconds` | config | `haywire-core:type:FLOAT` | Shortest sound sent; shorter is discarded |
| `max_seconds` | config | `haywire-core:type:FLOAT` | Longest segment; a longer one is cut there |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:AUDIO_EXEC` | Signal for sequencing the nodes of an audio flow |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `size` | backlog | `16` | How many events wait while every pooled listener is busy. |
| `full` | backlog | `'Drop oldest'` | Drop oldest makes room by losing the oldest waiting event. Wait holds the emitter up to 5 s for room, then loses the new event. |

## Notes

Listens to an audio flow and sends each stretch of sound, such as a sentence, as a clip.

The clip keeps the flow's sample rate and channels; Transcribe converts it for its model.

A block is loud when its level (RMS) is above `Threshold`. The first loud block opens a
segment, together with the `Pre-roll` before it, so a quiet first sound is kept. A pause
of `Hang-over` ends the segment and the clip goes to every Audio Event listening on
`Subscribers`; the pause itself is left out. Speech shorter than `Min Seconds` (a click, a
cough) is discarded; a segment that reaches `Max Seconds` is sent at once and the next loud
block opens a new one. `Cut` ends the open segment at once, as a pause would. The status
shows the level, which helps to set the threshold.

The clip goes to every Clip Event listening on `Subscribers` and arrives in a flow of its
own, so a slow step, such as a speech model, never holds up the audio flow:

```text
Device In → Audio Event → Clip Segmenter (Add)
Clip Segmenter (Subscribers) ← Clip Event → Clip Ready → Transcribe → Print
```

The Clip Event's `Clip` is the clip, its `Timestamp` the start of the sound in seconds since
the segmenter's first block, and its `Clip Number` the count of clips sent. Clip Events set to
Pooled share the clips, the next free one taking each; `Backlog` holds the clips that wait
while every pooled one is busy.

Inputs:
    add: Feed the block on `audio` (wire it to an Audio Event's Block Ready)
    cut: End the open segment now and send it
    audio: The block
    callbacks: Pooled CLIP_CALLBACK subscriptions from the Clip Event nodes that get the clips
    threshold: Level (RMS) above which a block counts as sound
    hangover_ms: Pause that ends a segment
    preroll_ms: Audio kept from before the first loud block
    min_seconds: Shortest sound sent; shorter is discarded
    max_seconds: Longest segment; a longer one is cut there

Outputs:
    next: Control flow after the block is taken
