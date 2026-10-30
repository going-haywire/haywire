# S0 — IMAGE value class + realtime benchmark spike — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the storage-flexible `ImageValue` (fixed semantics, free storage, accessor-only pixel
access) in a new `haybale-image` library and prove with benchmarks that it meets the realtime budget
before anything else is built on it.

**Architecture:** A pure-Python value class (no haywire type registration yet — that is S5) holding one
*primary* buffer (numpy array or torch tensor, any supported dtype, RGB or BGR order) plus a per-value
cache of converted views. `array()` / `tensor()` convert lazily; tensor paths upload in the native
dtype and convert on the device; downloads convert on the device first. Torch is an optional import.
Benchmarks are new cases in the existing `benchmarks/` drift suite, registered only when torch / a GPU /
a model file are present.

**Tech Stack:** Python ≥ 3.12, numpy, torch (optional, `uv run --with torch`), spandrel (spike only),
existing `benchmarks/run.py` harness.

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) — §2.4 (Images),
§3 (S0 row + status rule). Read §2.4 before Task 2.

## Global Constraints

- Semantics are fixed: **RGB channel order, values in [0,1] for float dtypes, layout ∈ {gray, rgb, rgba},
  `source_depth` ∈ {8, 16, 32}**. Storage is free: dtype, channel order (RGB/BGR), residency.
- **No BGR layout/type.** BGR exists only as a storage order (`ChannelOrder.BGR`).
- Integer semantics: `uint8` spans [0,255], `uint16` spans [0,65535]; float↔int conversion is
  `clip(x, 0, 1) * max` then round-half-to-even (`np.rint` / `torch.round`); `uint8 → uint16` is `× 257`.
- Array dtypes: `uint8`, `uint16`, `float16`, `float32`. Tensor dtypes: `uint8`, `float16`, `bfloat16`,
  `float32`. Anything else → `TypeError`.
- Array shape: `H×W` or `H×W×1` (gray), `H×W×3` (rgb), `H×W×4` (rgba). Tensor shape: `C×H×W` or
  `1×C×H×W`, C ∈ {1,3,4}. Anything else → `ValueError`.
- `haybale_image` must import without torch installed; torch is imported only inside tensor code paths.
- No relative imports under `barn/` (ruff TID252). Line length 109.
- Torch stays out of the monorepo lock (spec Q32): it is an optional extra, never a hard dependency.
- Tests carry `pytestmark = pytest.mark.unit` (CI runs only `-m unit` / `-m integration`).
- Realtime gate (spec Q27/Q36): **`img_gpu_trip_1080p` min ≤ 3 ms, and below `img_cpu_f32_1080p`.**

## Review Focus

1. **Non-contiguous / negative-stride input** (a crop `a[100:500, 50:]`, a view `a[..., ::-1]`) — wraps
   without error and uploads correctly (`torch.from_numpy` rejects negative strides). → Task 2 / Task 4 tests.
2. **Caller keeps writing into the wrapped buffer** (camera producers that reuse a buffer) — wrapping is
   zero-copy by contract; ownership transfers. Returned arrays are read-only so *consumers* can't corrupt a
   shared value. → docstring on `from_array` + Task 3 read-only test.
3. **Model output slightly outside [0,1]** (overshoot, e.g. 1.03 or -0.01) — converts to integers by
   clipping, never wrapping. → Task 3 (numpy) and Task 4 (torch) clip tests.
4. **Odd sizes** (1×1, odd width/height like 1081×1921) — every accessor path works. → Task 4 round-trip test.
5. **Gray given as H×W×1** (common from OpenCV / PIL conversions) — treated as gray, returned as H×W.
   → Task 2 test.

---

### Task 1: Scaffold the `haybale-image` library and wire it into the workspace

**Files:**
- Create: `barn/haybale-image/pyproject.toml`, `barn/haybale-image/README.md`,
  `barn/haybale-image/haybale_image/__init__.py`, `barn/haybale-image/haybale_image/haybale.toml`,
  `barn/haybale-image/haybale_image/py.typed`
- Modify: `pyproject.toml` (`[tool.uv.sources]`, `[dependency-groups].dev`, `[tool.mypy].mypy_path`,
  mypy `ignore_missing_imports` overrides), `.github/workflows/mypy.yml` (path list),
  `CLAUDE.md` (the mypy command's path list), `uv.lock`
- Test: `tests/image/__init__.py`, `tests/image/test_library.py`

**Interfaces:**
- Produces: package `haybale_image`, entry point `image = "haybale_image:Library"`, library name
  `haybale-image`.

- [ ] **Step 1: Baseline.** Run `uv run ruff check . && uv run ruff format --check .` and the full mypy
  command from `CLAUDE.md`. Expected: clean. If not clean, stop and start an error-fix session with the user.

- [ ] **Step 2: Write the failing test** `tests/image/test_library.py`

```python
import pytest

pytestmark = pytest.mark.unit


def test_library_identity_is_haybale_image():
    from haybale_image import Library

    assert Library.class_identity.name == "haybale-image"
```

- [ ] **Step 3: Run it.** `uv run pytest tests/image/test_library.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Create the library.** Mirror `barn/haybale-haystack/` exactly in file roles:
  - `pyproject.toml`: name `haybale-image`, version `0.3.0`, requires-python `>=3.12`, MIT,
    dependencies `["haywire-core>=0.3.0", "numpy"]`, optional extra `torch = ["torch"]`, entry point
    `[project.entry-points."haywire.libraries"] image = "haybale_image:Library"`, hatchling,
    `packages = ["haybale_image"]`.
  - `haybale.toml`: `name = "haybale-image"`, `version = "0.3.0"`, `label = "Image"`,
    description "Image types, IO and viewers shared by vision and ML libraries", `linked_libraries = []`.
  - `__init__.py`: `@library(file_watcher=True) class Library(BaseLibrary)` with
    `register_components()` that registers nothing yet (docstring: "types/adapters/nodes arrive in S5")
    and `validate() -> True`.
  - Root `pyproject.toml`: add `haybale-image = { workspace = true }` to sources, `"haybale-image"` to the
    dev group, `"barn/haybale-image"` to `mypy_path`, and `"torch", "torch.*", "spandrel", "spandrel.*"` to
    the `ignore_missing_imports` module list.
  - Add `barn/haybale-image/haybale_image/` to the mypy path list in `.github/workflows/mypy.yml` and in
    the `CLAUDE.md` mypy command.

- [ ] **Step 5: Lock and sync.** `uv lock && uv sync` → torch must NOT appear in `uv.lock`
  (`grep -c '^name = "torch"' uv.lock` → `0`).

- [ ] **Step 6: Generate library docs.** `uv run haywire docs barn/haybale-image` → creates
  `OVERVIEW.md`, `QUICKREF.md`, `docs/`.

- [ ] **Step 7: Run the test.** `uv run pytest tests/image/test_library.py -v` → PASS.

- [ ] **Step 8: Commit.**

```bash
git add barn/haybale-image pyproject.toml uv.lock .github/workflows/mypy.yml CLAUDE.md tests/image
git commit -m "feat(image): scaffold the haybale-image library"
```

---

### Task 2: `ImageValue` construction from arrays

**Files:**
- Create: `barn/haybale-image/haybale_image/value/__init__.py`,
  `barn/haybale-image/haybale_image/value/image_value.py`
- Test: `tests/image/test_image_value.py`

**Interfaces:**
- Produces (exported from `haybale_image.value`):
  - `class Layout(StrEnum)`: `GRAY = "gray"`, `RGB = "rgb"`, `RGBA = "rgba"`
  - `class ChannelOrder(StrEnum)`: `RGB = "rgb"`, `BGR = "bgr"`
  - `class ImageValue` with
    - `@classmethod from_array(cls, data: np.ndarray, *, order: ChannelOrder = ChannelOrder.RGB, source_depth: int | None = None) -> ImageValue`
    - properties `layout: Layout`, `width: int`, `height: int`, `channels: int`, `source_depth: int`,
      `residency: str` (`"array"` for a numpy primary; the tensor's `str(device)` otherwise)

- [ ] **Step 1: Write the failing tests** in `tests/image/test_image_value.py` (`pytestmark = pytest.mark.unit`):
  - `test_gray_rgb_rgba_layouts_from_shape`: `zeros((4,6))` → `GRAY`, `channels == 1`; `(4,6,3)` → `RGB`;
    `(4,6,4)` → `RGBA`; all have `width == 6`, `height == 4`, `residency == "array"`.
  - `test_hw1_is_gray`: `zeros((4,6,1))` → `layout is Layout.GRAY`, `channels == 1`.
  - `test_bad_shapes_raise_value_error`: shapes `(4,6,2)`, `(4,6,5)`, `(2,4,6,3)`, `(6,)` each raise `ValueError`.
  - `test_bad_dtypes_raise_type_error`: `int32`, `bool`, `float64` each raise `TypeError`.
  - `test_source_depth_defaults_from_dtype`: `uint8 → 8`, `uint16 → 16`, `float16 → 32`, `float32 → 32`.
  - `test_explicit_source_depth_kept_and_validated`: `source_depth=16` on a float32 array → `16`;
    `source_depth=12` → `ValueError`.
  - `test_non_contiguous_input_wraps`: `from_array(a[1:3, ::2])` and `from_array(a[..., ::-1])` succeed with
    the sliced dimensions.

- [ ] **Step 2: Run them.** `uv run pytest tests/image/test_image_value.py -v` → FAIL (import error).

- [ ] **Step 3: Implement** `ImageValue.__init__` (private; takes the primary buffer, its `ChannelOrder`,
  `Layout`, `source_depth`) and `from_array` in `image_value.py`. `from_array` never copies; it squeezes
  `H×W×1` to `H×W`. Use `__slots__`; hold a `_cache: dict[tuple, object]` for Task 3. The `from_array`
  docstring states: *"Zero-copy: the value takes ownership of `data`; the caller must not write to it
  afterwards."* Validate dtype before shape.

- [ ] **Step 4: Run them.** Same command → PASS.

- [ ] **Step 5: Commit.** `git commit -m "feat(image): ImageValue construction from arrays"`

---

### Task 3: `array()` accessor — dtype scaling, order swap, zero-copy, read-only, cache

**Files:**
- Create: `barn/haybale-image/haybale_image/value/_numpy_ops.py`
- Modify: `barn/haybale-image/haybale_image/value/image_value.py`
- Test: `tests/image/test_image_value.py`

**Interfaces:**
- Consumes: Task 2's `ImageValue`, `ChannelOrder`, `Layout`.
- Produces:
  - `ImageValue.array(self, dtype: npt.DTypeLike = np.float32, order: ChannelOrder = ChannelOrder.RGB) -> np.ndarray`
    — `H×W` for gray, `H×W×C` otherwise; always read-only; cached per `("array", dtype, order)`.
  - `_numpy_ops.convert(src: np.ndarray, src_order: ChannelOrder, dtype: np.dtype, order: ChannelOrder) -> np.ndarray`
    — returns `src` itself (a read-only view) when nothing changes.

- [ ] **Step 1: Write the failing tests:**
  - `test_same_storage_is_zero_copy`: `a` u8 BGR `(4,6,3)`; `v.array(np.uint8, ChannelOrder.BGR)` →
    `np.shares_memory(out, a)`.
  - `test_order_swap_keeps_alpha_last`: `a` u8 `(2,2,4)` with distinct channel values, stored BGR;
    `v.array(np.uint8, ChannelOrder.RGB)` equals `a[..., [2, 1, 0, 3]]`.
  - `test_gray_ignores_order`: gray value; `array(order=BGR)` equals `array(order=RGB)`.
  - `test_u8_to_float_scales`: `255 → 1.0`, `0 → 0.0`, `51 → 0.2` (float32, `atol=1e-6`).
  - `test_u16_to_float_scales`: `65535 → 1.0`.
  - `test_float_to_u8_clips_and_rounds`: float32 `[-0.1, 0.0, 0.5, 1.0, 1.03]` → u8 `[0, 0, 128, 255, 255]`.
  - `test_u8_to_u16_is_times_257`: `255 → 65535`, `1 → 257`.
  - `test_float16_target`: u8 `128` → float16 within `1e-3` of `128/255`.
  - `test_returned_arrays_are_read_only`: writing into any `array()` result raises `ValueError`.
  - `test_accessor_is_cached`: two identical calls return the same object (`is`); a different dtype does not.

- [ ] **Step 2: Run them.** → FAIL.

- [ ] **Step 3: Implement** `_numpy_ops.convert` (order swap first as an index on channels 0–2, then
  dtype conversion per Global Constraints; `setflags(write=False)` on the result) and `ImageValue.array`
  (cache lookup → `convert` on the numpy primary; the tensor-primary branch arrives in Task 4 — raise
  `NotImplementedError` there for now).

- [ ] **Step 4: Run them.** → PASS. Also `uv run ruff check barn/haybale-image tests/image` and
  `uv run mypy barn/haybale-image/haybale_image/ tests/image/` → clean.

- [ ] **Step 5: Commit.** `git commit -m "feat(image): array accessor with lazy cached conversion"`

---

### Task 4: Torch residency — `from_tensor`, `tensor()`, device-side conversion

**Files:**
- Create: `barn/haybale-image/haybale_image/value/_torch_ops.py`
- Modify: `barn/haybale-image/haybale_image/value/image_value.py`
- Test: `tests/image/test_image_value_torch.py`, `tests/image/test_import_without_torch.py`

**Interfaces:**
- Consumes: Tasks 2–3.
- Produces:
  - `ImageValue.from_tensor(cls, data: "torch.Tensor", *, order: ChannelOrder = ChannelOrder.RGB, source_depth: int | None = None) -> ImageValue`
  - `ImageValue.tensor(self, device: "str | torch.device", dtype: "torch.dtype | None" = None, order: ChannelOrder = ChannelOrder.RGB) -> "torch.Tensor"`
    — shape `1×C×H×W`, default dtype `torch.float32`, cached per `("tensor", str(device), dtype, order)`.
  - `ImageValue.array()` now also works on a tensor primary.
  - `_torch_ops.upload(src: np.ndarray, src_order, device, dtype, order) -> torch.Tensor` and
    `_torch_ops.download(src: torch.Tensor, src_order, dtype: np.dtype, order) -> np.ndarray`.

- [ ] **Step 1: Write the failing tests.**
  `test_import_without_torch.py` (unit; runs everywhere): a subprocess
  `python -c "import sys, haybale_image.value; assert 'torch' not in sys.modules"` exits 0.
  `test_image_value_torch.py` starts with `torch = pytest.importorskip("torch")` and `pytestmark = pytest.mark.unit`:
  - `test_tensor_shape_dtype_device`: u8 BGR `(5,7,3)` → `tensor("cpu", torch.float16)` has shape `(1,3,5,7)`,
    dtype `float16`, device type `"cpu"`.
  - `test_tensor_matches_array_path`: `tensor("cpu")[0].permute(1,2,0).numpy()` ≈ `array(np.float32)`
    (`atol=1e-6`).
  - `test_u8_round_trip_is_exact_through_f16`: every value 0–255 in a `(16,16,3)` BGR u8 array →
    `from_tensor(v.tensor("cpu", torch.float16)).array(np.uint8, ChannelOrder.BGR)` equals the input exactly.
  - `test_odd_sizes_round_trip`: shapes `(1,1,3)` and `(1081,1921,4)` round-trip exactly through
    `tensor("cpu", torch.float32)` and back.
  - `test_negative_stride_input_uploads`: `from_array(a[..., ::-1])` → `tensor("cpu")` succeeds and matches.
  - `test_from_tensor_accepts_chw_and_nchw`: `(3,4,5)` and `(1,3,4,5)` accepted; `(2,3,4,5)` → `ValueError`.
  - `test_tensor_to_u8_clips`: a float tensor with `1.03` and `-0.01` → `array(np.uint8)` gives `255` and `0`.
  - `test_tensor_accessor_cached`: same args → same object; different dtype → different object.
  - `test_gpu_residency` (skip unless `torch.cuda.is_available()` or `torch.backends.mps.is_available()`):
    `tensor(dev).device.type == dev`; `from_tensor(t).residency` starts with `dev`.

- [ ] **Step 2: Run them.** `uv run --with torch pytest tests/image/ -v` → torch tests FAIL; then
  `uv run pytest tests/image/ -v` → torch tests SKIPPED, import test passes.

- [ ] **Step 3: Implement.** `_torch_ops` imports torch at module top; `image_value.py` imports
  `_torch_ops` only inside the tensor branches. `upload`: `np.ascontiguousarray` only when strides are
  negative or non-contiguous, `torch.from_numpy` in the **native** dtype, `.to(device, non_blocking=True)`,
  then on device: `permute(2,0,1)` + `unsqueeze(0)`, channel flip if orders differ, dtype conversion per
  Global Constraints. `download`: on device convert dtype + order + `permute(1,2,0)` first, then `.cpu().numpy()`,
  read-only. `from_tensor` stores the tensor as primary (squeezing a leading batch of 1).

- [ ] **Step 4: Run them.** `uv run --with torch pytest tests/image/ -v` → PASS; without `--with torch` →
  skips + import test PASS. Lint + mypy as in Task 3 → clean.

- [ ] **Step 5: Commit.** `git commit -m "feat(image): torch residency with device-side conversion"`

---

### Task 5: Benchmark cases

**Files:**
- Modify: `benchmarks/cases.py`, `benchmarks/README.md` (one paragraph: the `img_*` cases, how to run them)
- Test: none new — the runner is the check.

**Interfaces:**
- Consumes: `ImageValue`, `ChannelOrder` from Tasks 2–4.
- Produces: cases `img_wrap_1080p`, `img_cpu_f32_1080p` (micro, always registered);
  `img_gpu_up_f16_1080p`, `img_gpu_down_u8_1080p`, `img_gpu_trip_1080p` (registered only when torch imports
  and CUDA or MPS is available); `img_sr2x_540p` (also needs `spandrel` importable and env
  `HAYWIRE_BENCH_SR_MODEL` pointing at an existing file).

- [ ] **Step 1: Add the cases.** Inputs are a fixed-seed `np.random.default_rng(0)` u8 BGR frame,
  `1080×1920×3` (`540×960×3` for SR). Each `run()` builds a **fresh** `ImageValue` so the cache never
  hides the conversion; GPU cases end `run()` with `torch.cuda.synchronize()` / `torch.mps.synchronize()`.
  `ops=1`, `repeats=30`, `warmup=5`. Device: `cuda` if available else `mps`.
  - `img_wrap_1080p`: `from_array(frame, order=BGR)`.
  - `img_cpu_f32_1080p`: `from_array(frame, order=BGR).array(np.float32, RGB)` — the rejected Q24C path.
  - `img_gpu_up_f16_1080p`: `from_array(...).tensor(dev, torch.float16)`.
  - `img_gpu_down_u8_1080p`: `from_tensor(t_f16).array(np.uint8, BGR)` with `t_f16` prepared once.
  - `img_gpu_trip_1080p`: wrap → `tensor(dev, f16)` → `from_tensor` → `array(np.uint8, BGR)` — the gate.
  - `img_sr2x_540p`: prepare verifies the model file's sha256
    (`27985aa2198711ecd72f9bb274ec7b164e018fc9ce2933daaa7c7ab36a2bd3fe`), loads it with
    `spandrel.ModelLoader().load_from_file`, `.to(dev).eval()`, `.half()` when `supports_half`; `run()` does
    wrap → `tensor(dev, f16)` → `model(t)` under `torch.inference_mode()` → `from_tensor` →
    `array(np.uint8, BGR)`.

- [ ] **Step 2: Run without torch.** `uv run python benchmarks/run.py img_` → only `img_wrap_1080p` and
  `img_cpu_f32_1080p` rows; exit 0.

- [ ] **Step 3: Lint.** `uv run ruff check benchmarks && uv run ruff format --check benchmarks` → clean.

- [ ] **Step 4: Commit.** `git commit -m "bench(image): realtime spike cases for ImageValue"`

---

### Task 6: Run the spike, record the verdict, mark S0 done

**Files:**
- Modify: `benchmarks/results/results.jsonl` (appended by the runner),
  `docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md` (§2.4 note + §3 status row)

- [ ] **Step 1: Fetch the spike model** (Real-ESRGAN v2 animevideo xsx2, compact 2x, BSD-3-Clause, 2.4 MB)
  into the session scratchpad (`export SCRATCH=<your scratchpad dir>`), never into the repo:

```bash
mkdir -p "$SCRATCH/models" && curl -L -o "$SCRATCH/models/RealESRGANv2-animevideo-xsx2.pth" \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.3.0/RealESRGANv2-animevideo-xsx2.pth
shasum -a 256 "$SCRATCH/models/RealESRGANv2-animevideo-xsx2.pth"
```

Expected hash: `27985aa2198711ecd72f9bb274ec7b164e018fc9ce2933daaa7c7ab36a2bd3fe`.

- [ ] **Step 2: Run the full spike on a clean tree** (commit Tasks 1–5 first so rows are baseline-eligible):

```bash
HAYWIRE_BENCH_SR_MODEL="$SCRATCH/models/RealESRGANv2-animevideo-xsx2.pth" \
  uv run --with torch --with spandrel python benchmarks/run.py img_
```

Expected: six `img_*` rows, `dirty=false`.

- [ ] **Step 3: Evaluate the gate.** PASS iff `img_gpu_trip_1080p` min ≤ 3 ms **and** <
  `img_cpu_f32_1080p` min. Record `img_sr2x_540p` against the 33 ms frame budget (informative — model-bound).

- [ ] **Step 4: Full verification.** `uv run ruff check . && uv run ruff format --check .`, the full mypy
  command from `CLAUDE.md`, and `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`
  → all clean, `exit=0`.

- [ ] **Step 5: Mark the slice done (status rule — mandatory last task).** In the spec:
  - §3 table, S0 row: status → `done (<merge commit>, <YYYY-MM-DD>)` — or
    `done — gate FAILED, Q27 reopened (<commit>, <date>)` if Step 3 failed; link this plan in the row.
  - §2.4: add a "S0 result" line with the host, device, and the min of `img_cpu_f32_1080p`,
    `img_gpu_trip_1080p`, `img_sr2x_540p`, plus any deviation from this plan.
  - If the gate failed: stop here and bring Q27 back to the user before S1 starts.

- [ ] **Step 6: Commit.**

```bash
git add benchmarks/results/results.jsonl docs/superpowers/plans/2026-10-30-spandrel-haybale-design.md
git commit -m "docs(plan): S0 done — ImageValue realtime spike results"
```
