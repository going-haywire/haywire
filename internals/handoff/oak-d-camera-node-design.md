# Handoff: OAK-D 3D Camera Support for haybale-visiongraph

## Goal

Expand the **haybale-visiongraph** library with nodes + datatypes to support the
**Luxonis OAK-D** depth camera (RGB + depth + infrared), wrapping the existing
`visiongraph` device abstraction.

This document captures an **in-progress design interview** (via the `inquisition`
skill). No code has been written yet. Several decisions are settled; a few branches
remain open. Resume the interview from **Q4a / Q5 / Q6** (see Open Questions).

## Source material (read these)

- **visiongraph source** (local, NOT in this repo):
  `/Volumes/Ddrive/03_personal/visiongraph/`
  - Device wrapper to wrap: `visiongraph/input/OakDInput.py`
  - Base classes (full param surface lives here):
    `visiongraph/input/DepthAIBaseInput.py`, `BaseDepthCamera.py`,
    `BaseDepthInput.py`, `BaseInput.py`
  - Examples: `visiongraph/examples/` (e.g. `DepthCameraExample.py`)
- **Existing library** (symlink — gitignored local-only target is
  `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`):
  `barn/haybale-visiongraph/haybale_visiongraph/`
  - `types/frame_type.py` — the `FRAME` datatype (currently assumes 3-channel BGR/RGB)
  - `nodes/start_web_cam_stream_node.py` — **the pattern to mirror** (emit node, own
    capture thread, `PooledType[CALLBACK]` inlet, `context.emit_callback`)
  - `nodes/webcam_frame_event_node.py` — the matching EVENT node
  - `nodes/frame_info_display_node.py`, `widgets/opencv_viewer_widget.py`
  - `__init__.py` — `@library` decorator + `register_components`
- **Haywire docs**: `docs/components/settings/setting-canon.md`,
  `docs/architecture/settings/settings-arch.md`,
  `docs/components/datatypes/datatype-canon.md`, `docs/reference/glossary.md`

## Decisions settled so far

1. **Integration boundary (Q1 = A):** Wrap visiongraph's `OakDInput` rather than
   talking to `depthai` (`dai`) directly. **Mechanism caveat:** visiongraph devices
   configure via `configure(args: argparse.Namespace)`, which Haywire has no analog
   for. So the node must set `OakDInput`'s **public attributes directly** before
   `setup()` (e.g. `.enable_depth`, `.color_sensor_resolution`, `.frame_alignment`),
   not via `configure()`.

2. **Node shape:** Follow the **emit-node + event-node** pattern from the webcam
   nodes (NOT a single multi-outlet node).
   - **Emit node** (`Start OAK-D Stream`): owns the `OakDInput`, runs its own capture
     thread, emits callbacks. Pipeline shape ~ `StartWebcamStreamNode`.
   - **Event node** (`OAK-D Frame Event`): subscribes via CALLBACK edge, exposes
     `FRAME` data outlets, dynamically revealing outlets per the streams it consumes.

3. **One bundled callback message (user's key correction):** The emit node sends
   **ONE** callback message per captured frame — a **bundle** carrying whichever
   streams are required, e.g.
   `{"rgb": ndarray, "depth": ndarray, "ir": ndarray, "frame_number": N, "timestamp": t}`,
   with keys present only for streams someone needs. NOT three separate callback
   channels. Each event node picks the stream(s) it wants out of the bundle and
   passes them on.

4. **Stream gating (Q3 = B, refined by #3):** Single `PooledType[CALLBACK]` channel
   (matches webcam pattern, supports multiple subscribers). The set of enabled device
   streams is the **union of stream-requirements across all connected event nodes**.
   If nobody asks for `ir`, the device never enables IR and the bundle omits the key.
   Rationale: enabling the OAK stereo-depth pipeline + IR laser is the expensive part;
   don't pay for streams nobody consumes.

5. **Three logical streams + their channel formats (user's intent, encoding TBD):**
   - `rgb` — 3-channel RGB
   - `depth` — encoding **undecided** (user floated HSV; see Open Q4b). Note the
     hardware distinction: `OakDInput.depth_map` (colorized JET, **display only**) vs
     `OakDInput.depth_buffer` (uint16 **millimeters**, the real measurement data).
   - `ir` — 1-channel grayscale

## Key technical findings (don't re-derive)

- **OAK params split by run-time mutability** — this is a *correctness* boundary the
  hardware enforces, sharper than config-vs-settings:
  - **Category 1 — pipeline-construction params** (read once at
    `setup()`/`pre_start_setup()`, **immutable while running**; changing requires
    device rebuild): stream enables (`enable_color/_depth`, `use_infrared`,
    `use_depth_as_input`, `enable_color_still`), `color_sensor_resolution`,
    `color_board_socket`, `color_fps`, `color_isp_scale`, `interleaved`,
    `queue_max_size`, `ir_sensor_resolution`, `select_ir_camera`, `depth_preset_mode`,
    `depth_median_filter`, `depth_left_right_check`, `depth_subpixel`,
    `depth_extended_disparity`, `frame_alignment`. (~19 params)
  - **Category 2 — live camera-control params** (every setter guarded by
    `if not self.is_running: return`, sends a `dai.CameraControl` to the running
    device; **color-sensor only**, except the two IR knobs): `enable_auto_exposure`,
    `exposure` (µs), `iso`, `auto_exposure_compensation`, `enable_auto_white_balance`,
    `white_balance` (K), `auto_white_balance_mode`, `auto_focus`, `focus_distance`,
    `brightness`, `contrast`, `saturation`, `sharpness`, `luma_denoise`,
    `chroma_denoise`, `anti_banding_mode`, `effect_mode`,
    `ir_laser_dot_projector_intensity`, `ir_flood_light_intensity`. (~18 params)
  - **Category 3 — read-only/query** (candidate data outlets, not inputs):
    `distance(x,y)` → meters, `get_camera_matrix()` (intrinsics),
    `get_fisheye_distortion()`, `serial`, `camera_features`, `device_info`.
- **Many Category-1 params are `dai.*` enums** (resolutions, preset, median filter,
  alignment) — cannot expose a raw `depthai` enum as a port/setting value. Need a
  Haywire-side plain `str`/`int` enum that maps to the `dai` constant. (Unresolved
  sub-question.)
- **Category 2 only touches the color sensor** (+ 2 IR knobs). If a graph runs
  depth/IR only (`enable_color=False`), the entire exposure/WB/focus/tuning surface is
  inert (the control queue doesn't exist). Argues for grouping live-color params so
  the whole group can hide/disable when color is off.
- **In Haywire, config-port vs NodeSettings is chosen PER PARAMETER**, not for the
  whole node. So the answer to "config or settings?" is a *partition*, not one bucket.

## ⚠️ Terminology collision to resolve (glossary)

`docs/reference/glossary.md:99` defines **Frame** as "one full execution pass through
a Flow from its entry EVENT node to completion" — a control-flow term. But this
library ships a `FRAME` **datatype** meaning a *video image*. Two unrelated concepts,
same word. Disambiguate as the design firms up (e.g. "video frame" / `FRAME` datatype
vs "execution Frame"). The `inquisition` skill is meant to update the glossary inline
when terms resolve — this one is still open.

## Open questions (RESUME HERE)

- **Q4a — union computation coupling:** Settled on single pooled CALLBACK channel +
  per-event-node stream-selection config (which also drives the dynamic outlet
  reveal). Still to confirm: does the **emit node introspect subscribers' declared
  stream-sets** to compute the device-enable union, or should each event node **push
  its stream-set to the emit node explicitly** (e.g. via callback registration
  payload)? Leaning toward the explicit-push to avoid emit→subscriber introspection
  coupling — unconfirmed.
- **Q4b — depth encoding:** What does the `depth` bundle entry carry? Colorized JET
  `depth_map` (display), raw uint16-mm `depth_buffer` (measurement), HSV-encoded, or
  both? Interacts with whether `FRAME` (currently 3-channel BGR/RGB assumption) can
  hold single-channel uint16. **Likely forces a `FRAME` extension or a new depth
  datatype** — not yet designed.
- **Q5 — config/settings partition (recommended D):** pipeline params (Cat 1) →
  `as_config` ports; live-control params (Cat 2) → `NodeSettings` bag(s) grouped by
  subsystem (`color` / `depth` / `ir`). User asked for the param overview before
  answering — **not yet answered.**
- **Q6 — first-cut scope (recommended A):** curated subset (enables + resolution +
  depth preset + alignment + exposure/WB/focus + IR intensity), deferring the
  image-tuning tail (brightness/contrast/saturation/sharpness/denoise/anti-banding/
  effect). **Not yet answered.**
- **Not yet opened:** `dai`-enum → Haywire-enum mapping strategy; `FRAME` datatype
  extension vs new depth datatype; whether Category-3 queries (`distance`, intrinsics)
  become outlets on the emit or event node; start/stop control flow details.

## Constraints / gotchas

- `barn/haybale-visiongraph` is a **gitignored local-only symlink** — `find` without
  `-L` skips it. mypy CI excludes it. Edit through the symlink path normally.
- Per CLAUDE.md: read files before editing; grep callers before modifying a function;
  for substantial changes run `ruff check` + `mypy` baseline on the touched path
  *before* editing, then again after. The codebase is expected to be error-clean —
  if a baseline is dirty, stop and raise it with the user.
- A single OAK device cannot be opened twice — reinforces the single-emit-node-owns-
  the-device model.

## Suggested skills

- **`inquisition`** — resume the design interview (Q4a/Q4b/Q5/Q6). Interview was mid
  -flight; the user values being grilled before any code. Update
  `docs/reference/glossary.md` inline as terms resolve (esp. the Frame collision).
- **`design`** — the structured design interview for architectural decisions in this
  codebase (config vs settings, dynamic ports, datatype design). Pairs well once the
  open questions narrow toward implementation shape.
- **`haywire-nodes`** — load node-authoring docs before writing the emit/event nodes
  (dynamic ports, workers, `PooledType[CALLBACK]`, `emit_callback`).
- **`haywire-settings`** — load settings docs before implementing the `NodeSettings`
  bag(s) for live camera-control params.
- **`verify`** / **`haywire-codesanitizer`** — run after implementation; full repo
  ruff + mypy + pytest must pass before claiming done.
