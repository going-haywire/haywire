# haybale-audio — component index (v0.3.4)

## node
- `haybale-audio:node:AudioClockNode` — Audio Clock — Emits a silent audio block at a steady rate  _tags: audio, clock, tick, timer, master, pace, emit_
- `haybale-audio:node:AudioEventNode` — Audio Event — Triggered for each audio block a connected audio emitter delivers  _tags: audio, block, event, callback, receive, stream, microphone_
- `haybale-audio:node:ChannelMergeNode` — Channel Merge — Stacks audio blocks into one block with all their channels  _tags: audio, channel, merge, combine, stack, join, multichannel_
- `haybale-audio:node:ChannelSelectNode` — Channel Select — Picks, reorders or repeats the channels of an audio block  _tags: audio, channel, select, route, map, left, right, stereo, mono_
- `haybale-audio:node:ChannelSplitNode` — Channel Split — Gives each channel of an audio block its own output  _tags: audio, channel, split, separate, left, right, mono, multichannel_
- `haybale-audio:node:FilePlayerNode` — File Player — Plays an audio file as audio blocks, in real time  _tags: audio, file, play, wav, flac, ogg, read, emit_
- `haybale-audio:node:MixToMonoNode` — Mix to Mono — Averages all channels of an audio block into one  _tags: audio, mono, mix, downmix, average, stereo_
- `haybale-audio:node:ReblockNode` — Reblock — Re-cuts audio blocks to a fixed size and delivers them to Audio Event nodes  _tags: audio, reblock, block, size, buffer, chunk_
- `haybale-audio:node:RecorderNode` — Recorder — Writes audio blocks to a file  _tags: audio, record, write, save, file, wav, flac, ogg_
- `haybale-audio:node:ResampleNode` — Resample — Converts audio blocks to another sample rate and delivers them to Audio Event nodes  _tags: audio, resample, sample rate, convert, 44100, 48000, 16000_

## type
- `haybale-audio:type:AUDIO` — Audio — A block of audio samples. Never saved with the graph.
- `haybale-audio:type:CALLBACK_AUDIO` — Callback Audio — Subscription for emitters that deliver audio blocks
