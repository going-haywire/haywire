# Spandrel haybale — design spec (inquisition-settled 2026-10-30, unbuilt)

Bring [spandrel](https://github.com/chaiNNer-org/spandrel) (PyTorch image-model loading: SR,
restoration, inpainting) into haywire, plus the framework pieces chaiNNer provides around it
that haywire lacks: paths, folder batches, saving, model acquisition.

**Goal (Q1):** batch first (folder in → restore → folder out, chaiNNer-style), but every type
interoperates with visiongraph so the same nodes run in realtime Flows. Haywire is realtime —
speed matters in every design choice below.

Decision numbers (Qn) refer to the inquisition; each is recorded with its reason.

---

## 1. Research findings (ground truth at time of writing)

### spandrel / chaiNNer
- spandrel only **loads**: `.pth` / `.safetensors` / `.ckpt` / `.pt` → architecture auto-detected →
  `ImageModelDescriptor` / `MaskedImageModelDescriptor` (`scale`, `input_channels`,
  `output_channels`, `tiling: ModelTiling`, `supports_half`, `supports_bfloat16`, `purpose`,
  `size_requirements`). No download, no image↔tensor conversion. Deps: torch, torchvision,
  safetensors, numpy, einops; py ≥ 3.10.
- `spandrel_extra_arches`: non-commercial-licensed architectures; opt in with
  `MAIN_REGISTRY.add(*EXTRA_REGISTRY)` *before* loading. chaiNNer enables it unconditionally.
- chaiNNer adds around it: Load Model node (path → model + dir + name); Upscale node with
  auto tile size from VRAM/RAM budget, custom scale (repeat-apply), padding, separate alpha,
  CUDA cache wipe; package settings (GPU index, CPU mode, fp16, memory budget); per-platform
  torch pins via `extra_index_url`; batch via `generator` / `collector` node kinds (Load Images /
  Load Models over a folder with glob, limit, fail-fast) and iterator-scoped caching; Save Image
  = base dir + relative subdir + name + format + skip-existing.
- chaiNNer downloads **no** models; users fetch from OpenModelDB. Exception: facexlib (face
  restore) downloads its own helper weights into `context.storage_dir`.
- OpenModelDB data repo: 671 model JSONs, each with `architecture`, `scale`, in/out channels,
  `license`, `resources[]` = `{platform, type, size, sha256, urls[] (mirrors)}`.

### visiongraph
- Models are raw HTTP from `huggingface.co/cansik/visiongraph/resolve/main/` into
  `~/.visiongraph/assets` (`VISIONGRAPH_ASSET_DIR`); downloaded on first use; no digest.
- `RGB_FRAME` is **BGR uint8** (OpenCV-native; acknowledged in `annotate_node.py:34`).
- Depends on `opencv-contrib-python`.
- Viewer: `StreamingBackend` MJPEG route + `StreamingViewer` element (DROP-1 frame queue).

### haywire (verified in code)
- No PATH type, no file picker widget, no image type outside visiongraph, no folder iteration,
  no user-triggered EVENT node (only BeginPlay / Shutdown / Tick in haybale-core).
- `ForLoopNode` (LOOPBACK) exists; the loopback stack pops on return, so stack depth is nesting,
  not iteration count — 10k-file loops are fine.
- Cancel: the VM checks `cancel` at every control node (`vm.py:207`) and exposes it as
  `ExecutionContext.cancel` — long workers can poll it.
- **Stale-outlet gap:** `BaseNode._execute` pops dirty ports *before* the worker
  (`base.py:156`); `vm._execute_data_node` only records the exception (`vm.py:423`). A failed
  data node's outlet keeps its previous value, and the consuming control node runs on it.
  In a batch: `img_042.png` silently contains image 41. Control-node failures are fine (worker
  returns `None` → loopback pops → next iteration).
- `error_runtime` is sticky — cleared only on revalidation (`node_wrapper.py:382`), never on a
  successful run. Ledger dedupes by fingerprint (`count`, `last_seen_at`).
- `NodeWarning` (`node_warning.py`, has `kind`) is the framework's advisory node surface.
- Marketplace installs via `uv pip` (`library_manager.py:230`); uv 0.13.5 supports
  `--torch-backend auto` (`UV_TORCH_BACKEND`).
- `library_storage_dir()` → `~/.haywire/db/<pkg>/`; `workspace_root` lives on the core DI config.
- Studio's pure-ASGI login gate covers custom FastAPI routes (MJPEG viewer is gated).
- Type inheritance: child → ancestor is passthrough; parent → child needs an adapter
  (`datatype-canon.md:52`).

---

## 2. Settled design

### 2.1 Paths — haywire-core builtin (Q3–Q7, Q30)
- **Volume path:** a PATH value is `(volume, relative)` — volume is its own field, never a
  parsed string prefix (no in-band sentinel).
- **Types:** base `PATH`; derived `FILE_PATH`, `FOLDER_PATH`. "Must exist" vs "write target" and
  extension filters are port/widget options, not types.
- **Volumes** (S1b-Q1–Q3): `~/.haywire/volumes.toml` is the single list of volumes — key, label,
  description, location. The only built-in is `project` (`haywire-core:volume:project`, derived from
  `workspace_root`, never stored, not editable). Keys follow `<library-id>:volume:<name>` and are fixed
  once created; libraries add theirs once (e.g. `haybale-models:volume:models`, S1b-Q4); users add
  `user:volume:<name>` for outside folders (e.g. `user:volume:scans` -> `/Volumes/Scans`).
- **No absolute volume** (Q6C). Every graph stays portable by construction.
- **Locations** live in the framework file `~/.haywire/volumes.toml` (per machine; S1-Q1b), next to
  each volume's label and description; label, description and location are editable, the key is not
  (S1b-Q3). Editing is ADMIN. Libraries that need env vars
  (`VISIONGRAPH_ASSET_DIR`, `HF_HOME`) read their location from the volume and pass it explicitly
  (`cache_dir=`); haybale-models sets no env var (S6-Q9) — the volume is the single source.
- **Resolver** refuses a resolved path that escapes its volume root (`..`, outward symlink),
  checked on the resolved path.
- **Undefined volume** (Q7B, amended by S1-Q3): value kept verbatim; widget shows "volume undefined";
  node errors at run time via the ledger; ADMIN action is "fix in the Volumes editor or
  `haywire volumes set`".
- **Picker** (S1-Q3/Q4): server-side filesystem browser (the browser cannot give server paths) —
  volume select + relative field + browse popup + status line, rooted at volumes only; mode from the
  derived type (file / folder / save target). The eager-then-lazy tree is a shared core element, also
  used by `LazyFileBrowserEditor`. No in-widget define action.

**S1 decisions (2026-10-30)**

| # | decision |
|---|---|
| S1-Q0 | The concept is called **volume** (not "anchor": that word is the UI attach point of flyouts/popups/pins). Value = **volume path**. |
| S1-Q1a | `~/.haywire/db/<name>/` uses the **top-level module name**; fix the three drifted docstrings. |
| S1-Q1b | Volume locations live in the framework file **`~/.haywire/volumes.toml`** (not settings — the app never writes the global settings tier, and workspace `settings.json` is committed). |
| S1-Q2 | ~~Volumes are declared **Surface-style** (class registry on import, hot-reload supersede, collision raises); `volumes.toml` entry wins over the declared default; an entry may name an undeclared volume (ADMIN-defined outside folder).~~ **Superseded by S1b-Q1/Q4.** |
| S1-Q3 | Picker widget (volume select + relative field + browse popup + status line); volumes are defined in an **ADMIN Volumes editor** and the CLI — no in-widget define action (amends Q7B). |
| S1-Q4 | The eager-then-lazy folder tree moves from `LazyFileBrowserEditor` into a core element both use. |

**S1 deviations from plan**

- CLI `set` absolutises a relative folder against cwd (plan Step 1 said refuse); the store still refuses relative locations.
- PathWidget's mode reaches ports via `PATH._configure_port`.
- `FolderTreeModel` gains `extensions=` and a shared `DEFAULT_EXCLUDE_DIRS`.
- ~~`Volume.label` defaults to the volume's name.~~ (superseded by S1b-Q1/Q4: no class registry)
- ~~A declared default that raises or is relative is logged and the volume is reported undefined.~~
  (superseded by S1b-Q1/Q4)
- `project` is undefined in the CLI (no workspace root outside the studio).

**S1b decisions (2026-10-30, after the S1 live check)**

| # | decision |
|---|---|
| S1b-Q1 | `~/.haywire/volumes.toml` is the **single store**: one entry per volume with key, label, description, location. No volume exists outside it except `project`. |
| S1b-Q2 | Volume **key** follows the registry-key pattern `<library-id>:volume:<name>` (e.g. `haybale-models:volume:models`); volumes a user adds get `user:volume:<name>`. The key is **fixed once created**; renaming means a new volume. |
| S1b-Q3 | Everything stored in the file is **editable** (label, description, location). `project` (`haywire-core:volume:project`, = ambient workspace root) is built in, never stored, never editable. There is **no `home` volume**. |
| S1b-Q4 | A library adds its volume from its **`AppState.on_enable`** via `ensure_volume(key, label, description, location)`: writes the entry only when the key is absent, never creates the folder, safe on every enable / hot reload. |
| S1b-Q5 | **Deleting** a library's volume is a reset: the library adds it back with its suggested location on its next enable. Uninstalling a library leaves its entry as an ordinary volume. |
| S1b-Q6 | A PATH value stores the **key** (`VolumePath.volume`); the UI shows the label. |
| S1b-Q7 | **No source column, no state words.** Status carries facts: location (`None` = not set), exists, editable. |
| S1b-Q8 | Suggested model location: `~/.haywire/db/<module>/models` (S6, haybale-models) — suggested, not enforced. Any future "reset library data" tool must leave a `models` folder alone. |
| S1b-Q9 | The store serializes read-modify-write with a process lock and writes atomically (temp file + rename). |

**S1b deviations from plan**

- `ensure_volume` on an unreadable volumes file logs and adds nothing instead of raising, so a broken file never stops a library from enabling.
- `haywire volumes add` makes a relative folder absolute against the current directory, like `set`.
- The PathWidget's "not defined" status names the volume by the key's name part.
- `list_volumes` treats an OS error checking a location as "missing".

**S1b follow-up — DONE 2026-11-01 (f8cd13fad on master; found in the S6 live check; live-checked)**. Deviations: `ensure_volume` also backfills `suggested` on an existing entry (volumes added before this change get one on the library's next enable); a library volume with no recorded suggestion shows no Reset button; `VolumeStore.remove` itself refuses library keys, so the CLI `remove` does too, and a new `haywire volumes reset` exists; open gap: an uninstalled library's volume can no longer be deleted except by hand-editing the file.

- A volume a library added (key not `user:volume:…`) shows **Delete** in the Volumes editor. Delete means "reset" (the library re-adds it with its suggested location), but only at the library's next `on_enable`; until then the volume is undefined and the library breaks (Models refuses to scan and download). Decision (b): library volumes get **Reset to suggested location** instead of Delete — `ensure_volume` also stores the suggested location in the entry (`suggested` field in `volumes.toml`) and Reset writes it back at once, so the volume never disappears. Only user volumes (`user:volume:…`) can be deleted. Tell by the key.

### 2.2 Batch nodes — haybale-core (Q8, Q11, Q12, Q31)
- **`Run Button`** — EVENT widget node; emits one Trigger; OPERATE tier.
- **`For Each File`** — LOOPBACK. Inputs: folder, glob (stdlib `pathlib` glob, `**` recursive),
  recursive, limit, `on_error = continue | stop`. Outlets: `loop_body`, path, relative subdir,
  stem, index, `failed` (list of paths), `completed`. Progress via ProgressSettings (index/total).
- **`Path Exists?`** — control branch (`exists` / `missing`) on any `PATH`.
- **`Output Path`** — data node: `volume-folder / relative-subdir / stem + suffix . ext`. The
  single home of "mirror the input subfolder structure".
- Resume pattern: `For Each → Path Exists? →(missing)→ Save`. Upscale is a DATA node pulled only
  by Save's localized data flow, so an `exists` branch never runs it. Save keeps
  `if_exists = overwrite | skip | unique-suffix` as a safety net.
- Ship the full pattern as a **macro** ("Batch Upscale Folder") once spandrel lands.

**S4 decisions (2026-10-30, inquisition S4-Q1–Q20; full table in the [S4 plan](2026-10-30-s4-batch-nodes.md))**

- **Run Button** triggers a flow in a *running* graph, TickEmit-shaped: inlets `start`/`stop`/`callbacks`,
  outlets `started`/`stopped`; the listener is the existing **Tick Event** (payload `delta_time` = time since
  the previous emit). The press is a BOOL setting promoted as CONFIG, drawn by a new builtin **`ButtonWidget`**;
  a click writes `True` through the edit route (OPERATE gate); the node emits and releases it (see deviations). Clicks
  before pickup coalesce; picked-up runs queue (`BLOCK`); `start` clears a stale press.
- **For Each File:** `pattern` = `;`-separated file-**name** patterns, case-insensitive; `recursive` sets depth;
  dot-names skipped; symlinked folders not entered, outward file links skipped; listing taken once at `execute`,
  sorted, `limit` after sorting; adds `break_loop`, `extension`, `total` and `stopped` (see deviations). An unlistable folder raises.
  `on_error` acts under bail `branch` only (`frame`/`run` abandon the loop); `on_frame_end` closes an abandoned
  loop's progress.
- **Path Exists?:** plain `exists()`; an unresolvable path raises.
- **Output Path:** validates its parts and raises naming the part; extension with or without a dot.
- No ADR, no glossary term (the VM fix below is a bug fix, not a semantics decision).

**S4 deviations from plan (2026-10-31)**

- **VM fix: an edge back into a looping node keeps its inlet.** `_navigate_next` re-entered a node already on the
  loopback stack with no inlet, so a Break wired from the loop body arrived as "next iteration" (For Loop's Break
  never worked from the body). Now the edge's inlet is passed; an implicit return (branch ends) still enters with
  none. An edge from the body back into `execute` therefore restarts the loop (the Group-straddle test fixture
  wired one and was fixed to let its branch end). A Break from another flow still has no effect (frame border).
- **`stopped` outlet on For Loop and For Each File** (user request): Break, and For Each File's `on_error=stop`,
  end the loop through `stopped`; `completed` fires only when the loop ran through. For Loop's Break used to fire
  `completed`. For Each File keeps `break_loop` (Q16).
- **Run Button has no thread** (reverses Q5c, user decision 2026-10-31): the press's field subscription emits to
  the listeners at once (enqueueing waits only on a full `BLOCK` queue) and releases the button with `post_value`,
  which runs after the press's own write. A press while the button is still held changes nothing, so it emits
  nothing.
- Live check found an S1 defect: a `PATH` port's default and any JSON write (Farmhand `set_property`) stayed a
  plain dict, so nodes failed on `.volume` and the graph could not be saved. Fixed with `PATHField` (converts on
  default and on every write, as `INTField` does).
- `haywire docs --all` also regenerated pages earlier slices had left stale (own commit).
- **Copied callback listeners publish their own id**: a copied Tick Event / Custom Callback kept the original's id
  on its Listen outlet, so emitters wired to the copy triggered the original's flow. Fixed in `post_init`.
- **Path → text adapter + Resolve Path node** (user request): a path wired into a text inlet carries its display
  form `volume name:relative`; Resolve Path gives the absolute location on this machine and reports an undefined
  volume or an escape as a node error.

**S4 deferred minors (from the final review and the live check; not fixed)**

1. `ButtonWidget` uses raw `ui.button` (Quasar primary colour, uppercase label, `w-full` without `flex`); design
   guide §8.8a wants `hui.button`.
2. Each press in EDIT mode adds an undo step and marks the graph unsaved; undo looks like a no-op, redo fires a run.
3. Output Path accepts `.`/`..` as the name; `PATHField` turns a malformed dict into the project root.
4. File order is case-sensitive (`Z` before `a`); `limit` takes the first files in that order.
5. `on_error` is matched exactly: a wired `"Stop"` behaves as `continue`.
6. Docstrings: Tick Event lists port ids instead of labels; `ButtonWidget` uses reST like its siblings.
7. For Each File shows inlet "Subfolders" and outlet "Subfolder" on one card.
8. `failed` keeps the previous run's list until the loop ends, and after a failed `execute`.
9. Farmhand `set_property` on a PATH port reports `set_rejected` though the write landed (read-back compares the
   requested dict with the stored `VolumePath`).
10. Not live-checked: Run Button pending spinner and VIEW-mode refusal in a real browser (Chrome extension was not
    connected).

**S4b decisions (2026-10-31, inquisition after S5; built inline, no plan file)**

- **List Files** (`core/paths`): a CONTROL node that lists the folder on every `Execute` (same rules as For Each File) and outputs `Files` (`ArrayType[FILE_PATH]`) and `Total`.
- **Loop Array** (`core/control/loops`, LOOPBACK): the `Array` inlet is an open `ADD` slot that takes `ArrayType[T]` from the wire; `Item` becomes `T`, `Failed` `ArrayType[T]`. Keeps For Each File's `On Error` (`continue | stop`), `Break`, `Completed`/`Stopped`, progress. Empty or unwired array → `Completed`.
- **Step Array** (`core/control/loops`): `Start` snapshots the array and steps item 0, `Next` advances, `Stop` forgets; `mode = once | loop | palindrome` (palindrome does not repeat the ends). In loop/palindrome `Completed` fires at every return to item 0, then `Step`. `Next` before `Start` does nothing; state resets on graph start.
- Pacing comes from Tick Emit (0.5 FPS = 2 s per item); no timer node.
- For Each File stays as it is.
- Deviation: a worker fires one outlet, so Step Array is a LOOPBACK node whose `Completed` loops back to fire `Step` for item 0 in the same frame.

**Follow-ups booked from S5**

- Delete File / Delete Folder — lead option OS trash via `send2trash`, not a trash volume (`/tmp` self-wipes; cross-disk moves copy) (S5-Q13).
- Resize node (S5-Q21).
- Low priority — more image formats:
  - JPEG XL and HEIC/HEIF: neither cv2 nor Pillow decodes them here; add each as an opt-in extra (`pillow-jxl-plugin` / `pillow-heif`) plus extension and round-trip test. HEIC brings libheif/libde265 (LGPL, HEVC patents) — decide on licensing first.
  - DDS: read-only via Pillow for the common BCn variants; a GPU texture format (mipmaps, cubemaps) that fits "one image" poorly.
  - EXR and Radiance HDR: cv2 already encodes/decodes them; blocked on an inquisition about HDR semantics of the IMAGE value (values above 1, linear vs. display-referred, what View/Save do with them). Relevant to S7 too.

### 2.3 Failure poisoning — haywire-core VM (Q9, Q10, Q37) — **ADR required**
1. **`failed` flag** per node, separate from `error_runtime`. Set when a worker raises (data or
   control); cleared when the worker next returns normally. `error_runtime` stays the sticky
   diagnostic.
2. **Failed stays dirty:** on exception `_execute` re-inserts the ports it popped into
   `_has_dirty_ports`, so the next evaluation retries (transient OOM recovers).
3. **Blocked, transitively:** in `_evaluate_data_flow`, before a data node runs, if any of its
   **data-inlet** sources is failed or blocked-in-this-pass, skip it **without popping its dirty
   ports** and add it to the pass-local blocked set. Control (exec) edges never poison.
4. **Control node:** the same check on its own data inlets; blocked → no worker → return `None` →
   existing branch-end / loopback-pop path.
5. **`ExecutionContext.failures`** — append-only `(node_id, error | "blocked")`. `For Each File`
   snapshots `len()` at `loop_body` and compares on re-entry → `failed` outlet; `on_error=stop`
   returns `completed`.
6. **Surface:** blocked node gets `NodeWarning(kind="blocked", "skipped: <upstream> failed")`,
   removed on its next real run; no ledger entry (the root cause already has one, deduped).
- Partial writes: a node that wrote outlet A then raised poisons all its outlets.
- Shared data nodes (ADR 0064): flag lives on the node; every group sees it.
- Behaviour change for live Flows: consumers of a failed node skip that frame instead of running
  on stale data. Sweep tests/graphs for anything relying on "run anyway".
- Out of first cut: adapter exceptions during transport; a general `accepts_failed` port
  capability for a future Try/Fallback node (never a per-node-kind gate).

**S2 deviations from plan (2026-10-30)**

- **Failure poisoning replaced by bailing** (S2-Q10, user decision after the final review): items 1–6 above
  are not built. On a worker exception the VM reports it, marks the node's data inlets dirty (retry at its next
  evaluation), records `(node, exception)` in `ExecutionContext.failures`, and bails by the graph's run policy
  `GraphRunSettings.on_exception_bail`: `branch` (default; a loop goes on), `frame` or `run`. A worker error on
  a card clears when the flow's next frame starts. No failed/blocked flags, no counters, no source lists. ADR
  0066 records it.
- Retry re-marks **all data inlets** dirty, not the ports the failed run had resolved: on a retry `on_change`
  fires for unchanged inlets too.
- The hot-path budget below applies to what remains: one boolean test per data node, one attribute test per
  control node. The four failure-path benchmark cases stay.
- `on_error=continue|stop` tests move to S4 (`For Each File` does not exist yet); S2 tests the `failures` list.

**Hot-path budget & performance tests (mandatory for this slice).** The check runs once per data
node per evaluation, so it must be ~free when nothing failed:
- Fast path: a failure counter (flow- or pass-scoped) that is zero in the happy path — the
  per-node check is then one integer test. Precompute each data node's upstream data-node
  indices at Assembly (on `LocalizedDataFlow`) so the slow path never walks ports/edges.
- **Record a clean baseline** of `graph_loop` and `node_execute_bare` on `master` *before* the
  first S2 commit (`haywire-benchmark`, clean tree).
- **New benchmark cases** (absolute per case, min-of-N, fixed topology, DO-NOT-EDIT nodes in
  `barn/haybale-testing/haybale_testing/nodes/benchmark/`; never a derived delta):
  - `graph_data_chain_ok` — one control node whose localized data flow is a 32-node chain plus a
    fan-in, all succeeding → cost of the check per data node in the happy path.
  - `graph_data_chain_root_fails` — same topology, root data node raises every frame → cost of
    exception + dirty re-insert + transitive blocking.
  - `graph_loop_half_failing` — LOOPBACK body where every other iteration's data node raises →
    loop with failures and `context.failures` bookkeeping.
  - `node_execute_raises` — micro: one node whose worker raises → exception path incl.
    dirty re-insert.
- **Acceptance:** `graph_loop`, `node_execute_bare` and `graph_data_chain_ok` show no move beyond
  noise vs the baseline (target ≤ 2 % on min); a blocked node costs less than running it
  (`graph_data_chain_root_fails` < `graph_data_chain_ok`). Fold the result rows into the slice's
  commits.
- Correctness tests alongside: stale-image regression (the `img_042` scenario), transitive
  blocking, retry recovery, control-node failure with data outlets read later in the frame,
  shared data node across two execution groups, `on_error=continue|stop`.

### 2.4 Images — new `haybale-image` (monorepo `barn/`) (Q2, Q24–Q29)
- **Types (Q25C):** base `IMAGE` (any layout); derived `IMAGE_GRAY`, `IMAGE_RGB`, `IMAGE_RGBA`.
  Layout-generic nodes (Load, Resize, Upscale, Save) take/return `IMAGE`; layout-dependent ports
  declare the derived type. **No BGR types.**
- **Value (Q27A, revises Q24):** *semantics fixed* — RGB order, values in [0,1], layout from the
  type, `source_depth: 8|16|32`. *Storage free* — dtype (u8/u16/f16/f32), channel order (RGB/BGR),
  residency (ndarray or tensor@device). Nodes reach pixels **only** through accessors
  (`img.array(dtype=…)`, `img.tensor(device, dtype)`): lazy, GPU-side conversion preferred,
  cached on the immutable value. float32 is the accessor default, not the storage.
- **Adapters (real, type-changing):** `IMAGE → IMAGE_GRAY/RGB/RGBA` (by runtime layout),
  `GRAY ↔ RGB ↔ RGBA`, running on the value's residency. Storage conversion is **not** an Adapter.
- **Helpers (Q26C):** `to_pil`/`from_pil`, `to_tensor`/`from_tensor` (lazy torch import),
  `to_cv_bgr`/`from_cv_bgr`; PIL modes `P`/`LA`/`I;16`, premultiply, depth rules handled once.
- **Codecs (Q28B):** OpenCV first — PNG 8/16, JPEG, WebP, TIFF 8/16/f32, BMP; Pillow for GIF
  (read), TGA, AVIF (optional extra), ICC/EXIF passthrough. Depend on **`opencv-contrib-python`**
  (same distribution as visiongraph — cv2 variants clobber each other). Save defaults to
  `source_depth`.
- **Nodes:** Load Image (FILE_PATH → `IMAGE` + stem/dir), Save Image (`IMAGE` + FILE_PATH +
  format + `if_exists`), View Image.
- **Viewer (Q29B):** move `StreamingBackend`/`StreamingViewer` here from visiongraph (visiongraph
  reuses it); modes `stream` (MJPEG, live) and `still` (PNG on demand, 1:1 zoom); DROP-1 for
  batch previews.
- **Visiongraph adapters (S9):** `RGB_FRAME`/`GRAY_FRAME` ↔ `IMAGE_*` as zero-copy wraps tagging
  storage BGR u8.
- **S0 result (2026-10-30, host MB-41545, Apple M1 Max, MPS, torch 2.15.0, commit a6fddf81f6e3):**
  min per op — `img_wrap_1080p` 1.9 µs; `img_cpu_f32_1080p` 5.05 ms (input side only of the
  rejected Q24C path); `img_gpu_up_f16_1080p` 1.26 ms; `img_gpu_down_u8_1080p` 1.96 ms;
  `img_gpu_trip_1080p` **3.18 ms** (gate ≤ 3 ms: missed by 6 %; gate "< cpu_f32": met);
  `img_sr2x_540p` 63.9 ms end to end with Real-ESRGAN v2 animevideo xsx2 fp16 (model-bound; over
  the 33 ms frame budget on this machine). **Gate failed → Q27 reopened.**
  Rerun after the final-review fixes (commit cad5d961a, same session): trip 3.37 ms, up 1.38 ms,
  down 2.08 ms, cpu_f32 5.17 ms, sr2x 65.4 ms — unchanged code paths moved +2…6 % too, so the
  delta is session noise (README: ±4 % across sessions), not the fixes. The reviewer measured an
  in-place `clamp_/mul_/round_` download at ~0.2 ms faster.
  **Tuning (commit 778d98316):** on MPS a fancy-index channel swap and a permute copy each cost a
  full pass; every conversion now writes one copy in the destination layout with channels in
  target order, then scales in place. Interleaved A/B (min of 8 alternating rounds): up 1.28 →
  0.53 ms, down 1.94 → 0.74 ms, trip 3.43 → 1.45 ms. Harness, 3 runs: `img_gpu_trip_1080p`
  1.19–1.31 ms, `img_cpu_f32_1080p` 5.0–5.3 ms, `img_sr2x_540p` 63.0–63.1 ms (model-bound).
  **Gate met (≤ 3 ms and < cpu_f32) → Q27A stands.** SR at 33 ms needs a faster model or GPU,
  not a different value design.
  Deviations from the S0 plan: `Layout`/`ChannelOrder` live in `haybale_image/value/enums.py`;
  `_torch_ops.convert_tensor` added for tensor→tensor hops; torch tests run with
  `uv run --with torch python -m pytest`; `uv.lock` records torch as an optional extra but
  no sync installs it.

**S5 decisions (2026-10-31):** see the decision table in [the S5 plan](2026-10-31-s5-haybale-image.md).

**S5 deviations from plan**

- No `format` inlet on Save Image: the extension is the format (S5-Q7).
- AVIF is supported out of the box, not as an optional extra: Pillow wheels carry it.
- No tensor helper wrappers: `ImageValue.from_tensor` / `.tensor()` already are.
- IMAGE's `@type` default is a descriptive dict (`{width: 0, height: 0, layout}`); `IMAGEField` and `IMAGE.__init__` turn it into an empty `ImageValue` (`@type` refuses non-JSON defaults) — PATHField pattern.
- GIF is written with Pillow (cv2 5's GIF encoder fails on gray and dithers colour).
- Format limits found while building: gray reads back as RGB from WebP and GIF; GIF/JPEG/BMP drop alpha; TIFF carries ICC but not EXIF; float RGB(A) TIFF carries no metadata; an opaque RGBA saved with metadata via Pillow (WebP/AVIF) reads back RGB; 16-bit / float saves drop ICC/EXIF; a PNG whose eXIf chunk follows the pixel data is not seen (header-only read).
- Save Image's per-format bags are module-level classes attached with `bag()` (mypy typing); `tiff_compression` is `setting[CHOICES]`; the path inlet uses the PathWidget `save` mode; BMP/GIF/TGA hide all bags.
- Output Path's new outlet has id `out_folder` (the inlet already uses `folder`).
- `atomic_write` takes `placeholder=` so only a claimed unique-suffix placeholder is removed on failure.
- Benchmarks: six `img_*` cases recorded (codec fixtures are random noise — worst-case entropy).

**S5 deferred minors (final review; not fixed)**

- ICC profile kept when it no longer matches the layout (CMYK JPEG → RGB keeps a CMYK profile; GRAY↔RGB adapters keep the profile). `encode_image` should drop an ICC whose colour space (header bytes 16–19) does not match the written layout.
- View Image still mode fed by a live source pushes a prop update per frame (whole-page re-render) and encodes a PNG per fetch — throttle version pushes.
- Save Image `_shown_format` is read and written from UI and runner threads without a lock (worst case: briefly stale bag visibility).
- Overwrite via `os.replace` replaces a symlink with a regular file and drops the old mode/owner.
- Live check: still render confirmed by the user (2026-10-31, 10-bit AVIF). Not yet checked in a browser: 1:1 toggle, MJPEG stream, mode rebuild, Save Image `.jpg` bag visibility after reload (Farmhand cannot write a FILE_PATH inlet).
- Fixed after the live test: 10/12-bit AVIF — cv2 returns unscaled uint16 (0..1023/0..4095); the codec reads the bit depth from the av1C box and scales to full range.
- 12-bit TIFF (BitsPerSample=12) not verified: no available tool (Pillow, cv2, tifffile absent) writes one for a test, so TIFF handling is unchanged; it may decode unscaled like AVIF.
- If the av1C box cannot be parsed, a 10/12-bit AVIF still loads dark (values left as decoded).

**S5 deferred minors (per-task reviews; triaged "stay deferred" by the final review)**

1. Value: `with_metadata` values share one conversion cache (a concurrent first fill converts twice; harmless); no `from_tensor(metadata=)` test.
2. Layout: RGB→GRAY accumulates in float32 (cv2 uses fixed-point); torch alpha hardcodes 255 instead of `alpha_opaque`; no float16/bfloat16 luma tests; torch paths tested on CPU only (MPS/CUDA untested).
3. Helpers: `unpremultiply` has no float-dtype guard (uint8 input gives wrong results); `premultiply` copies twice; a vacuous `is not None` assert in `test_helpers.py`; RGBA `to_pil` test checks the mode only.
4. Types: `_as_image` falls back to GRAY on a dict without `layout` (should use the type's `LAYOUT`); dict writes are discarded silently; no field round-trip tests.
5. Codecs: TIFF EXIF (`get_ifd(0x8769)`) not carried; a PNG eXIf chunk after the pixel data or an XMP-only orientation is not seen (header-only read); `_read_header` mutates the cached Exif; `options.depth or` should be `is None`; a bomb-sized TGA/palette file gives the generic "cannot read image" error; the huge-image fallback's docstring/warning do not say orientation is skipped; no AVIF-metadata or PNG/WebP-EXIF tests.
6. Placement: the temp name adds ~14 characters (names near 255 bytes fail); SKIP is check-then-act.
7. Load Image / Image Info: no BGR→RGB pixel assertion and no corrupt-file test at node level; Image Info RGB/RGBA untested.
8. Save Image: only the JPEG bag → `EncodeOptions` wiring is tested (a cross-wired bag would pass); no test for all bags hidden on BMP/GIF/TGA or for an unknown extension in the worker; a hand-edited `depth`/`if_exists` raises Python's raw `int()`/enum error.
9. Path nodes: a volume root that is a file gives a generic OS error from Create Folder; Split Path has no dotfile/no-extension tests; Output Path's docstring sentence "`Folder` is the folder the file goes in" predates the `Parent` outlet label.
10. Viewer: stream mode keeps the last frame on an empty image (still mode hides it); the stream queue reader polls every 0.1 s until cleanup (inherited from visiongraph); the mode-change test checks the config only; `backend.py` holds both backends and the element.
11. Benchmarks: codec fixtures are random noise (worst-case entropy); the temp dir is never cleaned; the stream case sets the private `_is_running`.
12. Tests: `tests/image/test_library.py` checks the installed environment, not the pyproject declaration; several tasks have no recorded RED run.

### 2.5 Models — new `haybale-models` (monorepo `barn/`) (Q13–Q17, Q21, Q34)
- **Model reference (Q13B):** source URI (`hf://org/repo/path@rev`, `https://…`, or local) +
  sha256. Plain local paths allowed. Graph stores the reference → runnable on a fresh machine.
- **Model catalog (Q14D; kind later renamed `catalog`):** a component kind libraries register (entries = reference + metadata
  in OpenModelDB's shape: architecture, scale, channels, license, size, sha256, mirror urls).
  Subscribable feeds later.
- **Models editor:** one, framework-wide: lists every library's catalog + local models, disk
  usage, download (resumable, mirror fallback, progress, digest-verified), remove.
- **Needs-list:** on graph open, collect model references from nodes → "needs N models (X MB) —
  fetch all".
- **Store (Q16B):** `models` volume (`haybale-models:volume:models`, added by this library's
  AppState via `ensure_volume`, S1b-Q4; suggested location `~/.haywire/db/haybale_models/models`,
  S1b-Q8 — suggested, not enforced; a future "reset library data" tool leaves `models` alone) = human folders
  (`models/openmodeldb/4x-UltraSharp.pth`, user subfolders allowed) + `models/.index.json`
  (sha256 → path + source; re-hash only on size/mtime change). Dropped-in files become indexed
  *local* models on next scan. Moved/renamed files still resolve by digest.
- **HF (Q15C):** `hf://` resolves through `huggingface_hub` into the HF cache (`HF_HOME`);
  shown as "external (HF cache)"; **haywire never deletes there**. HF provides sha256 via
  `lfs.oid`. Gated repos (token) wait for the security document.
- **Resolution order:** index by sha256 → HF cache (`hf://` only) → **missing**. Missing never
  downloads in a worker; node errors "model missing — fetch from Models".
- **Tiers (Q34B):** download and remove are ADMIN.
- **`LoadedModels` pool (Q21B):** keyed `(sha256, variant_key)`, refcounted by holder nodes;
  libraries supply `load(path)` and `release(obj)`. No eviction yet.

**S6 decisions**: see the [S6 plan](2026-10-31-s6-haybale-models.md).

**S6 deviations from plan:**
- Nothing was committed during execution; the slice was committed afterwards as six commits (`ab52290dc..eeaf9db5a` on `feat/s6-haybale-models`).
- Catalog component kind renamed `model` → `catalog` (key `<lib>:catalog:<stem>`, `CatalogRegistry`) and the core module `haywire.core.models` → `haywire.core.catalog`, so "model" means only the model itself.
- Model stems follow their own rule (`[A-Za-z0-9][A-Za-z0-9_-]*`, so `4x-Demo` is valid), not the macro registry's.
- A download target takes an optional digest lookup to add `-<sha8>` on a same-name, different-digest file; without one it never suffixes.
- `ResolvedModel.key` is the pool key (sha256 when known, else `path:` + absolute path); `sha256` stays honest and is empty when unknown.
- Core `NodeWrapper.replace_warnings(kind, warnings)` was added; the consumer and the needs-list use it. A missing non-empty ref sets the "Model missing" warning, an empty ref clears it.
- The scan runs on library enable (S6-Q19), which no task had listed; `ModelsState.on_enable` starts it on a daemon thread.
- The widget's status line uses the owning node's `model_preference` when the port has an owner, else the port's `prefer`, so it matches the worker.
- Catalog-wide status is resolved when the picker popup opens; a model change resolves only the current ref.
- A mirror switch deletes the `.part` file; resume only applies across restarts of the same URL.
- Two jobs writing the same target: the second fails fast ("another download is writing ...").
- Downloads send `Accept-Encoding: identity` (Range offsets are raw bytes); the activity tracker starts inside the `try`.
- Path traversal in layout (a `..` basename, a bundle `file.path` with `../`) is refused; download is the only writer.
- `huggingface_hub` resolved to 2.4 (plan said at least 1.0).
- `@library(dependencies=...)` no longer exists; `linked_libraries` in `haybale.toml` declares graph-editor.
- Show in Models opens the editor; the **Needed** section at its top lists, per open graph, the missing models with status, Download/Cancel and Fetch all (there is no graph filter). The HF cache section lists only files a catalog entry or an open graph refers to, with what uses each. Draws do one locate per row.
- Removal deletes only digests actually removed from the index; with nothing deletable it notifies and shows no dialog.
- `models_list` `local` lists every indexed file, with no "unclaimed" filter.

**S6 live check (2026-11-01)**

Passed: notice + filtered Models editor, Fetch all (catalog and pasted address), Pin digest + undo, `hf://` download (auto-pin from `lfs.sha256`, progress moves under Xet — the `*.incomplete` glob matches Xet's temp blob), Remove (confirmation names the graph, notice returns), Rescan of a dropped-in file, VIEW tier, deleting a node with a model warning, needs watcher across a graph-editor hot reload, Farmhand `models_list` / `models_needs` / `models_fetch`, Models editor scroll position during downloads (progress updates in place, no redraw), model picker stays open while statuses fill in, library-wide compatibility notice on the row (tested with a temporary `compatibility_warnings()` in haybale-example, removed afterwards; dismiss hides it per editor). The two OpenModelDB demo entries are byte-identical to upstream `data/models/` at commit `782aac08`. Fixed during the check: filter redraw, notice icon/popup look, Barns properties surface + Models/Image settings panels, the data-node first-run gap (ADR 0070), Addresses and Downloads sections, HF list refresh/sort/collapse, a "Needed" section in the unfiltered editor. The notice popup closing on "Show in Models" is intended.

Still open:
- **Follow-up — reloading graph-editor corrupts the open page.** After a graph-editor hot reload the Properties editor (`PropertiesEditor._rebuild_content`, `GraphSettingsPanel.draw`) draws into deleted slots ("The parent element this slot belongs to has been deleted"); the page needs a browser refresh. Not S6 code and not a regression (pre-existing, per the user).
- Follow-up idea: deprecated nodes (`deprecation_warning` in the node decorator, shown on the card only) could post a graph notice ("This graph uses N deprecated nodes") as a third producer.
**S6 deferred minors (per-task and final reviews; triaged "can wait" by the final review)**

1. Catalog registry: no test for a malformed `sha256` inside bundle `files[]`; a bundle file with neither `urls` nor `sha256` is accepted (unfetchable); `Resource` `platform`/`type` default `""` is hidden by `tags()` and only half documented.
2. Graph notices: `rekey` swaps `_graphs` and moves notices under separate lock acquisitions (a post to the new id in the gap is overwritten); `_emit_notices_changed` duplicates the `_on_history_changed` loop hop; no test posts from a real worker thread or checks that `rekey` emits.
3. Haystack row: `_dismissed_notices` is never pruned (a re-post under the same key stays dismissed); the tooltip's `\n` join renders as one line; `register` never retracts stale `haywire:compatibility:<i>` keys on re-register; findings computed after `register` are never posted; markers use `.props(data-hw-mark)`, not `.mark()`; test helpers duplicate `_render`, and `_dismiss_buttons` matches any close icon.
4. `hf_default_cache` ignores `XDG_CACHE_HOME` and the legacy `HUGGINGFACE_HUB_CACHE` (follows the plan's literal order) — consider `huggingface_hub.constants`.
5. `MODEL_REF`: `_configure_port` `setdefault` shares the mutable `{}`/`[]` defaults across ports (deepcopy); `pinned()` on a catalog ref raises a generic `ValueError`; a catalog ref with a `label` is refused.
6. Matcher/layout: a multi-dot name gets the `-<sha8>` suffix before the last extension only; the matcher test stub uses `LibraryIdentity.__new__`; `entry_matches` returns `False` for an unknown filter key.
7. Index: `_fail` notifies listeners under the scan lock (others notify outside); `by_sha256` may return a vanished path, or an arbitrary one among duplicates; an `on_progress` exception aborts `hash_pending` (no save/notify); `_lost_sources` (source kept across a move) is in memory only; no concurrency/corrupt-index tests beyond those added. Rule kept: an index listener must never call `scan()`/`hash_pending()` synchronously (it runs under `_scanning`/`_hashing`).
8. HF bridge: an `on_progress` that raises kills the poller silently; cancel waits for `hf_hub_download` to finish (multi-GB).
9. Resolver: `ModelFile` re-exported from `resolver`; a pinned digest is trusted as the pool key even when the file was found through the HF cache or by URL (add a comment); the pool key flips from `path:` to the digest once a file is digested (same file briefly under two keys); catalog stub and a dead `bundle()` helper in tests.
10. Pool/consumer: the per-key lock is not reentrant (a `load` must not acquire from the pool — document); a load in flight escapes `release`/`release_all`; `acquire_port` re-resolves on every call; per-key locks are never pruned; `widget_config["properties"] = None` is not handled; consumer tests use fake nodes. All `MODEL_REF` ports of one node share one `"model"` warning list (last call wins; the needs watcher clears only a list equal to `[MISSING_WARNING]`) — key it per port when a two-port consumer lands.
11. Widget/demo: both Compact Pretrain demo entries are named "Compact Pretrain" (2x/4x); a filtered-out installed entry is labelled "not installed"; the Other… row is not revealed on a model change; option texts are cached until the next popup-show; untested: a pasted filtered-out catalog ref (Q4), the "HF cache" status, a bundle's folder path, a VIEW-tier pick.
12. Downloads: a 206's `Content-Range` start is not checked; HTML/4xx on a resumed attempt leaves the old `.part`; finished jobs are never pruned (`jobs()` grows); `stop()` joins up to 5 s per thread sequentially; a close-delimited truncated body with no sha/size is indexed; a re-queued job may Range-resume a leftover `.part` from a later same-host mirror (unpinned only); a target claim is held across mirrors until the job ends.
13. Needs watcher: "Needs 1 model (0 B, 1 of unknown size)" wording; `batch_total` not reset on `rekey`; `stop()` would self-deadlock if called from inside a walk (only caller: `on_disable`).
14. Models editor: unlinking a file the pool holds relies on POSIX semantics, with no warning; dead branches; a firing trailing timer counts as pending during its own redraw (a filter switch inside the window stays stale until the next signal); relies on NiceGUI's private `Timer._is_canceled`; the timer is faked in tests; untested: Rescan, "indexing… N %", `failed:` status, HF scanning.
15. Farmhand tools: `in_hf`/locate logic is duplicated between the tool and the editor (only the status text is shared); `status.py` docstring says "every file" where callers use any.
16. Tests: `tests/models/conftest.py` docstring about redirecting HOME is stale; the session-wide `library_storage_dir` redirect shares one per-package dir across tests in a worker; `ModelsState.on_enable` creates the default models folder even when the volume was moved. Pre-existing (fails at `eec4193cf` too): `tests/image/test_save_image_node.py::test_library_default_reaches_node` under `-m integration -n 4`.

**S6b — model picker dialog (settled with the user 2026-11-01, implemented inline)**

The `MODEL_REF` widget is the model picker of every node with a `MODEL_REF` inlet. The select + address field + status line looked incomplete in every state (a Models-folder file has neither a catalog key nor an address to show), so the card shrinks to one row and the choosing moves into a dialog.

| # | decision |
|---|---|
| S6b-1 | Card row: `[state icon] name [pin] [edit]`. Details only in the name's tooltip (stored key/address, sha256 short form, the variant/file used here, size, where). |
| S6b-2 | State icons: resolved `model_training` success green; resolved but not pinned `online_prediction` warning; missing `model_training` warning; no model `model_training` error. |
| S6b-3 | Name: catalog entry `name`; `hf://user/repo/file` → `repo`; otherwise the reference's `label` (file name); empty → "no model". Short; the tooltip carries the rest. Two catalog entries with the same `name` (the demo's 2x/4x "Compact Pretrain") are told apart only in the tooltip. |
| S6b-4 | Pin button on the card only when the reference is unpinned and its file is on this machine (digest known or hashable); one click = one undo step. |
| S6b-5 | Dialog: "Current" area on top (form, name, key/address copyable, sha256 or "not pinned", what it resolves to here, Clear) + four tabs — Catalog (port-`filter`ed entries by library, variant · state · size), Models Volume (files, picked by digest; hashed off the UI thread), Hugging Face (cached model files as `org/repo/path`), Address (`hf://` / `https://`; `hf://` asks the Hub for the digest). Every tab has a search field. |
| S6b-6 | Clicking a row only chooses (shown in Current); **Use** stores it and closes, **Cancel** drops it. Opens on the tab of the current reference (Catalog for none). |
| S6b-7 | **Use** pins a file reference whose digest is known at that moment (amends S6-Q12: no separate Pin step when the digest is known); an address whose file is not here yet is stored unpinned and pinned later from the card. |
| S6b-8 | The dialog never downloads (S6-Q17 kept); missing models are fetched in the Models editor. |

**Models editor (2026-11-01):** a "Show:" filter row like the marketplace's — toggles Catalog, Models, Huggingface and a search toggle (search narrows every section; hiding it clears it). Sections renamed: Local → Models, HF cache → Huggingface. The disk-usage line is gone: each section header counts what it lists as "N file(s), SIZE" ("Models — 2 files, 1.2 MB"), the tooltip gives the whole volume ("Hugging Face cache: 16.1 GB in all, shared with other tools"). The Needed section is always shown; Huggingface lists only files a catalog entry or an open graph uses (no Reveal location — the Volumes editor shows the cache's location).

The state icon is an indicator only (not clickable): a widget cannot reach its session to publish `Reveal` (the client→session map is private to `haywire_studio.app`), and the haystack notice already leads to the Models editor.

### 2.6 Torch install — haybale-marketplace (Q18B)
- Every `uv pip install` / dry-run passes `--torch-backend <setting>`; framework setting,
  default `auto`, overridable (`cpu`, `cu126`, …). Torch is an environment property, not a
  library one. Covers `git+URL` consumer installs.
- **S3 deviations (2026-11-01):** a `LibrarySettings` of haybale-marketplace (`MarketplaceSettings.torch_backend`, namespace `marketplace`, Barns panel at EDIT), not a haywire-core `FrameworkSettings` — follows NetworkSettings/ModelsSettings; `CHOICES` with 13 suggested backends plus any typed value (`SelectWidget` gained `new_value_mode`: copies its options, shows a non-option value as an extra option of that widget only; a bad value fails in uv's own message), blank reads as `auto`; passed on local editable installs too; uninstall gets none. `LibraryManager` takes a `torch_backend` callable, read per uv run. `uv sync` paths (update/rename) untouched.

### 2.7 Spandrel — existing `haybale-spandrel` project (Q19–Q23, Q33)
- Project scaffold `haybale-spandrel-dev` at `../haybale-spandrel`, barn member
  `barn/haybale-spandrel`; add `barn/haybale-spandrel-extra` (lockstep, ADR 0023).
- **Nodes (Q23B):** Load Model (model reference → `MODEL` + architecture/scale/channels/purpose
  outlets; `MODEL` is `store_strategy=NEVER`), Upscale Image (SR + 1x restoration; tiling
  `auto | none | N px` with auto from memory budget and `ModelTiling.INTERNAL` respected; custom
  scale; separate alpha; padding; polls `context.cancel` between tiles; reports progress), Inpaint
  (`IMAGE` + `IMAGE_GRAY` mask), Model Info.
- **Settings (Q22B):** LibrarySettings `device`, `precision` (`auto | fp32 | fp16 | bf16`),
  `memory_budget`; nodes may `shadow()` device/precision; `tile_size` per Upscale node.
  `precision=auto` resolves against `supports_half`/`supports_bfloat16` + device and defuses
  (fp32 + status note), never refuses.
- **Pool use (Q20B):** variant key `(device, dtype)`; release hook `del` + `torch.cuda.empty_cache()`.
  `on_reload = "restart"` (hot-reload drops the pool module).
- **Extra arches (Q19B, Q33A):** `haybale-spandrel-extra` registers `EXTRA_REGISTRY` on load,
  declares its non-commercial license; base stays MIT. A model that failed to detect before the
  extra library loaded retries via failed-stays-dirty.

**S7 deviations (landed 2026-11-03; details in the [S7 plan](2026-11-01-s7-spandrel-nodes.md)):**
- **Model kinds (ADR 0071).** `MODEL` became `MODEL_BASE` with kinds `IMAGE_MODEL` (SR, FaceSR,
  Restoration) and `INPAINT_MODEL`; Upscale Image takes the first, Inpaint the second, Model Info
  any. The loader node (labelled **Load Spandrel Model**, key unchanged) has a bare `ADD` outlet
  that takes the kind of the first inlet it is connected to, keeps it until reset, and only then
  shows its Model picker, filtered by the kind's `catalog_filter`. Load Model has no
  architecture/scale outlets: Model Info (labelled **Spandrel Model Info**) carries them.
- `on_reload = "none"` (not `restart`): the pool lives in haybale-models, which survives a
  spandrel reload; Load Model lets go of its hold in `on_teardown`.
- **`BaseNode.run_again()`** (S7-Q19): Load Model releases its pool hold in `on_shutdown` and runs
  again on the next run (ADR 0070 would keep the clean data node from re-running). The release hook
  only empties the CUDA/MPS cache; it no longer moves weights to the CPU.
- **MPS limit:** a convolution over ≥ 2³¹ elements fails on Apple GPUs; automatic tiles are capped
  so a tile's output stays below it, and `run_tiled` halves the tile and retries on that error as on
  out-of-memory. A custom scale above the model's runs the model again on a shrunk input, so no
  pass grows larger than the result.
- **No LaMa catalog entry:** no spandrel-loadable published file (HF TorchScript has a `model.` key
  prefix; the Lightning checkpoint is refused by spandrel's restricted unpickler). Inpaint is tested
  with a `LaMa(in_nc=4)` fixture; the live Inpaint check (step 7) is a **priority follow-up**.
- Catalog entries declare `purpose: ["SR"]`. The model picker and Models editor describe entries
  (scale, architecture, tags; description in the hover tip) and the picker's Models Volume tab leaves
  out catalog variants (haybale-models).
- Framework changes found on the way, each with its own commit: `shadow()` mirrors keep their
  source's widget, options and range; progress bars on Load/Save Image; `store=StoreStrategy.NEVER`
  settings; `UiState.HIDE_WIDGET`; a settings promotion channel; user-hidden ports; hover tips with
  data types; the edge rebuild after a port is retyped while linking; the node-title docs icon.
- The **Upscaler** macro (List Files → Loop Array → Load Image → Upscale Image → Save Image,
  skipping finished files) ships in haybale-spandrel's `macros/`.

---

## 3. Build order (Q36C)

| # | slice | where | needs | status |
|---|---|---|---|---|
| S0 | **spike:** IMAGE value class + accessors + benchmarks (camera frame u8 BGR → GPU fp16 → SR → display within 33 ms at 1080p) | haybale-image | — | done — gate met after tuning (778d98316, merged to master 2026-10-30) — plan removed after landing (git history) |
| S1 | PATH types, volumes (née anchors), resolver, volumes.toml, picker, Volumes editor, CLI | haywire-core builtin + haybale-studio + CLI | — | done (merged ff to master 17f31b352, 2026-10-30; plan removed after landing) |
| S1b | the volumes file is the volume list (S1b-Q1–Q9) | haywire-core builtin + haybale-studio + CLI | S1 | done (merged ff to master 17f31b352, 2026-10-30; plan removed after landing) |
| S2 | failure poisoning + failed-stays-dirty **+ benchmarks (§2.3)** | haywire-core VM | — | done (squashed on feat/s2-failure-poisoning, backup tag spandrel-s2-full, unmerged, 2026-10-30; reworked to bail-by-policy S2-Q10; live check passed) — [plan](2026-10-30-s2-failure-poisoning.md) |
| S4 | Run Button, For Each File, Path Exists?, Output Path | haybale-core | S1, S2 | done (merged ff to master 4add63fc2, 2026-10-31; live check passed; deferred minors listed in §2.2) — [plan](2026-10-30-s4-batch-nodes.md) |
| S5 | rest of haybale-image | haybale-image (+ Split Path, Create Folder in haybale-core) | S0, S1 | done (merged ff to master b2fbfb565, 2026-10-31; still render live-checked, rest listed in §2.4) — [plan](2026-10-31-s5-haybale-image.md) |
| S4b | List Files, Loop Array, Step Array | haybale-core | S4 | done (fcc03b7e2, merged with S5, 2026-10-31; slideshow live-checked) — decisions in §2.2 |
| S6 | haybale-models (+ graph notices in graph-editor/haystack, catalog registry in core) | haybale-models | S1 | done (merged ff to master 4f2ebd3b2, 2026-11-01; live check passed incl. the S6b model picker; follow-ups and deferred minors listed in §2.1 and §2.5) — [plan](2026-10-31-s6-haybale-models.md) |
| S3 | `--torch-backend` setting | haybale-marketplace | — | done (9d651f6b2 + widget 4dfdbd423 on master, 2026-11-01; live-checked; no slice plan — implemented inline; deviations in §2.6) |
| S7 | spandrel nodes + settings | haybale-spandrel | S3, S5, S6 | done (haywire-repo `feat/s7-spandrel` 9c2a6096b…, haybale-spandrel `feat/s7-spandrel` b5da8d9…cc6788c, merged ff to master 2026-11-03; live check passed incl. batch + Upscaler macro; Inpaint live check is a priority follow-up; deviations in §2.7) — [plan](2026-11-01-s7-spandrel-nodes.md) |
| S8 | extra arches | haybale-spandrel-extra | S7 | open |
| S9 | visiongraph frame adapters | haybale-visiongraph | S5 | open |

If S0 misses the realtime budget, revisit Q27 before S1.

**Status rule (applies to every slice plan).** Status values: `open` → `planned` (slice plan
written; link it in the row) → `done` (implemented, verified, merged). **The last task of every
slice plan is: update this table — set the slice's status to `done`, with the merge commit hash
and date, and note any deviation from this spec in the slice's section.** A slice plan without
that final task is incomplete.

---

## 4. Non-goals (Q35)
1. Implicit iteration / generators / collectors (explicit LOOPBACK only)
2. Video load/save, spritesheets, collectors beyond `ARRAY`
3. ONNX / NCNN / TensorRT, model conversion, model interpolation
4. Face restoration (facexlib) — first follow-up after haybale-models
5. Subscribable catalog feeds (OpenModelDB browsing in-studio)
6. LRU / VRAM-budget eviction of loaded models
7. GPU scheduling between execution groups
8. Migrating visiongraph onto IMAGE / haybale-models; renaming `RGB_FRAME`
9. HF tokens for gated repos (waits for the security document)
10. EXR / DDS / HDR / ICC conversion (passthrough only)
11. Training / fine-tuning

---

## 5. To land with the code (not edited inline)

### Glossary terms
- **Volume** — a named, per-machine root location (`project`, `home`, `models`, user-named).
- **Volume path** — a PATH value `(volume, relative)`; the only path form a graph stores.
- **Failed node** — a node whose last worker run raised; stays dirty, retried at next evaluation.
- **Blocked node** — a node skipped because a data-inlet source is failed or blocked.
- **Image layout** — channel arrangement (gray/RGB/RGBA), carried by the type.
- **Image storage** — dtype, channel order, residency; invisible to wires, reached via accessors.
- ~~**Model reference** — source URI + sha256 identifying a model file.~~ (landed in S6)
- ~~**Model catalog** — a library-declared list of model references with metadata.~~ (landed in S6)
- ~~**Model store** — the `models` volume's folders + digest index.~~ (landed in S6)
- ~~**Needs-list** — the set of model references a graph's nodes require, offered for fetch.~~ (landed in S6)
- ~~**Loaded model**, **Model kind**~~ (landed in S7)
- Flag: "Adapter" stays reserved for type-changing conversions; storage conversion is not one.

### ADR candidates
- ~~Model loaders live with their framework library; model kinds are types.~~ (landed in S7: ADR 0071)
1. Volumes: named per-machine locations; no absolute paths in graphs.
2. Failure poisoning + failed-stays-dirty (execution semantics change).
3. IMAGE: fixed semantics, free storage, accessor-only pixel access.
4. ~~Models identified by digest; HF cache used, never deleted.~~ (landed in S6: ADRs 0067, 0068)
5. Torch backend is an environment property passed on every install.

### `.insights/` traps
- Stale outlet after a data-node exception (until S2 lands).
- `RGB_FRAME` is BGR.
- `cv2` distribution clash (`opencv-python` vs `-contrib` vs `-headless`).

### Docs to add (facts found only in code)
- `docs/architecture/execution/virtual-machine` / `lazy-evaluation`: a failed data node leaves
  its previous outlet value and consumers still run (until S2; then document poisoning).
- visiongraph type docs: `RGB_FRAME` / `GRAY_FRAME` channel order is BGR (OpenCV-native).
- Error docs: `error_runtime` is sticky until revalidation, not cleared by a successful run.
