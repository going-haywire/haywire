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
| `device` | output | `'System default'` | Output device to play on. The list is read when the node is shown. |
| `buffer_ms` | output | `100` | Buffer of the sound device itself. Raise it when playback crackles while other work keeps the computer busy; 0 uses the device's own default. |
| `prefill` | output | `8` | Blocks queued before playback starts and kept queued. More blocks ride out longer stalls of the flow, with more delay. |

## Notes

Plays each block on an output device. The first block opens the device at its own sample rate;
blocks are converted to it, and a mono block plays on both speakers of a stereo device.

Playback starts once the prefill is queued and restarts after a stall. A producer clock that
differs slightly from the device clock is absorbed by adjusting the conversion ratio.

Crackling means the computer was too busy to feed the device in time. The status shows two
counters: `stalls` are times the flow did not deliver blocks fast enough (raise Prefill), `late`
are times the device itself ran dry (raise Device Buffer).

Inputs:
    write: Queue the block on `audio` (wire it to an Audio Event's Block Ready)
    stop: Close the device; the next `write` opens it again
    audio: The block to play

Outputs:
    next: Control flow after a block is queued
    depth: Frames queued for the device
