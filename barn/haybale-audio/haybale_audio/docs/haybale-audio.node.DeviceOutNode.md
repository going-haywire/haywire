# Device Out

`haybale-audio:node:DeviceOutNode` · kind: node

Plays audio blocks on a sound device

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to play |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `depth` | outlet | `haywire-core:type:INT` | Whole number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `device` | output | `''` | Name (or part of it) or number of the output device. Empty uses the system default. |
| `prefill` | output | `4` | Blocks queued before playback starts. More blocks survive longer stalls but add delay. |

## Notes

Plays each block on an output device. The first block opens the device at its own sample rate;
blocks are converted to it, and a mono block plays on both speakers of a stereo device.

Playback starts once the prefill is queued and restarts after a stall. A producer clock that
differs slightly from the device clock is absorbed by adjusting the conversion ratio.

Inputs:
    write: Queue the block on `audio` (wire it to an Audio Event's Block Ready)
    stop: Close the device; the next `write` opens it again
    audio: The block to play

Outputs:
    next: Control flow after a block is queued
    depth: Frames queued for the device
