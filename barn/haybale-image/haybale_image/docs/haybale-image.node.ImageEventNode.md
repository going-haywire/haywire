# Image Event

`haybale-image:node:ImageEventNode` · kind: node

Triggered for each image a connected image emitter delivers

## Ports

| id | direction | type | description |
|---|---|---|---|
| `listen_callback` | outlet | `haybale-image:type:CALLBACK_IMAGE` | Subscription for emitters that deliver single images |
| `frame_ready` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `image` | outlet | `haybale-image:type:IMAGE` | A picture of any channel layout. Pixels are kept as made and converted on demand. |
| `timestamp` | outlet | `haywire-core:type:FLOAT` | Decimal number |
| `frame_number` | outlet | `haywire-core:type:INT` | Whole number |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `queue_mode` | dispatch | `'Drop (realtime)'` | Drop keeps only the newest image (live preview). Block queues every image and back-pressures the emitter. |
| `max_queue_size` | dispatch | `1` | How many pending images to hold. Drop mode needs 1 to guarantee newest-wins. |

## Notes

Runs its flow once per image from the emitter it is wired to.

Connect `Listen` to the image-callback inlet of an emitter (a stream receiver, a camera).
The emitter sends `{"image": ImageValue, "timestamp": float, "frame_number": int}`.

Outputs:
    frame_ready: Control flow when an image arrives
    image: The image
    timestamp / frame_number: Seconds since the emitter started, and the count
