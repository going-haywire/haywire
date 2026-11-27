# Clip Event

`haybale-audio:node:ClipEventNode` · kind: node

Triggered for each audio clip a connected clip emitter delivers

## Ports

| id | direction | type | description |
|---|---|---|---|
| `listen_callback` | outlet | `haybale-audio:type:CLIP_CALLBACK` | Subscription for emitters that deliver whole audio clips |
| `clip_ready` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `clip` | outlet | `haybale-audio:type:AUDIO_CLIP` | A whole audio clip, such as one utterance, as one block. Never saved with the graph. |
| `timestamp` | outlet | `haywire-core:type:FLOAT` | Decimal number |
| `clip_number` | outlet | `haywire-core:type:INT` | Whole number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `queue_mode` | dispatch | `'Block (every clip)'` | Block queues every clip and holds the emitter back when the queue is full. Drop keeps only the newest clip, so clips are lost whenever the flow runs behind. |
| `max_queue_size` | dispatch | `16` | How many clips wait while the flow runs. |
| `mode` | delivery | `'Every'` | Every runs this flow for every event. Pooled shares the events with the other pooled listeners of the same emitter: the next free one runs each event. |

## Notes

Runs its flow once per clip from the emitter it is wired to.

Connect `Listen` to the clip-callback inlet of a clip emitter, such as Clip Segmenter's
`Subscribers`. The emitter sends `{"clip": AudioBlock, "timestamp": float, "clip_number": int}`.

`Clip Ready` is plain control flow: the flow may take as long as it needs, such as a speech
model transcribing the clip, and the emitter's audio flow goes on meanwhile.

Delivery: `Every` runs the flow for every clip. `Pooled` shares the clips with the emitter's
other pooled listeners: the next free one takes each clip, so two pooled flows with a slow
model each work on a clip at once. Queue Mode and Max Queue Size then have no effect; the
emitter's Backlog holds the clips that wait. Two pooled flows run at once only when they share
no control node: flows that share one run one after the other.

Outputs:
    clip_ready: Control flow when a clip arrives
    clip: The clip
    timestamp: Where the clip starts, in seconds since the emitter's first block
    clip_number: The count of clips the emitter has sent
