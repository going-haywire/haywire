# S7 — spandrel nodes + settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (chosen: inline, S7-Q18B). Steps use checkbox (`- [ ]`) syntax for tracking. **Never commit without the user's explicit consent** — "Commit" steps mean "stage and ask".

**Goal:** Load spandrel image models from haybale-models references and run them as haywire nodes (Load Model, Upscale Image, Inpaint, Model Info), with library settings for device, precision and memory budget, a small catalog and a "Batch Upscale Folder" macro.

**Architecture:** Torch/spandrel logic lives in a node-free `runtime/` package (device/dtype resolution, loading, tiling, upscale, inpaint) that tests drive directly; nodes are thin. Load Model is the pool holder (`haybale_models.consumer.acquire_port`) and puts a `SpandrelModel` (descriptor already on device/dtype + a per-model lock) on a `MODEL` wire; consumers run it.

**Tech Stack:** spandrel ≥ 0.4.2, torch (installed via `--torch-backend`), haybale-image `ImageValue`, haybale-models consumer/pool/catalog, haywire node/settings/panel APIs.

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.7 (design), §3 (status). The S7 decisions below amend it.

## S7 decisions (inquisition 2026-11-01)

| # | decision |
|---|---|
| S7-Q1 | Code + tests in the external project `../haybale-spandrel` (barn member `barn/haybale-spandrel`, tests in `../haybale-spandrel/tests/`, own `conftest.py` like visiongraph). Editable sources for haybale-image / haybale-models. Studio use: `uv pip install -e ../haybale-spandrel/barn/haybale-spandrel` into haywire-repo `.venv`. |
| S7-Q2 | **Load Model is the pool holder**: it resolves device + precision (library settings, `shadow()`-able on the node), acquires `(sha256, (device, dtype))` from the haybale-models pool, outputs `MODEL` = descriptor already on device/dtype. Consumers have no device/precision. |
| S7-Q2b | Loaders live with the framework library; haybale-models owns files + pool; no loader registry. **ADR** (lands with the code). |
| S7-Q3 | `precision=auto`: cuda → fp16 if `supports_half`, else bf16 if `supports_bfloat16` and `torch.cuda.is_bf16_supported()`, else fp32; mps → fp16 if `supports_half`, else fp32; cpu → fp32. Explicit unsupported choice → fp32 + card note. |
| S7-Q4 | `device`: `CHOICES` + typed values (`auto`, `cpu`, `mps`, `cuda`, `cuda:0`, `cuda:1`; `new_value_mode: add-unique`). `auto` = cuda → mps → cpu. Unavailable → cpu + card note. |
| S7-Q5 | Tiling `auto`: estimate from `memory_budget`; `size_requirements` honoured; OOM → halve + retry down to the floor; 16 px overlap; `INTERNAL` never tiles; `DISCOURAGED` → auto = none (explicit N still tiles). |
| S7-Q6 | `scale` inlet (float, `0` = native): repeat passes until ≥ target, then on-device antialiased downscale to the exact size. |
| S7-Q7 | `alpha = resize | model`, default `resize` (bicubic); 4-channel models get RGBA directly. |
| S7-Q8 | Layout mismatch adapted in; output keeps the input's layout; RGB into a 1-ch model → gray out + note. Outlet type `IMAGE`. |
| S7-Q9 | Inpaint: whole image, padded to `size_requirements`, cropped back; mask `IMAGE_GRAY`, > 0.5 = fill, nearest-resized to the image; alpha passes through; wrong purpose → error. |
| S7-Q10 | Load Model outputs `MODEL` only (+ card status line); Model Info carries every fact (amends Q23B). |
| S7-Q11 | Small permissive catalog copied byte-identical from OpenModelDB (licences checked; NC excluded). |
| S7-Q12 | "Batch Upscale Folder" macro: loop body with exec in/out; exposed input folder, output folder, pattern, model (`MODEL_REF`), scale; Load Model inside. Run Button + Tick Event stay outside (ADR 0041: no EVENT node in a Subgraph). |
| S7-Q13 | `on_reload = "none"` (amends Q20B); a test proves a reload leaves no pool hold by a dead node. |
| S7-Q14 | Tests use tiny random-weight models generated in fixtures; GPU variants `skipif`. |
| S7-Q15 | Upscale output stays a tensor-backed `ImageValue` on the device. |
| S7-Q16 | A lock per loaded model; each tile's forward pass runs under it. |
| S7-Q17 | Out of scope: S8 extra arches, S9 visiongraph adapters, face restore, ONNX, eviction, GPU scheduling, multi-image batches, HDR (outputs clamped to [0,1]), Resize node, Inpaint `max_size`. |
| S7-Q18 | Inline execution; commits only with consent. |

## Global Constraints

- Python ≥ 3.12; `spandrel>=0.4.2`; torch never imported at module level outside `runtime/` (library import must not fail before torch is needed → import lazily inside `runtime` functions or guard with a clear error naming `--torch-backend`).
- No relative imports under `barn/` (ruff TID252).
- Displayed docstrings (node/type/panel class docstrings) are Markdown in UI words; all others reST (`.claude/rules/python-docs.md`).
- UI follows `docs/reference/design-guide.md`; panels follow `ModelsSettingsPanel`.
- "Defuse, don't refuse": unsupported precision/device fall back and say so on the card (`NodeWarning`, kind `"spandrel"`).
- Glossary terms and ADRs are collected below and land with the code (not edited inline mid-session).
- Tests: `cd ../haybale-spandrel && uv run pytest tests/` ; torch-on-CPU always; MPS/CUDA tests `skipif` unavailable; the LaMa fixture (≈200 MB, 51 M params) is session-scoped and its tests marked `slow`.

## Review Focus

1. **Image smaller than one tile / smaller than `size_requirements.minimum`** — runs untiled, padded to the minimum, cropped back to exact `w*scale × h*scale`. Test in Task 4.
2. **Tile seams** — tiled output equals untiled output within 1e-3 (fp32, CPU) for a Compact model; odd sizes (e.g. 37×53, tile 16). Test in Task 4.
3. **Cancel mid-image** — `context.cancel` set between tiles stops the run with no outlet write and no partial image. Test in Task 4 (runtime) + Task 6 (node).
4. **Ref changes while held** — changing Load Model's reference releases the old pool hold (pool entry count back to 0 for the old key). Test in Task 5.
5. **Empty / 0×0 image into Upscale or Inpaint** — node error "empty image", not a torch shape error. Test in Task 6/7.

---

## File Structure

All paths below are under `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-spandrel/` unless prefixed `haywire-repo:`.

```
pyproject.toml                                   (sources: haybale-image, haybale-models, haybale-graph-editor; pytest config)
tests/conftest.py                                library_system + models_env + tiny model fixtures
barn/haybale-spandrel/pyproject.toml             deps
barn/haybale-spandrel/haybale_spandrel/
  haybale.toml                                   label/description/tags, on_reload="none", linked_libraries
  __init__.py                                    register: settings, types, nodes, panels, macros, catalog
  settings/spandrel_settings.py                  SpandrelSettings
  panels/spandrel_settings_panel.py              Barns panel
  types/model.py                                 MODEL type (store NEVER)
  value/spandrel_model.py                        SpandrelModel value
  runtime/__init__.py
  runtime/devices.py                             resolve_device, resolve_dtype, memory_budget_bytes
  runtime/loader.py                              load_model, release_model
  runtime/tiling.py                              choose_tile, run_tiled
  runtime/upscale.py                             upscale_image
  runtime/inpaint.py                             inpaint_image
  nodes/load_model.py | upscale_image.py | inpaint.py | model_info.py
  catalog/*.json
  macros/BatchUpscaleFolder.hwm
```

---

### Task 1: Project wiring + settings + panel

**Files:**
- Modify: `pyproject.toml`, `barn/haybale-spandrel/pyproject.toml`, `barn/haybale-spandrel/haybale_spandrel/haybale.toml`, `barn/haybale-spandrel/haybale_spandrel/__init__.py`
- Delete (scaffold, unused): `skins/`, `themes/`, `adapters/`, `editors/`, `widgets/`, `states/` folders + their registrations
- Create: `settings/spandrel_settings.py`, `panels/spandrel_settings_panel.py`, `tests/conftest.py`, `tests/test_library.py`

**Interfaces:**
- Produces: `SpandrelSettings` (namespace `"spandrel"`, label `"Spandrel"`): `device = setting[CHOICES]("auto", options DEVICES, new_value_mode "add-unique")`, `precision = setting[CHOICES]("auto", options ("auto","fp32","fp16","bf16"))`, `memory_budget = setting[FLOAT](0.0, min=0, label="Memory budget (GB)", description="0 = derive from the device")`. `DEVICES = ("auto","cpu","mps","cuda","cuda:0","cuda:1")`.
- Produces: `tests/conftest.py` fixtures `library_system` (session; loads haywire-repo libraries haybale-core, haybale-image, haybale-models, haybale-graph-editor plus this barn — follow visiongraph's conftest, adding the monorepo barn dirs to `library_paths` if entry-point discovery does not load them), `models_env` (copy of haywire-repo `tests/models/conftest.py` fixture + its HOME redirect), `graph` (a graph on that library system with a `SyncScheduler`).

- [x] **Step 1:** Commit the pending scaffold rename (hay-spandrel → haybale-spandrel) — ask consent first.
- [x] **Step 2:** `barn/haybale-spandrel/pyproject.toml` deps: `haywire-core>=0.3.0`, `haybale-image`, `haybale-models`, `haybale-core`, `spandrel>=0.4.2`, `torch`. Root `pyproject.toml`: add editable `[tool.uv.sources]` for `haybale-image`, `haybale-models`, `haybale-graph-editor` (haywire-repo paths, same style as the existing ones); add `[tool.pytest.ini_options]` with markers `slow`, `integration`. `uv sync` in the project.
- [x] **Step 3:** haybale.toml: `label = "Spandrel"`, description `"Upscale and restore images with PyTorch models (spandrel)"`, tags `["image","models","upscale","torch"]`, `on_reload = "none"`, `linked_libraries = ["haybale_models", "haybale_image"]`.
- [x] **Step 4: Failing test** `tests/test_library.py::test_library_registers_settings_and_panel` — library loads; `SpandrelSettings` reachable from the settings registry with defaults `device=="auto"`, `precision=="auto"`, `memory_budget==0.0`; the panel class is registered on `Barns`.
- [x] **Step 5:** Implement settings + panel (copy `ModelsSettingsPanel` shape; label "Spandrel", description "Device, precision and memory budget for spandrel models.", icon from `hui.icon` — pick an existing one, e.g. `hui.icon.models`, order 20).
- [x] **Step 6:** `uv run pytest tests/test_library.py` → PASS; `uv run ruff check . && uv run ruff format --check .`
- [x] **Step 7: Commit** (consent): `feat(spandrel): library wiring, settings and Barns panel`

### Task 2: Device + precision resolution, loader, MODEL type

**Files:**
- Create: `runtime/devices.py`, `runtime/loader.py`, `value/spandrel_model.py`, `types/model.py`
- Test: `tests/test_devices.py`, `tests/test_loader.py`, fixtures in `tests/conftest.py`

**Interfaces:**
- Produces:
  - `resolve_device(name: str) -> tuple[torch.device, str | None]` — note when falling back (`"cuda:1 not available — running on cpu"`).
  - `resolve_dtype(precision: str, device: torch.device, *, supports_half: bool, supports_bfloat16: bool) -> tuple[torch.dtype, str | None]` — rules S7-Q3; note e.g. `"fp16 not supported by this model — running fp32"`.
  - `memory_budget_bytes(device: torch.device, setting_gb: float) -> int` — `setting_gb > 0` → that; else cuda `torch.cuda.mem_get_info(device)[0] * 0.8`, mps `torch.mps.recommended_max_memory() * 0.5`, cpu `4 GiB`.
  - `load_model(path: Path, device: torch.device, precision: str) -> SpandrelModel` — `spandrel.ModelLoader(device="cpu").load_from_file(path)`, `.eval()`, resolve dtype from the descriptor, `.to(device)`, then `.half()`/`.bfloat16()`; raises `UnsupportedModelError` through unchanged (message names the file).
  - `release_model(model: SpandrelModel) -> None` — drops the descriptor, then `torch.cuda.empty_cache()` / `torch.mps.empty_cache()` for the model's device type.
  - `@dataclass(frozen=True, eq=False) SpandrelModel`: `descriptor: ImageModelDescriptor | MaskedImageModelDescriptor`, `device: torch.device`, `dtype: torch.dtype`, `name: str` (file stem), `notes: tuple[str, ...]`, `lock: threading.Lock = field(default_factory=threading.Lock)`; properties `architecture`, `purpose`, `scale`, `input_channels`, `output_channels`, `tiling`, `size_requirements`, `is_inpaint`; `status() -> str` → `"ESRGAN · 4x · RGB · mps fp16"` (channels as GRAY/RGB/RGBA).
  - `MODEL` type: `PrimitiveType[SpandrelModel | None]`, `store_strategy=StoreStrategy.NEVER`, default `{"value": None}`, `to_dict` → `{"value": None}`, colour distinct from MODEL_REF (`#d97ab0`), label `"Loaded model"`, description `"A model loaded on a device, ready to run. Never saved with the graph."`.
- Fixtures: `tiny_sr_path(tmp_path_factory)` session — `Compact(num_feat=8, num_conv=2, upscale=2)` saved `.safetensors`; `tiny_sr4_path` (upscale=4, `.pth` via `torch.save(state_dict)`); `tiny_1x_path` (upscale=1); `tiny_gray_path` (`num_in_ch=1, num_out_ch=1`); `lama_path` (session, `LaMa()` random, `.safetensors`). Seed `torch.manual_seed(0)`.

- [x] **Step 1: Failing tests** `test_devices.py`: auto on a machine without cuda/mps → cpu (monkeypatch `torch.cuda.is_available`/`torch.backends.mps.is_available` False); `"cuda:1"` unavailable → cpu + note; precision table: (cpu, auto) → fp32 no note; (mps, auto, half) → fp16; (mps, auto, no half) → fp32 no note; (cuda, auto, no half, bf16, bf16-capable) → bf16; (cpu, "fp16", half) → fp16 (explicit honoured); (any, "bf16", no bf16) → fp32 + note; budget: setting 2.0 → 2 GiB; cpu 0 → 4 GiB.
- [x] **Step 2:** Run → FAIL. **Step 3:** implement `devices.py`.
- [x] **Step 4: Failing tests** `test_loader.py`: `load_model(tiny_sr_path, cpu, "auto")` → scale 2, dtype float32, purpose `"SR"`, `status()` contains `"2x"` and `"cpu fp32"`; `.pth` loads too; garbage file → `spandrel.UnsupportedModelError`; `release_model` runs without error; `MODEL` round-trip `to_dict()` → `{"value": None}`.
- [x] **Step 5:** Implement loader, value, type. **Step 6:** tests PASS; ruff; mypy on the package.
- [x] **Step 7: Commit** (consent): `feat(spandrel): device/precision resolution, loader and MODEL type`

### Task 3: Tiling

**Files:** Create `runtime/tiling.py`; Test `tests/test_tiling.py`

**Interfaces:**
- Produces:
  - `OVERLAP = 16`; `MIN_TILE = 64`; `BYTES_PER_PIXEL_FACTOR = 64` (coarse per-arch constant; tunable).
  - `choose_tile(model: SpandrelModel, width: int, height: int, *, tile_setting: int | None, budget_bytes: int) -> int | None` — `None` = whole image. `tile_setting`: `None` = auto, `0` = none, `N` = N px. Auto: `INTERNAL` or `DISCOURAGED` → `None`; else side = `floor(sqrt(budget / (element_size * (in_ch + out_ch*scale²) * FACTOR)))`, rounded down to `multiple_of`, ≥ max(`MIN_TILE`, `minimum`); `None` if side ≥ max(width, height). `INTERNAL` → `None` even for explicit N.
  - `run_tiled(forward: Callable[[Tensor], Tensor], image: Tensor, *, scale: int, tile: int | None, requirements: SizeRequirements, cancel: threading.Event | None, on_tile: Callable[[int, int], None] | None) -> Tensor` — input `1×C×H×W`; pads each tile (and the untiled image) with reflect padding to satisfy `requirements` (`requirements.get_padding(w, h)`), crops the output back; tiles overlap `OVERLAP` and are blended with a linear ramp; raises `Cancelled` (own exception, defined here) when `cancel` is set between tiles; on `torch.OutOfMemoryError` halves `tile` (from whole image: start at 512) and retries the whole image, raises after `tile < MIN_TILE`. `on_tile(done, total)`.

- [x] **Step 1: Failing tests:** auto for a small image → `None`; huge image with 1 GiB budget → an int that is a multiple of `multiple_of` and ≥ `MIN_TILE`; DISCOURAGED auto → None but explicit 128 → 128; INTERNAL explicit → None; `run_tiled` with `forward = lambda t: F.interpolate(t, scale_factor=2, mode="nearest")` on 37×53 with tile 16 equals untiled (exact); with the tiny Compact on CPU fp32 tiled vs untiled `allclose(atol=1e-3)` (Review Focus 2); padding: requirements `multiple_of=8`, image 37×53 → output 74×106; image smaller than `minimum=64` → output exact size (RF 1); cancel set after first tile → `Cancelled`, `on_tile` called once (RF 3); OOM: forward raising `torch.OutOfMemoryError` when input side > 32 → result produced, final tile ≤ 32.
- [x] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS + ruff/mypy.
- [x] **Step 5: Commit** (consent): `feat(spandrel): tile size estimate and tiled execution`

### Task 4: Upscale + inpaint runtime

**Files:** Create `runtime/upscale.py`, `runtime/inpaint.py`; Test `tests/test_upscale_runtime.py`, `tests/test_inpaint_runtime.py`

**Interfaces:**
- Consumes: `SpandrelModel`, `choose_tile`, `run_tiled`, `Cancelled`, `ImageValue.tensor(device, dtype)`, `ImageValue.from_tensor`.
- Produces:
  - `upscale_image(image: ImageValue, model: SpandrelModel, *, scale: float = 0.0, tile_setting: int | None = None, alpha: str = "resize", budget_bytes: int, cancel=None, on_progress: Callable[[int, int], None] | None = None) -> tuple[ImageValue, list[str]]` — returns the image and notes. Steps: layout adapt (S7-Q8: gray→3ch replicate / RGB→1ch luma, note `"model is grayscale"`), alpha (S7-Q7; 4-ch models take RGBA), passes = smallest n with `native**n ≥ target` (target `0` → native, one pass), each forward under `model.lock`, final `F.interpolate(mode="bicubic", antialias=True)` to `round(w*target) × round(h*target)` when not exact, clamp [0,1], convert back to the input layout, `ImageValue.from_tensor(out, source_depth=image.source_depth)` then `image.derive(...)` for metadata. Raises `ValueError("empty image")` for an empty input; raises `ValueError` naming the purpose for an inpaint model.
  - `inpaint_image(image: ImageValue, mask: ImageValue, model: SpandrelModel, *, cancel=None) -> ImageValue` — requires `model.is_inpaint` else `ValueError("… is a SR model, not an inpainting model")`; mask resized nearest to the image, thresholded > 0.5; pad to requirements, run once under the lock, crop; alpha of an RGBA image passes through; gray image → replicate in, luma out.

- [x] **Step 1: Failing tests (upscale, tiny models, CPU):** RGB 20×30 with 2x → 40×60 RGB, residency tensor; scale 3 with 2x model → 2 passes then 60×90; scale 1.5 → 30×45; RGBA alpha=resize → RGBA 40×60, alpha equals bicubic of the input alpha; alpha=model → RGBA, called forward twice (spy); gray into RGB model → GRAY out; RGB into `tiny_gray` → GRAY + note; source_depth 16 carried; empty image → `ValueError("empty image")` (RF 5); lama model on upscale → `ValueError` naming inpainting; lock held during forward (spy forward asserts `model.lock.locked()`).
- [x] **Step 2: Failing tests (inpaint, `slow`, lama fixture):** 64×48 RGB + mask → same size RGB; mask 32×24 resized; RGBA alpha unchanged; SR model → `ValueError`.
- [x] **Step 3:** FAIL. **Step 4:** implement. **Step 5:** PASS (`-m "slow or not slow"`), ruff/mypy.
- [x] **Step 6: Commit** (consent): `feat(spandrel): upscale and inpaint runtime`

### Task 5: Load Model + Model Info nodes

**Files:** Create `nodes/load_model.py`, `nodes/model_info.py`; Test `tests/test_load_model.py`, `tests/test_model_info.py`

**Interfaces:**
- Consumes: `haybale_models.consumer.acquire_port`, `release_node`, `resolve_port`; `load_model`, `release_model`, `resolve_device`, `SpandrelSettings`.
- Produces:
  - `LoadModelNode` (`label="Load Model"`, menu `"models/spandrel"`, `NodeType.DATA`): inlet `model` (`MODEL_REF`, `prefer=[{"type": "safetensors"}, {}]`), outlet `loaded` (`MODEL`, label "Model"); `settings = bag(LoadModelSettings)` where `LoadModelSettings(NodeSettings)` has `device = shadow(SpandrelSettings.device)`, `precision = shadow(SpandrelSettings.precision)`. Worker: resolve device, `acquire_port(self, "model", variant_key=(str(device), precision_setting), load=lambda r: load_model(r.path, device, precision), release=release_model)`; before acquiring, `release_node(self)` when the resolved key changed since the last run (RF 4); `replace_warnings("spandrel", notes)` with device + dtype notes; outputs the `SpandrelModel`; card status = `model.status()` (shown as an info `NodeWarning`? — use the existing card-subtitle mechanism if one exists, else a `NodeWarning(kind="spandrel-status")`; check the node API before choosing and record the choice as a deviation). `on_shutdown` and `on_teardown` → `release_node(self)`.
  - Pool variant key uses the **requested** precision string, not the resolved dtype (resolving needs the loaded descriptor); two holders with the same request share one load.
  - `ModelInfoNode` (`"Model Info"`, DATA): inlet `model` (`MODEL`); outlets `architecture` STRING, `purpose` STRING, `scale` INT, `input_channels` INT, `output_channels` INT, `tiling` STRING, `supports_fp16` BOOL, `supports_bf16` BOOL, `min_size` INT, `multiple_of` INT, `device` STRING, `precision` STRING (`fp32/fp16/bf16`), `parameters` INT. Empty (`None`) model → node error "no model".

- [x] **Step 1: Failing tests** (integration, real graph run like haywire-repo `tests/models/test_resolve_model_run.py`; model file placed in `models_env`'s Models volume and indexed): Load Model → Model Info, run → `scale == 2`, `device == "cpu"`, `precision == "fp32"`; two Load Model nodes with the same ref → one pool entry with 2 holders; deleting one → 1 holder; changing the ref → old key gone (RF 4); missing ref → node error + "Model missing" warning; `device="cuda:1"` shadow on a CPU machine → cpu + warning text contains "not available"; shutdown → pool empty; **reload** of haybale_spandrel (library registry reload as in haywire-repo reload tests) → pool empty, the reloaded node loads again (S7-Q13).
- [x] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS + ruff/mypy.
- [x] **Step 5: Commit** (consent): `feat(spandrel): Load Model and Model Info nodes`

### Task 6: Upscale Image node

**Files:** Create `nodes/upscale_image.py`; Test `tests/test_upscale_image_node.py`

**Interfaces:**
- Consumes: `upscale_image`, `choose_tile`, `memory_budget_bytes`, `Cancelled`, `ProgressSettings`/`progress_field`.
- Produces: `UpscaleImageNode` (`"Upscale Image"`, menu `"image/models"`, DATA): inlets `image` (IMAGE), `model` (MODEL), `scale` (FLOAT, default 0.0, label "Scale", description "0 = the model's own scale"); config `tile_size` (STRING select `auto | none | 128 | 256 | 512 | 1024`, typed values allowed, label "Tile size"), config `alpha` (STRING select `resize | model`); outlet `image` (IMAGE). `progress = bag(UpscaleProgress)` with `main = progress_field("Tiles")`. Worker: parse tile setting (`auto`→None, `none`→0, digits→int, else node error naming the value), call runtime with `cancel=context.cancel`, `on_progress` → progress bar; `Cancelled` → return without writing the outlet; notes → `replace_warnings("spandrel", ...)`.

- [x] **Step 1: Failing tests** (graph run: Load Model + an image source → Upscale → recorder): 20×30 RGB → 40×60; `scale=3` → 60×90; `tile_size="16"` equals `"none"` within 1e-3; `tile_size="banana"` → node error naming it; empty image → node error "empty image" (RF 5); cancel event set from `on_progress` after tile 1 → outlet not written (RF 3).
- [x] **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS + ruff/mypy.
- [x] **Step 5: Commit** (consent): `feat(spandrel): Upscale Image node`

### Task 7: Inpaint node

**Files:** Create `nodes/inpaint.py`; Test `tests/test_inpaint_node.py` (`slow`)

**Interfaces:** `InpaintNode` (`"Inpaint"`, menu `"image/models"`, DATA): inlets `image` (IMAGE), `mask` (IMAGE_GRAY, description "White marks what to fill"), `model` (MODEL); outlet `image` (IMAGE). Errors: empty image, SR model.

- [x] **Step 1: Failing tests:** lama graph run → same size; SR model wired → node error naming inpainting.
- [x] **Step 2–4:** FAIL → implement → PASS + ruff/mypy.
- [x] **Step 5: Commit** (consent): `feat(spandrel): Inpaint node`

### Task 8: Catalog

**Files:** Create `catalog/*.json`, `catalog/README.md`; modify `__init__.py` (register `CatalogRegistry` on `catalog/`); Test `tests/test_catalog.py`

- [x] **Step 1:** Fetch candidate entries from the OpenModelDB data repo (`data/models/*.json`): RealESRGAN x4plus, RealESRGAN x2plus, RealESRGAN AnimeVideo v3 / a compact general model, LaMa (if listed; else an `hf://` entry with sha256 from the Hub). Keep only entries whose `license` is permissive (MIT, BSD, Apache, WTFPL, CC0, CC-BY); copy bytes unchanged; README states source repo + commit.
- [x] **Step 2: Failing test:** every entry registers under `haybale-spandrel:catalog:<stem>`, has a `pytorch` resource with sha256; licences in an allow-list.
- [x] **Step 3:** implement registration. **Step 4:** PASS.
- [x] **Step 5: Commit** (consent): `feat(spandrel): model catalog`

### Task 9: Docs, install, live check, macro

**Files:** generated docs (`haywire docs`), `README.md`, `macros/BatchUpscaleFolder.hwm`

- [x] **Step 1:** `uv run haywire docs barn/haybale-spandrel` in the project; review README/OVERVIEW/QUICKREF.
- [x] **Step 2:** Install into haywire-repo `.venv`: `uv pip install -e ../haybale-spandrel/barn/haybale-spandrel` (then `python -c "import cv2; print(cv2.__version__)"` — reinstall `opencv-contrib-python==5.0.0.93` if it flipped).
- [x] **Step 3: Live check** (studio): Fetch a catalog model; Load Image → Upscale → View Image (still); tile size auto on a large photo (progress bar moves; cancel via Stop); fp16 on mps shown on the card; RGBA alpha both modes; Inpaint with a painted mask; Model Info; reload the library while a graph holds a model. *(Done except Inpaint — see the priority follow-up below.)*
- [x] **Step 4:** *(Built by the user as `macros/Upscaler.hwm`, List Files + Loop Array based, live-run.)* Build the macro in the studio: `For Each File → Output Path → Path Exists? (missing) → Load Image → Upscale Image → Save Image`, Load Model inside; group, expose exec in/out, input folder, output folder, pattern, `MODEL_REF`, scale; Save as macro into `macros/`. Description names Run Button + Tick Event wiring. Live-run it on a folder of 3 images.
- [x] **Step 5: Commit** (consent): `feat(spandrel): Batch Upscale Folder macro and docs`

### Task 10: Land in haywire-repo

**Files:** haywire-repo: `docs/adr/00NN-loaders-live-with-the-framework-library.md`, `docs/reference/glossary.md`, spec §2.7 + §3, `.insights/` + CLAUDE.md if a trap was found, memory.

- [x] **Step 1:** ADR (S7-Q2b): "A model loader lives with its framework library; haybale-models owns files and the pool".
- [x] **Step 2:** Glossary: **Loaded model** (a model on a device in a precision, held by a Load Model node; never saved); **Tile size** only if the UI term needs it.
- [x] **Step 3:** Spec §3 row S7 → `done` with commit hashes + date; §2.7 "S7 deviations" list; amend Q20B/Q23B notes.
- [x] **Step 4:** Full haywire-repo gate unaffected: `uv run pytest -m "not browser and not perf" -n 4 -q` (only docs changed — run if anything outside docs changed).
- [x] **Step 5: Commit** (consent): `docs(spandrel): S7 done — ADR, glossary, spec status`

---

## Progress and deviations (2026-11-02)

Tasks 1–8 done, Task 9 steps 1–2 done (docs generated, installed into haywire-repo `.venv`); live check + macro (Task 9 steps 3–4) and Task 10 open. Nothing committed yet. `../haybale-spandrel` tests: 80 pass (incl. `slow`); ruff + mypy clean. Monorepo gate: 8790 passed after the classification-test fix below.

- **S7-Q19 (new, user decision): `BaseNode.run_again()`** in haywire-core. Load Model releases its pool hold in `on_shutdown` and calls `run_again()`, so the next run loads again (ADR 0070 would otherwise keep the clean data node from re-running and hand on a released model). Test in `tests/core/test_execution/test_data_node_first_run.py`. Mention in node-canon's "loaded models" row (Task 10).
- Spandrel's descriptor already pads inputs to `size_requirements`, crops and clamps to [0,1]; `run_tiled` does no padding of its own and takes no `requirements` argument.
- Feather blending gives the outer half of each 16 px margin weight 0 (pixels within the model's reach of the cut edge); tiled = whole within 1e-3 on Compact.
- OOM retry starts from half the image's longer side (not 512); floor `MIN_TILE = 32` (also the auto floor).
- spandrel outputs inference tensors: runtime work runs under `torch.inference_mode()` and the result is cloned once, so `ImageValue`'s in-place conversions work.
- `MODEL` default is `{"value": {}}` with a `MODELField` turning anything that is not a `SpandrelModel` into `None` (`@type` refuses a `None` default) — PATHField/IMAGEField pattern.
- Load Model's card line is a `LoadModelStatus` settings field (`SimpleLabelWidget`, CONFIG row) the worker writes, like `ProgressSettings`; there is no card-subtitle API. Device notes are per node (`kind="spandrel"` warnings), precision notes travel with the pooled model.
- Pool variant key = (resolved device, requested precision string).
- Output ports are `out_image` (inlet and outlet ids share one namespace).
- Teardown on reload: covered by `wrapper.cleanup()` (the same `_cleanup → on_teardown` path a rebuild takes); a real library hot reload is in the live check.
- Catalog: four BSD-3 Real-ESRGAN entries (x4plus, x2plus, general-x4v3, animevideo-v3) from OpenModelDB @ `782aac08`. **No LaMa entry**: OpenModelDB lists none; HF `fashn-ai/LaMa` big-lama.pt is TorchScript with a `model.` key prefix spandrel does not detect; `akhaliq/lama` best.ckpt is a Lightning checkpoint spandrel's restricted unpickler refuses.
- LaMa test fixture is `LaMa(in_nc=4)` (the mask counts as an input channel).
- `../haybale-spandrel` pins `ruff==0.12.12`, `mypy==2.1.0` (the monorepo's; ruff 0.17 enables more rules by default) and imports `NodeRegistry` before `MacroRegistry` in `__init__` (import cycle otherwise).
- `tests/studio/test_component_access_classification.py` now judges only components whose source is in this repo: an installed external library (haybale-spandrel's panel) made it fail.
- Real-model smoke (MPS, fp16, realesr-general-x4v3): 960×540 → 3840×2160 in 0.33 s tiled.

## Landed (2026-11-03)

S7 is done and merged ff to master in both repos. Live check passed: setup, upscale, settings
(device, precision, scale, alpha, gray), Stop and odd tile sizes, lifecycle with two parallel
threads, the batch flow driven over Farmhand, save → reopen → run, and the user-built Upscaler
macro. Further changes after 2026-11-02, each with its own commit:

- Release no longer moves weights to the CPU; Load Model drops its outlet's reference in
  `on_shutdown` and calls `run_again()`.
- Automatic tiles are capped below 2³¹ output elements (MPS convolution limit), and `run_tiled`
  halves the tile and retries on that error; a scale above the model's shrinks the input of the
  last pass, so no pass outgrows the result.
- Load Model's card line updates on a device or precision change (`run_again()` from a settings
  subscription) and reads `< shows after the first run >` until loaded.
- `shadow()` mirrors keep their source's widget, options and range (Load Model's Device and
  Precision selects were empty).
- **Model kinds (ADR 0071):** `MODEL_BASE`, `IMAGE_MODEL`, `INPAINT_MODEL`; the loader's `ADD`
  outlet takes the kind of the first inlet it is connected to, keeps it until reset, and only then
  adds its Model picker, filtered by the kind's `catalog_filter`. Labels: **Load Spandrel Model**,
  **Spandrel Model Info** (keys unchanged). A loaded model of the wrong kind is an error.
- Core fix found on the way: an edge whose port is retyped while it links is rebuilt on the next
  validation pass (`EdgeWrapper.built_for_current_ports`).
- Model picker: describes entries (summary line, description tip, wider search); Models Volume tab
  leaves out catalog variants; card widgets reach their node (`SettingWidgetModel(wrapper=…)`).
- Catalog entries declare `purpose: ["SR"]`.

### Follow-ups

- **Priority — Inpaint live check (Task 9 step 3):** needs a spandrel-loadable LaMa file. Convert
  the HF TorchScript `big-lama.pt` (strip the `model.` key prefix, save as safetensors) for a test,
  or find a published safetensors LaMa and add it to the catalog with `purpose: ["Inpainting"]`.
- Live progress on a Group card (a progress bar promoted to an outlet and wired out of a Group)
  would need an immediate wire for `PROGRESS`; declined for now (2026-11-03).
- Farmhand `set_property` reports a false `set_rejected` for `MODEL_REF` values (as S4 minor #9
  for paths): the write lands, but the check compares the requested dict with the stored object.
