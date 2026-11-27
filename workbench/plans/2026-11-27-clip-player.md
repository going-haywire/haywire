# Clip Player (haybale-audio) — plan

Decided by the owner in the speech TTS plan (decision 5 a): a node in haybale-audio that plays
an `AUDIO` clip (one `AudioBlock` holding a whole utterance, e.g. Speak's 24 kHz mono output) as
an audio flow, reusing File Player's emitter.

## How audio emitters work today

An emitter (File Player, Device In, Audio Clock) has **no `AUDIO_EXEC` outlet**. It holds a
`POOLED[AUDIO_CALLBACK]` inlet; each Audio Event wired to it receives every block as a callback
and starts the `AUDIO_EXEC` flow from its `Block Ready`. The shared pieces live in
`haybale_audio/emitter.py`: `BlockPump` (paced daemon thread), `deliver_to_subscribers`,
`set_status`. File Player is ~40 lines of glue around them plus `FileBlockReader`.

Demo wiring: Speak `done` → Clip Player `start`, Speak `clip` → Clip Player `clip`,
Audio Event `Listen` → Clip Player `Subscribers`, Audio Event `Block Ready` → Device Out `Write`.

## Design

- `ClipPlayerNode`, label "Clip Player", menu `audio/source`, `NodeType.CONTROL`.
- Ports, mirroring File Player: `start` / `stop` (EXEC in), `clip` (AUDIO in),
  `callbacks` (`POOLED[AUDIO_CALLBACK]` in, "Subscribers"), `status` (label config),
  `started` / `stopped` (EXEC out).
- Settings bag: `block_size` (256, 16–8192) and `loop` (False), as File Player's.
- Reuse: `BlockPump`, `deliver_to_subscribers`, `set_status` from `emitter.py`; nothing copied
  from File Player. A small `ClipBlockReader` (slices the clip's array into read-only views of
  `block_size` frames, loops when asked) is the only new piece; where it lives is decision 4.
- Rate: blocks keep the clip's sample rate and channels (File Player's rule). Device Out opens at
  the first block's rate and converts to the device; Resample is there for a flow that needs
  another rate.
- Errors: no clip on `start` raises `ValueError("no clip given")`; no subscriber shows
  "No subscriber" and returns `None` (File Player's behaviour). The pump holds the clip it
  started with: a new value on the inlet changes nothing until the next `start`.

## Tests (tests/audio/test_source_nodes.py, by File Player's test)

- plays a 960-frame 2 ch clip as blocks `[256, 256, 256, 192]`, status ends "Finished";
- keeps the clip's rate (24 kHz mono block in, 24 kHz mono blocks out);
- no subscriber → `None`, "No subscriber"; no clip → `ValueError`;
- start while playing behaves as decision 2 says; stop → "Stopped", `stopped`;
- loop emits more blocks than the clip holds;
- `test_audio_exec_pins.py`: add Clip Player to the emitters whose start/stop stay plain EXEC.

Then `uv run haywire docs barn/haybale-audio`, `pytest tests/audio`, `mypy`, `ruff`.
No version bump.

## Decided (owner, 2026-11-27: "go")

1 a: Clip Player, File Player's ports with `clip` for `path`, no Done outlet ·
2 a: a Start while playing switches the running pump to the new clip, without a gap ·
3 a: blocks keep the clip's rate ·
4 a: the reader is private to the node module ·
5 a: Block Size and Loop ·
6 b: a Keep Running setting, off by default, sends silence after the clip until Stop, so an
Audio Mixer counts no stall at a clip's end (one stall per clip otherwise). An end-of-stream
signal the mixer understands would be the general fix, a change of its own.

## Round 2: clip type and clip toolkit (owner, 2026-11-27)

Decided: a new type `AUDIO_CLIP` (same `AudioBlock` value, own colour) for clip ports · clip and
stream never connect directly; nodes are the bridges · Collect Clip and Speech Segmenter move to
haybale-audio, as Collect Clip and Clip Segmenter, keeping the input's rate and channels (the
16 kHz mono conversion moves into Transcribe) · Clip Segmenter gets a `clip` outlet and a
`Segment` control outlet, like Collect Clip · two nodes on one buffer: Collect Clip cuts on Stop,
Clip Segmenter at pauses plus a `Cut` inlet · Clip Queue: `Push`, `Pop`, `Clear` in; `clip`,
`count` out; Order (oldest first / newest first / newest only), Max Clips (drop oldest), Auto ·
Clip Player gets a `Finished` signal · everything in #276 (haybale-speech drops its copies and
moves to `AUDIO_CLIP` in its own PR).

Found: a node's own thread starts a flow only by `emit_callback` to an event node (Audio Event,
Tick Event); an EXEC outlet fires only inside the flow that ran the node. So Clip Player's
`Finished` (fired from its pump thread) and Clip Queue's Auto (a clip handed on in a flow of its
own) need a callback route. Open: decisions 7 and 8 of round 2.

Decided: 7 a, Clip Player's `On Finish` is a `POOLED[CALLBACK]` inlet for Tick Events · 8 a, a new
`CLIP_CALLBACK` type and a Clip Event node, the clip in the payload.

## Round 3: parallel consumers of one clip stream

Today (core, read 2026-11-27):

- Each event node listens on a callback named by its own node id; an emitter sends to every
  subscriber, so two Clip Events would each get **every** clip (broadcast, not shared work).
- Each flow has its own `FlowQueue` (`BLOCK` waits up to 5 s for room, then drops; `DROP` keeps
  the newest). An emitter in an audio flow that hits a full `BLOCK` queue holds the audio flow.
- Flows that share a control node form one execution group and run on one thread (ADR 0064). Two
  worker flows that both end on the same Clip Queue (`Pop`) share a group, so they never run in
  parallel.
- `FlowQueue._run_one` knows when a frame ends; nothing outside it is told.

Open: decisions 9 and 10 of round 3.

Owner, round 3 so far: pooled delivery is general (any callback), chosen per **event node**
(Delivery: every / pooled), the emitter unaware of distribution; core forms the pool from the
pooled listeners of one emit; the **emitter** sets the pool's backlog (size, full rule). Its own
core PR first (ADR, issue). Clip Queue stays, for flow-controlled playback (Pop driven by Clip
Player's On Finish); its Auto setting goes, the pooled backlog covers that case.
Open: 13, 14, 15 (revised), 16, 17.

Decided: 13 a, 14 a, 15 a (revised), 16 a, 17 a.

### Measured: two faster-whisper runs in parallel (2026-11-27)

i7-7700K (4 cores, 8 threads), faster-whisper 1.2.1, `small`, int8, a 15.4 s clip; a pure-Python
probe thread counts loop turns (16 M/s idle) to show whether the GIL is held.

| cpu_threads | two clips in turn | 2 threads, 1 model | 1 model, num_workers=2 | 2 models |
|---|---|---|---|---|
| 4 | 3.45 s | 4.39 s | 3.45 s | 3.44 s |
| 2 | 4.85 s | 4.84 s | 3.82 s | 3.93 s |

- The GIL is released during inference: the probe keeps 15.5 M/s at 2 threads each; it falls
  to 10 M/s only when 8 compute threads hold every core.
- Parallel runs gain only when one run leaves cores idle (1.27x at 2 threads each); at 4 the
  cores are already full. The limit is cores, not the GIL.
- One model with `num_workers=2` is as fast as two models, at one model's memory. A model
  without it serialises concurrent calls (4.39 s, slower than in turn).
- haybale-speech's `transcribe` holds `model.lock`, which serialises every call: pooled
  Transcribe flows need it gone and a Workers setting on Load STT Model (`num_workers`).

## Built (after #283, ADR 0097)

- Types `AUDIO_CLIP`, `CLIP_CALLBACK`; Clip Event (Dispatch + Delivery bags, `Clip Ready` plain EXEC).
- Collect Clip (`clip` is `AUDIO_CLIP`) and Clip Segmenter (Subscribers → Clip Event, the input
  format kept, `Cut`, Backlog bag) in `audio/clip`; `ClipBuffer` and `Segmenter` in `dsp/`.
- Clip Queue: Push / Pop / Clear; Pushed / Popped / Empty / Cleared; `clip_out`, `count`;
  Order, Max Clips.
- Clip Player: `clip` is `AUDIO_CLIP`, Backlog bag, `On Finish` (`POOLED[CALLBACK]`), run when a
  clip plays to its end (Keep Running: when its silence begins), never on Stop.

D10: two pooled Transcribe flows run at once only when each has its own Transcribe node (a shared
DATA node runs under its exec_lock) and they share no control node (one group, one thread). And
haybale-speech's `model.lock` serialises runs until it goes and Load STT Model passes `num_workers`.

## Round 4 (owner, 2026-11-27, after live check round 2 passed)

1 a: Clip Segmenter's settings move into a Segmenting bag (promotable to config ports), with a
new Post-roll (default 100 ms, at most the Hang-over; it does not count towards Min Seconds) ·
2 a: a block stream is never pooled: Delivery leaves Audio Event, the Backlog bag leaves Device In,
File Player, Clip Player, Audio Clock, Resample and Reblock; ADR 0097 D11 · 3 a: in #276. A graph
saved with those settings loads without them (`test_saved_graphs`, fixture
`pooled_audio_settings.haywire`).

Owner, via the lead: Clip Queue keeps Pushed, Popped, Empty and Cleared (3 a); Cut stays without an
outlet (4 a); no post-roll listen (6 a); a code review of #276 before the merge.
