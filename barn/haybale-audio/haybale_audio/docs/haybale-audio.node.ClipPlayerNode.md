# Clip Player

`haybale-audio:node:ClipPlayerNode` · kind: node

Plays an audio clip as audio blocks, in real time

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `clip` | inlet | `haybale-audio:type:AUDIO_CLIP` | Audio clip to play |
| `callbacks` | inlet | `haybale-core:type:POOLED` | Connect to an Audio Event node. |
| `finish_callbacks` | inlet | `haybale-core:type:POOLED` | Tick Event Listen outlets whose flows run when a clip has played to its end |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `block_size` | playback | `256` | Samples per block. The clip's own sample rate and channels are kept. |
| `loop` | playback | `False` | Start again at the end of the clip instead of stopping. |
| `keep_running` | playback | `False` | After the clip, send silent blocks until Stop instead of stopping. For a player wired to an Audio Mixer: the mixer sees one source that never ends, so a clip's end is no stall. |

## Notes

Cuts an audio clip, such as a spoken sentence, into blocks and delivers them, paced at the
clip's sample rate, to every Audio Event listening. The clip's own sample rate and channel count
are kept: Device Out and the Audio Mixer convert it, and Resample does for any other node.

`On Finish` runs the Tick Events wired to it when a clip has played to its end (with
`Keep Running`, when its silence begins); a Stop runs none. Wire it to a Clip Queue's Pop to
play queued clips one after another.

A Start while a clip plays switches to the clip now on `Clip`, from its first block and without a
gap. A new value on `Clip` alone changes nothing until the next Start.

`Keep Running` sends silent blocks after the clip until Stop. Turn it on when the player feeds an
Audio Mixer: otherwise each clip's end counts as a stall in the mixer's status, and each clip
starts only once the mixer's prefill is queued again.

Inputs:
    start / stop: Begin playing the clip on `clip`, or end playback
    clip: The audio clip to play
    callbacks: Pooled AUDIO_CALLBACK subscriptions from Audio Event nodes
    finish_callbacks: Pooled CALLBACK subscriptions from the Tick Events to run at a clip's end

Outputs:
    started / stopped: Control flow after the matching input
