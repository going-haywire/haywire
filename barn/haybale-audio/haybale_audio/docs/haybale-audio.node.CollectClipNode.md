# Collect Clip

`haybale-audio:node:CollectClipNode` · kind: node

Gathers the audio blocks of a flow into one clip, sent on Stop

## Ports

| id | direction | type | description |
|---|---|---|---|
| `add` | inlet | `haybale-audio:type:AUDIO_EXEC` | Signal for sequencing the nodes of an audio flow |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to append |
| `max_seconds` | config | `haywire-core:type:FLOAT` | Longest clip kept; later blocks are dropped |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:AUDIO_EXEC` | Signal for sequencing the nodes of an audio flow |
| `done` | outlet | `haywire-core:type:EXEC` | Runs after Stop, once Clip is set |
| `clip` | outlet | `haybale-audio:type:AUDIO_CLIP` | The gathered audio |
| `seconds` | outlet | `haywire-core:type:FLOAT` | Length of the clip so far |

## Notes

Appends each block to a clip in memory; `Stop` sends the clip and starts a new one.

The first block fixes the clip's channel count and sample rate; a later block that differs
is an error. Blocks past `Max Seconds` are dropped, and the status says so.

```text
Device In → Audio Event → Collect Clip (Add)
Run Button → Tick Event → Collect Clip (Stop) → Done → Clip Player (Start), Clip → Clip
```

Inputs:
    add: Append the block on `audio` (wire it to an Audio Event's Block Ready)
    stop: Send the clip on `clip` and continue on `done`; an empty clip sends nothing
    audio: The block to append
    max_seconds: Longest clip kept

Outputs:
    next: Control flow after a block is appended
    done: Control flow after `stop`, once `clip` holds the clip
    clip: The gathered audio, one block
    seconds: Length of the clip so far
