# Channel Split

`haybale-audio:node:ChannelSplitNode` · kind: node

Gives each channel of an audio block its own output

## Ports

| id | direction | type | description |
|---|---|---|---|
| `audio` | inlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |
| `ch_0` | outlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |

## Notes

Outputs single channels of the input block. Output `Channel 0` is the first channel, `Channel 1`
the second, and so on.

Connect the open output at the bottom to something: it becomes the output for the next channel
and a new open output appears below. Removing an output leaves the numbers of the others as they
are. An error names a channel the block does not have.
