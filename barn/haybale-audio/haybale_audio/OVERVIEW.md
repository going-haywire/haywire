# Audio

Audio blocks, events and routing shared by speech and streaming libraries

## Nodes
### Audio
- **Audio Clock** — Emits a silent audio block at a steady rate
- **Audio Event** — Triggered for each audio block a connected audio emitter delivers
- **File Player** — Plays an audio file as audio blocks, in real time
- **Recorder** — Writes audio blocks to a file

## Types
- **Audio** — A block of audio samples. Never saved with the graph.
- **Callback Audio** — Subscription for emitters that deliver audio blocks
