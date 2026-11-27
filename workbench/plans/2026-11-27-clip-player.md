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
