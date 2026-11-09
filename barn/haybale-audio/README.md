# Audio

<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `uv run --frozen haywire share --bump patch`.*
<!-- marketstall:share-url:end -->

Audio blocks, events and routing shared by speech and streaming libraries

## Nodes
### Audio
- **Audio Clock** — Emits a silent audio block at a steady rate
- **Audio Event** — Triggered for each audio block a connected audio emitter delivers
- **Audio Mixer** — Sums several audio sources into one block per clock tick
- **Channel Merge** — Stacks audio blocks into one block with all their channels
- **Channel Select** — Picks, reorders or repeats the channels of an audio block
- **Channel Split** — Gives each channel of an audio block its own output
- **Device Out** — Plays audio blocks on a sound device
- **File Player** — Plays an audio file as audio blocks, in real time
- **Mix to Mono** — Averages all channels of an audio block into one
- **Reblock** — Re-cuts audio blocks to a fixed size and delivers them to Audio Event nodes
- **Recorder** — Writes audio blocks to a file
- **Resample** — Converts audio blocks to another sample rate and delivers them to Audio Event nodes

## Types
- **Audio** — A block of audio samples. Never saved with the graph.
- **Callback Audio** — Subscription for emitters that deliver audio blocks
