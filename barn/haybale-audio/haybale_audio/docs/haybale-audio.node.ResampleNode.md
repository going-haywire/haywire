# Resample

`haybale-audio:node:ResampleNode` · kind: node

Converts audio blocks to another sample rate and delivers them to Audio Event nodes

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to convert |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `target_rate` | resample | `48000` | Samples per second of the delivered blocks. |
| `quality` | resample | `'Fast'` | Fast costs about 0.25% of real time for stereo and is clean for speech and music. |

## Notes

Converts each block that reaches `Write` to `Sample Rate` and delivers it to every Audio Event
listening. The filter keeps its state between blocks, so the joins are seamless. The first block
after a start or a format change can come out shorter or not at all while the filter fills.

Block sizes change with the rate (a 441-sample block at 44.1 kHz gives about 480 at 48 kHz); put a
Reblock after it where a fixed size is needed.

Inputs:
    write: Convert the block on `audio`
    audio: The block to convert
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    next: Control flow after the block is taken in
