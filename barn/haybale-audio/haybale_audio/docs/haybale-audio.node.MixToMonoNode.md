# Mix to Mono

`haybale-audio:node:MixToMonoNode` · kind: node

Averages all channels of an audio block into one

## Ports

| id | direction | type | description |
|---|---|---|---|
| `audio` | inlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |
| `mono` | outlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |

## Notes

Outputs one channel that is the average of the input's channels, which keeps the level of a
stereo pair that carries the same signal on both sides.
