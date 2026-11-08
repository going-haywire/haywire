# Audio Clock

`haybale-audio:node:AudioClockNode` · kind: node

Emits a silent audio block at a steady rate

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `sample_rate` | clock | `48000` | Samples per second of the blocks. |
| `block_size` | clock | `256` | Samples per block. 256 at 48 kHz is a block every 5.3 ms. |

## Notes

Paces audio flows: one silent single-channel block per period, to every Audio Event listening.

Wire the Audio Event that triggers a mixer to this node; the mixer then runs once per block.

Inputs:
    start / stop: Begin or end the ticks
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    started / stopped: Control flow after the matching input
