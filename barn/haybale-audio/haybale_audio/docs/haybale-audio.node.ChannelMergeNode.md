# Channel Merge

`haybale-audio:node:ChannelMergeNode` · kind: node

Stacks audio blocks into one block with all their channels

## Ports

| id | direction | type | description |
|---|---|---|---|
| `in_0` | inlet | `haywire-core:type:ADD` | Grows a new port from whatever connects to it |
| `merged` | outlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |

## Notes

Joins the blocks on its inputs, in order, into one block. A single-channel input adds one
channel; a multichannel input adds all of its channels.

Connect an audio output to the open input at the bottom: it becomes an input of its own and a
new open input appears below. Inputs without a block are skipped. All blocks must have the same
sample rate and number of samples; an error names the difference.
