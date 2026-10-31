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
  (`VISIONGRAPH_ASSET_DIR`, `HF_HOME`) set them *from* the volume — the volume is the single source.
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

### 2.5 Models — new `haybale-models` (monorepo `barn/`) (Q13–Q17, Q21, Q34)
- **Model reference (Q13B):** source URI (`hf://org/repo/path@rev`, `https://…`, or local) +
  sha256. Plain local paths allowed. Graph stores the reference → runnable on a fresh machine.
- **Model catalog (Q14D):** a component kind libraries register (entries = reference + metadata
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

### 2.6 Torch install — haybale-marketplace (Q18B)
- Every `uv pip install` / dry-run passes `--torch-backend <setting>`; framework setting,
  default `auto`, overridable (`cpu`, `cu126`, …). Torch is an environment property, not a
  library one. Covers `git+URL` consumer installs.

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

---

## 3. Build order (Q36C)

| # | slice | where | needs | status |
|---|---|---|---|---|
| S0 | **spike:** IMAGE value class + accessors + benchmarks (camera frame u8 BGR → GPU fp16 → SR → display within 33 ms at 1080p) | haybale-image | — | done — gate met after tuning (778d98316, merged to master 2026-10-30) — plan removed after landing (git history) |
| S1 | PATH types, volumes (née anchors), resolver, volumes.toml, picker, Volumes editor, CLI | haywire-core builtin + haybale-studio + CLI | — | done (merged ff to master 17f31b352, 2026-10-30; plan removed after landing) |
| S1b | the volumes file is the volume list (S1b-Q1–Q9) | haywire-core builtin + haybale-studio + CLI | S1 | done (merged ff to master 17f31b352, 2026-10-30; plan removed after landing) |
| S2 | failure poisoning + failed-stays-dirty **+ benchmarks (§2.3)** | haywire-core VM | — | done (squashed on feat/s2-failure-poisoning, backup tag spandrel-s2-full, unmerged, 2026-10-30; reworked to bail-by-policy S2-Q10; live check passed) — [plan](2026-10-30-s2-failure-poisoning.md) |
| S4 | Run Button, For Each File, Path Exists?, Output Path | haybale-core | S1, S2 | done (merged ff to master 4add63fc2, 2026-10-31; live check passed; deferred minors listed in §2.2) — [plan](2026-10-30-s4-batch-nodes.md) |
| S5 | rest of haybale-image | haybale-image (+ Split Path, Create Folder in haybale-core) | S0, S1 | planned — [plan](2026-10-31-s5-haybale-image.md) |
| S6 | haybale-models | haybale-models | S1 | open |
| S3 | `--torch-backend` setting | haybale-marketplace | — | open |
| S7 | spandrel nodes + settings | haybale-spandrel | S3, S5, S6 | open |
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
- **Model reference** — source URI + sha256 identifying a model file.
- **Model catalog** — a library-declared list of model references with metadata.
- **Model store** — the `models` volume's folders + digest index.
- **Needs-list** — the set of model references a graph's nodes require, offered for fetch.
- Flag: "Adapter" stays reserved for type-changing conversions; storage conversion is not one.

### ADR candidates
1. Volumes: named per-machine locations; no absolute paths in graphs.
2. Failure poisoning + failed-stays-dirty (execution semantics change).
3. IMAGE: fixed semantics, free storage, accessor-only pixel access.
4. Models identified by digest; HF cache used, never deleted.
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
