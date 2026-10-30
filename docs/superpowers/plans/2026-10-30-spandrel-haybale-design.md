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
- **Anchored path:** a PATH value is `(anchor, relative)` — anchor is its own field, never a
  parsed string prefix (no in-band sentinel).
- **Types:** base `PATH`; derived `FILE_PATH`, `FOLDER_PATH`. "Must exist" vs "write target" and
  extension filters are port/widget options, not types.
- **Anchors:** `project:` (derived from `workspace_root`, not editable), `home:`, plus
  library-contributed anchors (e.g. `models:` from haybale-models). Users add named anchors for
  outside folders (e.g. `scans:` → `/Volumes/Scans`).
- **No absolute anchor** (Q6C). Every graph stays portable by construction.
- **Locations** live in an `AnchorSettings` table at the **global (per-machine) tier**; editing
  it is ADMIN. Libraries that need env vars (`VISIONGRAPH_ASSET_DIR`, `HF_HOME`) set them *from*
  the anchor — the anchor is the single source.
- **Resolver** refuses a resolved path that escapes its anchor root (`..`, outward symlink),
  checked on the resolved path.
- **Undefined anchor** (Q7B): value kept verbatim; widget shows "anchor undefined"; node errors at
  run time via the ledger; ADMIN gets "define anchor…" on the widget.
- **Picker:** server-side filesystem browser (the browser cannot give server paths), rooted at
  anchors only; mode from the derived type (file / folder / save target). Reuse
  `LazyFileBrowserEditor`'s eager-then-lazy tree approach.

### 2.2 Batch nodes — haybale-core (Q8, Q11, Q12, Q31)
- **`Run Button`** — EVENT widget node; emits one Trigger; OPERATE tier.
- **`For Each File`** — LOOPBACK. Inputs: folder, glob (stdlib `pathlib` glob, `**` recursive),
  recursive, limit, `on_error = continue | stop`. Outlets: `loop_body`, path, relative subdir,
  stem, index, `failed` (list of paths), `completed`. Progress via ProgressSettings (index/total).
- **`Path Exists?`** — control branch (`exists` / `missing`) on any `PATH`.
- **`Output Path`** — data node: `anchor-folder / relative-subdir / stem + suffix . ext`. The
  single home of "mirror the input subfolder structure".
- Resume pattern: `For Each → Path Exists? →(missing)→ Save`. Upscale is a DATA node pulled only
  by Save's localized data flow, so an `exists` branch never runs it. Save keeps
  `if_exists = overwrite | skip | unique-suffix` as a safety net.
- Ship the full pattern as a **macro** ("Batch Upscale Folder") once spandrel lands.

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
- **Store (Q16B):** `models:` anchor (contributed by this library, Q17C) = human folders
  (`models:/openmodeldb/4x-UltraSharp.pth`, user subfolders allowed) + `models:/.index.json`
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
| S0 | **spike:** IMAGE value class + accessors + benchmarks (camera frame u8 BGR → GPU fp16 → SR → display within 33 ms at 1080p) | haybale-image | — | done — gate met after tuning (778d98316, merged to master 2026-10-30) — [plan](2026-10-30-s0-image-value-spike.md) |
| S1 | PATH types, volumes (née anchors), resolver, volumes.toml, picker, Volumes editor, CLI | haywire-core builtin + haybale-studio + CLI | — | planned — [plan](2026-10-30-s1-volumes.md) |
| S2 | failure poisoning + failed-stays-dirty **+ benchmarks (§2.3)** | haywire-core VM | — | open |
| S4 | Run Button, For Each File, Path Exists?, Output Path | haybale-core | S1, S2 | open |
| S5 | rest of haybale-image | haybale-image | S0, S1 | open |
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
- **Anchor** — a named, per-machine root location (`project:`, `home:`, `models:`, user-named).
- **Anchored path** — a PATH value `(anchor, relative)`; the only path form a graph stores.
- **Failed node** — a node whose last worker run raised; stays dirty, retried at next evaluation.
- **Blocked node** — a node skipped because a data-inlet source is failed or blocked.
- **Image layout** — channel arrangement (gray/RGB/RGBA), carried by the type.
- **Image storage** — dtype, channel order, residency; invisible to wires, reached via accessors.
- **Model reference** — source URI + sha256 identifying a model file.
- **Model catalog** — a library-declared list of model references with metadata.
- **Model store** — the `models:` anchor's folders + digest index.
- **Needs-list** — the set of model references a graph's nodes require, offered for fetch.
- Flag: "Adapter" stays reserved for type-changing conversions; storage conversion is not one.

### ADR candidates
1. Anchored paths; no absolute anchor.
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
