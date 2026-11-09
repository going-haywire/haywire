# Audio Mixer

`haybale-audio:node:AudioMixerNode` · kind: node

Sums several audio sources into one block per clock tick

## Ports

| id | direction | type | description |
|---|---|---|---|
| `tick` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `clock` | inlet | `haybale-audio:type:AUDIO` | Block of the Audio Clock |
| `in_0` | inlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `mixed` | outlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `prefill` | mixer | `4` | Blocks an input queues before it is mixed. More blocks ride out longer stalls. |

## Notes

Mixes live sources that run on their own flows. Each source has its own input: connect its audio
output to the open input at the bottom and it gets a `Write` pin, a `Gain` and a `Mute`; a new open
input appears below.

Wire each source's Audio Event Block Ready to its `Write` pin: the block is queued for that input.
Wire an Audio Clock's Audio Event to `Tick` and `Clock`: every tick mixes one block per input, in the
clock's sample rate and block size. Inputs at another sample rate or block size are converted, and
a source clock that differs slightly from the tick clock is absorbed.

An input is mixed once its prefill is queued, and again after a stall; until then it is silent. The
sum is not limited, so loud sources can exceed ±1; the output has the most channels of any input, and
a mono input plays on all of them.

Inputs:
    tick: Mix one block (wire it to the clock's Block Ready)
    clock: The clock's block; its sample rate and size set the output
    in_N / write_N: An input's audio and the pin that queues it
    gain_N / mute_N: An input's level and mute

Outputs:
    next: Control flow after a block is mixed
    mixed: The mixed block
