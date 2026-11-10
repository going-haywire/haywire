# Module: haybale-audio

> Audio blocks, events and routing for Haywire: the `AudioBlock` value, audio emitters and `EXEC_AUDIO` events, DSP primitives (reblock, resample, mix, channels), device and file I/O, and the nodes that tie them into a graph.

**Path:** `barn/haybale-audio/haybale_audio/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** 58d1e97e1f959095d744a7671e7014244f75b62b
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-audio` is the audio foundation that speech and streaming libraries build on. It defines what an audio block is (`value/audio_block.py`), how an audio emitter delivers blocks to an event node (`emitter.py`, `nodes/audio_event.py`), and the dual-flow exec variant that only audio flows accept (`EXEC_AUDIO`, `types/exec_audio.py`). It also supplies DSP helpers (reblock, resample, channel and mix operations), file and device I/O, and the nodes (clock, mixer, recorder, file player, device out) built on those. Removing it breaks every audio node in the barn.

## 2. Folder Architecture

```
haybale_audio/
├── __init__.py           ← `Library` subclass
├── emitter.py            ← audio emitter: delivers blocks to connected audio events
├── value/
│   └── audio_block.py    ← AudioBlock value type
├── types/
│   ├── audio.py          ← audio port/type
│   ├── callback.py       ← callback type
│   └── exec_audio.py     ← EXEC_AUDIO: an EXEC that only audio flows accept
├── dsp/
│   ├── buffer.py, fifo.py  ← buffering primitives
│   ├── reblock.py          ← change block size
│   ├── resample.py         ← sample-rate conversion
│   ├── channels.py, mix.py ← channel layout and mixing
├── io/
│   ├── device.py         ← audio device I/O
│   └── files.py          ← audio file I/O
├── nodes/
│   ├── audio_clock.py, audio_event.py, audio_mixer.py
│   ├── channel_merge.py, channel_select.py, channel_split.py, to_mono.py
│   ├── reblock.py, resample.py
│   ├── file_player.py, recorder.py, device_out.py
└── haybale.toml          ← library manifest
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` and `register_components()`.
- `value/audio_block.py` — the block every audio node passes.
- `types/exec_audio.py` — the EXEC variant; the pin rules for audio flows depend on it.

### On-demand

- `emitter.py` and `nodes/audio_event.py` — event delivery per block. Read with the execution cross-cut.
- `dsp/` — when changing block size, rate or channel handling. Keep DSP free of graph logic.
- `io/` — device and file I/O. Keep device handles out of node code where possible.
- `nodes/` — one file per node kind.

## 4. Rules & Boundaries

- Audio flows use `EXEC_AUDIO`. Do not wire a plain EXEC into an audio flow.
- DSP modules (`dsp/`) are pure transforms. They must not import node or graph classes.
- Register components through `Library.register_components()`.
- Documentation for each node lives in the library's `README.md` and `OVERVIEW.md`. Keep them in sync with the node code.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Audio block | `value/audio_block.py` | Block value shared by all audio nodes |
| Audio exec | `types/exec_audio.py` | EXEC variant for audio flows |
| Block delivery | `emitter.py` | Emitter that drives audio events |
| Library manifest | `haybale.toml` | Metadata, read from disk at runtime |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — node base, types, registries, execution model.
- [haybale-core](haybale-core.md) — shared EXEC, GROUP and primitive types.

### Depended on by

- Speech and streaming libraries (by design; the audio README names them). ⚠️ TODO: confirm the exact consumers with a grep for `haybale_audio` imports.
- [tests](tests.md) — `tests/audio/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | `haywire.libraries` entry point |
| Audio block | `value/audio_block.py` | Block value type |
| Audio emitter | `emitter.py` | Block delivery |
