# Audio Mixer

`haybale-audio:node:AudioMixerNode` · kind: node

Sums several audio sources into one block per clock tick

## Ports

| id | direction | type | description |
|---|---|---|---|
| `tick` | inlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `in_0` | inlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `mixed` | outlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `prefill` | mixer | `8` | Blocks an input queues before it is mixed. More blocks ride out longer stalls. |

## Notes

Mixes live sources that run on their own flows. Each source has its own input: connect its audio
output to the open input at the bottom and it gets a `Gain` and a `Mute`; a new open input appears
below. Removing an input from its pin menu removes its `Gain` and `Mute` with it.

An input collects every block its source delivers, at the source's own pace, until the next tick.
Wire an Audio Clock's Audio Event `Block Ready` to `Tick`. `Tick` is the moment to mix one block:
each tick takes what every input collected and mixes one block per input. The block that triggered
the tick sets the sample rate and block size of the output; it is not mixed in. The sources are the
numbered inputs. Inputs at another sample rate or block size are converted, and a source clock that
differs slightly from the tick clock is absorbed.

An input is mixed once its prefill is queued, and again after a stall; until then it is silent. The
sum is not limited, so loud sources can exceed ±1; the output has the most channels of any input, and
a mono input plays on all of them. An input holds 192 blocks between two ticks (about a second of
256-sample blocks at 48 kHz); when the ticks stop for longer, the oldest blocks are dropped and the
status counts them.

Inputs:
    tick: Mix one block (wire it to the clock's Block Ready); the triggering block sets the output
    in_N: An input's audio, collected until the next tick
    gain_N / mute_N: An input's level and mute

Outputs:
    next: Control flow after a block is mixed
    mixed: The mixed block
