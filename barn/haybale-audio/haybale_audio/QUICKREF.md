# haybale-audio — component index (v0.3.4)

## node
- `haybale-audio:node:AudioClockNode` — Audio Clock — Emits a silent audio block at a steady rate  _tags: audio, clock, tick, timer, master, pace, emit_
- `haybale-audio:node:AudioEventNode` — Audio Event — Triggered for each audio block a connected audio emitter delivers  _tags: audio, block, event, callback, receive, stream, microphone_
- `haybale-audio:node:FilePlayerNode` — File Player — Plays an audio file as audio blocks, in real time  _tags: audio, file, play, wav, flac, ogg, read, emit_
- `haybale-audio:node:RecorderNode` — Recorder — Writes audio blocks to a file  _tags: audio, record, write, save, file, wav, flac, ogg_

## type
- `haybale-audio:type:AUDIO` — Audio — A block of audio samples. Never saved with the graph.
- `haybale-audio:type:CALLBACK_AUDIO` — Callback Audio — Subscription for emitters that deliver audio blocks
