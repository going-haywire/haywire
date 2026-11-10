# Resample

`haybale-audio:node:ResampleNode` · kind: node

Converts audio blocks to another sample rate and delivers them to Audio Event nodes

## Ports

| id | direction | type | description |
|---|---|---|---|
| `write` | inlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |
| `audio` | inlet | `haybale-audio:type:AUDIO` | Block to convert |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `next` | outlet | `haybale-audio:type:EXEC_AUDIO` | Signal for sequencing the nodes of an audio flow |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `target_rate` | resample | `48000` | Samples per second of the delivered blocks. |
| `quality` | resample | `'Fast'` | Fast costs about 0.25% of real time for stereo and is clean for speech and music. |

## Notes

Converts each block that reaches `Write` to `Sample Rate` and delivers it to every Audio Event
listening. The filter keeps its state between blocks, so the joins are seamless. The first block
after a start or a format change can come out shorter or not at all while the filter fills.

Block sizes change with the rate (a 441-sample block at 44.1 kHz gives about 480 at 48 kHz); put a
Reblock after it where a fixed size is needed.

Use cases:

- Feed a model that wants one rate. Speech-to-text models usually take 16 kHz mono: resample
  to 16000, then a Mix to Mono, then a Reblock to the model's block size.
- Record or send at a set rate. A Recorder writes, and an OMT send transmits, the rate of the
  blocks it gets. Resample in front when the file or the receiver expects another one, for
  example a 44.1 kHz MP3 played into a 48 kHz show.
- Match sources before a node that does not convert. A Channel Merge needs blocks of one
  sample rate; resample the odd one out first.

```text
File Player → Audio Event → Resample (16000) → Audio Event → Mix to Mono → …
```

An Audio Mixer and a Device Out convert to their own rate themselves, and they also follow a source
whose clock runs slightly fast or slow, so neither needs a Resample in front. Resample uses a
fixed ratio and does not do that.

Inputs:
    write: Convert the block on `audio`
    audio: The block to convert
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    next: Control flow after the block is taken in
