# Audio Clock

`haybale-audio:node:AudioClockNode` · kind: node

Emits a silent audio block at a steady rate

## Ports

| id | direction | type | description |
|---|---|---|---|
| `start` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stop` | inlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `callbacks` | inlet | `haybale-core:type:PooledType` | Connect to an Audio Event node. |
| `status` | config | `haywire-core:type:STRING` | Text data |
| `started` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |
| `stopped` | outlet | `haywire-core:type:EXEC` | Signal for controlling execution flow between nodes |

## Settings

| name | bag | default | description |
|---|---|---|---|
| `sample_rate` | clock | `48000` | Samples per second of the blocks. |
| `block_size` | clock | `256` | Samples per block. 256 at 48 kHz is a block every 5.3 ms. |

## Notes

Emits one silent single-channel block per period to every Audio Event listening. The blocks
carry no sound: the clock is a metronome, and the Audio Event it feeds runs its flow once per beat.

`Sample Rate` and `Block Size` set the period. 256 samples at 48 kHz is a block every 5.3 ms;
smaller blocks lower the delay and raise the number of events per second.

Use cases:

- Pace a mixer. Wire the clock to an Audio Event and that event to an Audio Mixer, with
  `Block Ready` going to `Tick` and `Audio` to `Clock`. The mixer then makes one block per beat,
  in the clock's sample rate and block size, whatever the rates and block sizes of its inputs.
- Keep an output fed. The mixer makes a block on every beat, silent while no input plays, so a
  Device Out behind it gets a steady stream and never waits for a source to start.
- Give a flow a steady beat. A flow that makes its own sound, or a test signal, can hang on
  the clock's Audio Event.

A single source straight into a Device Out or a Recorder needs no clock: the File Player and
every other source paces itself.

Inputs:
    start / stop: Begin or end the ticks
    callbacks: Pooled CALLBACK_AUDIO subscriptions from Audio Event nodes

Outputs:
    started / stopped: Control flow after the matching input
