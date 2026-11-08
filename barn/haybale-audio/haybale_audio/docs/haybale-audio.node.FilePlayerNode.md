# File Player

`haybale-audio:node:FilePlayerNode` · kind: node

Plays an audio file as audio blocks, in real time

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `path` | inlet | `haywire-core:type:FILE_PATH` | Audio file to play |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `block_size` | playback | `256` | Samples per block. The file's own sample rate and channels are kept. |
| `loop` | playback | `False` | Start again at the end of the file instead of stopping. |

## Notes

Reads an audio file from a volume and delivers it, paced at the file's sample rate, to every
Audio Event listening. The file's own sample rate and channel count are kept: a node that needs
another format converts it (Reblock/Resample).

Inputs:
    start / stop: Begin or end playback
    path: Audio file to play
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    started / stopped: Control flow after the matching input
