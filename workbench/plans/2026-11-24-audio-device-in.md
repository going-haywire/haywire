# Device In node (haybale-audio)

Date: 2026-11-24 · Branch: `feat/audio-device-in` · Issue: [#232](https://github.com/going-haywire/haywire/issues/232), part 1 (and the PR's place for part 3's soak results).

| Status | implemented: A1 and B1 chosen by the user on 2026-11-24; soak check waits for the user |
|---|---|

## Shape

A new `DeviceInNode` in `haybale_audio/nodes/device_in.py`, menu `audio/source`, `NodeType.CONTROL`.
Ports exactly as File Player / Audio Clock: `start`, `stop` (EXEC), `callbacks`
(`POOLED[AUDIO_CALLBACK]`), `status` (LabelWidget config) → `started`, `stopped`. No subscriber →
`"No subscriber"`, no stream opened (as both). `on_shutdown` and `on_teardown` call `hb_stop`, which
uses the `getattr(self, "hb_…", None)` guard of every audio node.

Settings bag `DeviceInSettings`, "Applies on the next start", all `Promotable.CONFIG`:

| Setting | Type | Default | Follows |
|---|---|---|---|
| device | CHOICES | `"System default"` + `input_device_names()` | Device Out's `device` |
| channels | see decision **B** | | |
| sample_rate | see decision **B** | the device's | |
| block_size | INT 16–8192 | 256 | File Player / Audio Clock `block_size` |

## 1. Pacing: the device clock, a cheap callback, a delivery thread

- `sd.InputStream(callback=…, blocksize=block_size, dtype="float32", latency="low")`.
- **The callback** does only: `indata.T.copy()` (planar, owned), `queue.put_nowait(...)`, and
  `lost += 1` on `queue.Full`; it also counts `status.input_overflow` (data PortAudio lost before
  us). No AudioBlock construction, no lock, no graph call. Cost: one copy of 256×ch floats plus a
  non-blocking put, well under spike S7's 30–75 µs.
- **The delivery thread** takes a block from the queue, wraps it in `AudioBlock` and calls
  `deliver_to_subscribers` (unchanged). With Audio Event in BLOCK mode, `emit_callback`
  back-pressures *this* thread, never the callback: the only place a block is lost is the
  bounded queue, where it is counted.
- **Queue depth:** fixed at about 0.5 s of blocks (`max(8, ceil(0.5 / block duration))`, 94 blocks
  at 256/48 kHz), the same budget as Audio Event's default `max_queue_size` of 100 (≈0.5 s). S1 says
  a deep BLOCK queue, never DROP.

The thread mechanism is decision **A**.

## 2. Backend seam: the mirror of `OutputBackend`

In `io/device.py`, next to the output side, the same names with `Input`:

| Output (exists) | Input (new) |
|---|---|
| `OutputStream` Protocol: start/stop/close, `buffer_frames`, write | `InputStream` Protocol: start/stop/close, `latency` (s), `block_frames` |
| `OutputBackend` Protocol: `device_info(device) -> (rate, channels)`, `open(...)` | `InputBackend` Protocol: `device_info(device) -> (rate, max input channels)`, `open(device, rate, channels, block_size, callback)` |
| `SoundDeviceBackend` (lazy `import sounddevice`) | `SoundDeviceInputBackend` (same lazy import) |
| `_PortAudioOutput` | `_PortAudioInput` |
| `output_device_names()` | `input_device_names()` |
| `_index(device)` (output only) | `_index(device, kind)`: `kind` = `"output"` / `"input"`, the channel key follows it |
| `DeviceOutput` (owns backend, stream, thread, counters, `error`) | `DeviceInput` (owns backend, stream, queue, counters, `error`) |

Tests pass a `FakeInputBackend` whose stream keeps the callback; the test calls it as the device
would (`stream.feed(frames)`), as `test_device_out.py`'s `FakeBackend` does for output. The node
test swaps `DeviceInput` by `monkeypatch.setattr` on the module, exactly as
`test_node_plays_blocks_and_stops`. CI needs no sound device.

## 3. Clock drift: the existing `PullBuffer`, no new mechanism

Device In does nothing about drift: it delivers at the input device's clock. When it meets
another clock, the consumer's `PullBuffer` (Device Out, Audio Mixer) already resamples with its
`DriftController`. I verify that this absorbs input→output drift with one new unit test at the
`DeviceOutput` level (`threaded=False`, `render` pulled at the output clock, blocks written at
the input clock offset by ±100 and +500 ppm, the S9 cases), in simulated time like
`TestDriftController.test_holds_depth_against_a_clock_offset`: no restart after priming, depth
bounded, 20 simulated minutes. `max_trim` is 1000 ppm, so 500 ppm is inside the controller's
range. If the test shows it does not hold, I report *Blocked* rather than add a second mechanism.

## 4. Overflow counting

Two counters on `DeviceInput`, shown like Device Out's `stalls … late … dropped`:

- `lost`: blocks dropped because the delivery queue was full (the flow ran behind for > 0.5 s).
- `overflows`: callbacks PortAudio flagged `input_overflow` (the program held the interpreter so
  long that the device's own buffer overflowed).

## 5. Status label: the real block size and latency

Updated at most every `STATUS_INTERVAL` (0.5 s, Device Out's constant, imported) from the delivery
thread (File Player's `on_end` sets the status from its pump thread already):

`Listening 2 ch at 48000 Hz, blocks 256, latency 5.3 ms, lost 0, overflow 0`

- `blocks` is the frame count of the last callback, not the setting; when it differs:
  `blocks 512 (asked 256)`. PortAudio with a fixed `blocksize` normally keeps it, but S7 saw Core
  Audio impose 512, so the label shows what really arrives. Blocks are delivered as they come:
  a node that needs another size uses Reblock.
- `latency` is `stream.latency` (PortAudio's input latency), in ms.
- On stop: `Stopped`; on a delivery-thread error: `Error: …` (File Player's `on_end`).

## Decisions

**A. The delivery thread.**

- **A1 (recommended).** Reuse `BlockPump` with a new `paced: bool = True` flag; `paced=False` skips
  the sleep to the deadline and delivers as soon as `produce` returns. `produce` is
  `DeviceInput.read`, which blocks on the queue and returns `None` once the input is closed, which
  ends the pump as a file's end does. One delivery-thread mechanism for every audio emitter
  (numbering, `on_end`, stop/join), and `BlockPump`'s tests cover it.
- **A2.** `DeviceInput` runs its own delivery thread, like `DeviceOutput._feed`. Self-contained, but
  a second copy of the start/stop/number/on_end logic `BlockPump` already has.

**B. Channels and sample rate settings.** The design principles forbid in-band sentinels, so
"0 = the device's" is out.

- **B1 (recommended).** Both `CHOICES`, as the device setting does: sample rate
  `"Device default"`, 44100, 48000, 96000; channels `"All device channels"`, 1, 2. The default for
  both is the device's, as the issue asks. A count above the device's maximum is clamped; the label
  shows the real count.
- **B2.** `INT` settings, channels default 1, sample rate default 48000; the device's own values only
  through the label. Simpler, but not "the device's" by default.

## Soak check (part 3)

The PR body gets a *Soak check* section with the graph (no Audio Clock:
`Begin Play → Device In.start`, `Device In → Audio Event → Device Out`, saved as a fixture beside
`tests/audio/fixtures/audio_flow.haywire`) and the steps: 10 minutes with the studio and graph
viewer open, on Python 3.12 and 3.13, recording Device In's `lost`/`overflow` and Device Out's
`stalls`/`late`/`dropped`. Results are filled in only from the user's run.

## Findings while building

- On Linux with PipeWire, the ALSA `default`, `pipewire` and `sysdefault` inputs report 128 input
  channels, so *All device channels* records 128 channels there (it works; Device Out fits them to
  its own). The JACK device (`Built-in Audio Analog Stereo`) reports its real 4.
- On the development machine the ALSA `default` input does not open and `sysdefault` overflows at
  1–2 channels, the same with a bare `sounddevice` stream and an empty callback: the machine's ALSA
  setup, not Device In. The JACK device ran clean: 564 of ~562 expected blocks in 3 s.
- Studio run, 50 s, Device In (JACK, 4 ch 48 kHz) → Audio Event → Device Out (HDMI, 44.1 kHz):
  lost 0, overflow 0; Device Out stalls 7, all in the first seconds, late 0, dropped 0; no ledger
  errors; stop left no capture stream.
