# Channel Select

`haybale-audio:node:ChannelSelectNode` · kind: node

Picks, reorders or repeats the channels of an audio block

## Ports

| id | direction | type | description |
|---|---|---|---|
| `audio` | inlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |
| `channels` | config | `haywire-core:type:STRING` | Channel numbers from 0, like 0, 2-3 |
| `selected` | outlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |

## Notes

Builds a block from the channels named in `Channels`, in that order.

`Channels` is a list of channel numbers from 0 and inclusive ranges: `0` is the first channel,
`1, 0` swaps a stereo pair, `0, 0` makes mono into stereo, `2-3` takes the third and fourth.
An error names a channel the block does not have.
