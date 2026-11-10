# Audio Event

`haybale-audio:node:AudioEventNode` · kind: node

Triggered for each audio block a connected audio emitter delivers

## Ports

| id | direction | type | description |
|---|---|---|---|
| `listen_callback` | outlet | `haybale-audio:type:CALLBACK_AUDIO` | Subscription for emitters that deliver audio blocks |
| `block_ready` | outlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `audio` | outlet | `haybale-audio:type:AUDIO` | A block of audio samples. Never saved with the graph. |
| `timestamp` | outlet | `haywire-core:type:FLOAT` | Decimal number |
| `block_number` | outlet | `haywire-core:type:INT` | Whole number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `queue_mode` | dispatch | `'Block (every block)'` | Block queues every block and back-pressures the emitter. Drop keeps only the newest block, so audio is lost whenever the flow runs behind. |
| `max_queue_size` | dispatch | `100` | How many pending blocks to hold. 100 blocks of 256 samples at 48 kHz are about 0.5 s. |

## Notes

Runs its flow once per audio block from the emitter it is wired to.

Connect `Listen` to the audio-callback inlet of an emitter (a device input, a stream
receiver, a file player, a clock). The emitter sends
`{"audio": AudioBlock, "timestamp": float, "block_number": int}`.

Everything wired from `Block Ready` is an audio flow, paced by the emitter's sample rate and block
size. Its execution pins are `EXEC_AUDIO`: `Block Ready`, and the `Write`, `Tick` and `Next` pins of
the audio nodes. A plain `EXEC` outlet does not connect to them, so a control node cannot drive an
audio flow, while an `EXEC_AUDIO` outlet does connect to an `EXEC` inlet, so an audio flow can drive
a control node. That node then runs inside the flow's pass, and its time counts against the block
period. `Start` and `Stop` pins stay plain `EXEC`: the control world starts and stops audio nodes.

Outputs:
    block_ready: Control flow when a block arrives
    audio: The block
    timestamp / block_number: Seconds since the emitter started, and the count
