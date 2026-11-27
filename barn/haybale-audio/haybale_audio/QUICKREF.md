# haybale-audio — component index (v0.6.6)

## node
- `haybale-audio:node:AudioClockNode` — Audio Clock — Emits a silent audio block at a steady rate  _tags: audio, clock, tick, timer, master, pace, emit_
- `haybale-audio:node:AudioEventNode` — Audio Event — Triggered for each audio block a connected audio emitter delivers  _tags: audio, block, event, callback, receive, stream, microphone_
- `haybale-audio:node:AudioMixerNode` — Audio Mixer — Sums several audio sources into one block per clock tick  _tags: audio, mixer, mix, sum, gain, mute, combine, bus_
- `haybale-audio:node:ClipEventNode` — Clip Event — Triggered for each audio clip a connected clip emitter delivers  _tags: audio, clip, event, callback, receive, speech, segment, pool_
- `haybale-audio:node:ClipPlayerNode` — Clip Player — Plays an audio clip as audio blocks, in real time  _tags: audio, clip, play, speech, voice, emit_
- `haybale-audio:node:ClipQueueNode` — Clip Queue — Holds audio clips until a flow takes them, one at a time  _tags: audio, clip, queue, playlist, buffer, speech, fifo_
- `haybale-audio:node:ClipSegmenterNode` — Clip Segmenter — Cuts a live audio flow into clips at the pauses, such as one clip per sentence  _tags: audio, clip, speech, vad, voice, segment, split, pause, silence, live, microphone_
- `haybale-audio:node:CollectClipNode` — Collect Clip — Gathers the audio blocks of a flow into one clip, sent on Stop  _tags: audio, clip, collect, gather, buffer, speech, record, segment_
- `haybale-audio:node:DeviceInNode` — Device In — Records a sound device's input as audio blocks  _tags: audio, record, microphone, mic, input, device, sound, line in, emit_
- `haybale-audio:node:DeviceOutNode` — Device Out — Plays audio blocks on a sound device  _tags: audio, play, speaker, output, device, sound_
- `haybale-audio:node:FilePlayerNode` — File Player — Plays an audio file as audio blocks, in real time  _tags: audio, file, play, wav, flac, ogg, read, emit_
- `haybale-audio:node:MergeChannelsNode` — Merge Channels — Stacks audio blocks into one block with all their channels  _tags: audio, channel, merge, combine, stack, join, multichannel_
- `haybale-audio:node:MixToMonoNode` — Mix to Mono — Averages all channels of an audio block into one  _tags: audio, mono, mix, downmix, average, stereo_
- `haybale-audio:node:ReblockNode` — Reblock — Re-cuts audio blocks to a fixed size and delivers them to Audio Event nodes  _tags: audio, reblock, block, size, buffer, chunk_
- `haybale-audio:node:RecorderNode` — Recorder — Writes audio blocks to a file  _tags: audio, record, write, save, file, wav, flac, ogg_
- `haybale-audio:node:ResampleNode` — Resample — Converts audio blocks to another sample rate and delivers them to Audio Event nodes  _tags: audio, resample, sample rate, convert, 44100, 48000, 16000_
- `haybale-audio:node:SelectChannelNode` — Select Channel — Picks, reorders or repeats the channels of an audio block  _tags: audio, channel, select, route, map, left, right, stereo, mono_
- `haybale-audio:node:SplitChannelsNode` — Split Channels — Gives each channel of an audio block its own output  _tags: audio, channel, split, separate, left, right, mono, multichannel_

## type
- `haybale-audio:type:AUDIO` — Audio — A block of audio samples. Never saved with the graph.
- `haybale-audio:type:AUDIO_CALLBACK` — Audio Callback — Subscription for emitters that deliver audio blocks
- `haybale-audio:type:AUDIO_CLIP` — Audio Clip — A whole audio clip, such as one utterance, as one block. Never saved with the graph.
- `haybale-audio:type:AUDIO_EXEC` — Audio Execution Signal — Signal for sequencing the nodes of an audio flow
- `haybale-audio:type:CLIP_CALLBACK` — Clip Callback — Subscription for emitters that deliver whole audio clips
