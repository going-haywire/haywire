# Device In

`haybale-audio:node:DeviceInNode` · kind: node

Records a sound device's input as audio blocks

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `callbacks` | inlet | `haybale-core:type:POOLED` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `device` | recording | `'System default'` | Input device to record from. The refresh button reads the devices again, for one plugged in since the studio started; it works only while no audio node of the studio is running. |
| `channels` | recording | `'All device channels'` | Channels to record. More than the device has records all of the device's. |
| `sample_rate` | recording | `'Device default'` | Samples per second. The device's own rate needs no conversion by the sound system. |
| `block_size` | recording | `256` | Samples per block. 256 at 48 kHz is a block every 5.3 ms. |

## Notes

Records from an input device and delivers its blocks to every Audio Event listening.

The device is a microphone or an audio interface; the blocks come at the pace of its own clock.

The status shows what the device really delivers: channels, sample rate, block size and its
input latency. A device can impose its own block size: the status then shows the size asked
for in brackets, and a Reblock node fixes the size where a node needs it.

Two counters show lost audio. `lost` counts blocks dropped because the flow ran behind for
more than half a second. `overflow` counts the times the device itself lost input because the
program was busy too long.

Wired to a Device Out, the two devices run on two clocks that differ slightly; Device Out
absorbs the difference.

Inputs:
    start / stop: Begin or end recording
    callbacks: Pooled AUDIO_CALLBACK subscriptions from Audio Event nodes

Outputs:
    started / stopped: Control flow after the matching input
