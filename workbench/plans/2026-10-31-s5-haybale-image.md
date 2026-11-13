# S5 — haybale-image: types, adapters, codecs, Load / Save / View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn haybale-image from a value class into a usable image library: IMAGE types and adapters, file codecs, Load / Save / View / Image Info nodes, plus the path nodes batch saving needs (Split Path, Create Folder, Output Path's `folder` outlet).

**Architecture:** `IMAGE(PrimitiveType[ImageValue])` with GRAY/RGB/RGBA subclasses (PATH-style; workers receive the bare `ImageValue`). ICC/EXIF ride on the value as `ImageMetadata`. Codecs: OpenCV decodes/encodes pixels, Pillow reads header metadata, decodes the formats cv2 lacks and writes whenever metadata must be embedded. The MJPEG viewer is ported from visiongraph into haybale-image (visiongraph untouched until S9) and gains a lazy-PNG `still` mode.

**Tech Stack:** Python 3.12, numpy, `opencv-contrib-python`, Pillow, NiceGUI/FastAPI (viewer), optional torch (residency).

**Spec:** [2026-10-30-spandrel-haybale-design.md](2026-10-30-spandrel-haybale-design.md) §2.4 (design), §3 (status). The S5 decisions below amend it.

## S5 decisions (inquisition 2026-10-31)

| # | decision |
|---|---|
| S5-Q1 | Viewer is **built in haybale-image** (ported from visiongraph, adapted to `ImageValue`, + still mode); visiongraph is untouched until S9, which deletes its copy. |
| S5-Q2 | `IMAGE(PrimitiveType[ImageValue])`, derived `IMAGE_GRAY` / `IMAGE_RGB` / `IMAGE_RGBA`; empty default = a 0×0 image of the type's layout; `store_strategy=NEVER`. |
| S5-Q3 | RGBA → RGB / GRAY **drops alpha** (straight colour kept). |
| S5-Q4 | RGB → GRAY uses **Rec. 601** (0.299, 0.587, 0.114), like cv2 / PIL / visiongraph. Other mappings are future nodes. |
| S5-Q5 | ICC / EXIF passthrough rides **on the value** (`ImageValue.metadata`); `derive()` carries it to a new image. |
| S5-Q6 | EXIF orientation is **applied on load**; the carried EXIF's Orientation tag is reset to 1. |
| S5-Q7 | **The extension is the format.** Save Image has no `format` inlet (deviation from §2.4). Unknown / missing extension raises. |
| S5-Q8 | Save Image has one NodeSettings bag per format (`jpeg`, `png`, `webp`, `tiff`, `avif`); every field `shadow()`s an `ImageSettings` LibrarySettings default. |
| S5-Q9 | Only the bag of the current extension is visible (OAK-style `_set_ui_state_all`); all are visible until a path is known. A batch whose extension varies per file toggles bags per file — accepted. |
| S5-Q10 | `depth = source \| 8 \| 16 \| 32` (default `source`), defused silently to the deepest depth the format holds at or below the request. |
| S5-Q11 | Save Image **never creates folders**; a missing parent raises "folder … does not exist — add Create Folder before Save". |
| S5-Q12 | New **Create Folder** control node (haybale-core) on a `FOLDER_PATH`: `mkdir -p` below the volume root; existing → no-op; a missing volume root raises (an unmounted drive must not be recreated on the boot disk). |
| S5-Q12b | **Output Path gains a `folder` outlet** (FOLDER_PATH = the composed path's parent), wired straight into Create Folder. A value carries no type at run time, so Create Folder cannot infer "file → parent". |
| S5-Q13 | Delete File / Delete Folder: **follow-up**, not S5. Lead option: OS trash via `send2trash` — not a trash volume (`/tmp` self-wipes; a cross-disk move copies). |
| S5-Q14 | Save outlets `next` + `saved` (FILE_PATH actually written). `if_exists = overwrite \| skip \| unique-suffix` (default `overwrite`); `skip` leaves through `next` with `saved` = the existing path; unique-suffix = first free `stem_1.ext`, `stem_2.ext`… claimed with `O_EXCL`; every write goes to a temp file in the target folder, then `os.replace`. |
| S5-Q15 | cv2 for pixels (PNG / JPEG / WebP / TIFF / BMP / AVIF read+write); Pillow for header metadata, GIF (first frame) / TGA / PIL modes `P` `LA` `I;16` `I` `F` `CMYK`, TGA write, and every write that embeds ICC/EXIF. Deps `opencv-contrib-python`, `pillow`; **AVIF is not an extra** (Pillow wheels carry it; deviation from §2.4). |
| S5-Q16 | View Image `mode = stream \| still` (default `stream`). `stream` = MJPEG, DROP-1. `still` keeps a reference to the latest value and encodes a PNG only when the browser asks; click toggles fit ↔ 1:1. |
| S5-Q17 | Load Image: `path` → `image` only. New **Split Path** data node (haybale-core): `volume` (FOLDER_PATH, volume root), `folder` (STRING, relative parent), `stem`, `extension` (STRING, with dot, as For Each File), `parent` (FOLDER_PATH). |
| S5-Q18 | Alpha is **always straight**; `premultiply` / `unpremultiply` helpers for nodes that need it. |
| S5-Q19 | Declare `opencv-contrib-python` (same as visiongraph); add libGL to the Sandcastle image. |
| S5-Q20 | Six new `img_*` benchmark cases, baseline only, no gates. |
| S5-Q21 | Add **Image Info** (width, height, layout, source depth). Resize waits for its own round. |
| S5-Q22 | No ADR. Glossary terms land with the code (Task 13). |

## Global Constraints

- Pixels are reached only through `ImageValue.array()` / `.tensor()`; no node reads `_primary`.
- No BGR types; storage conversion is never an Adapter.
- `opencv-contrib-python>=5.0.0.93` (visiongraph's floor), `pillow>=12.0`. Never `opencv-python` or `-headless`.
- No relative imports under `barn/` (ruff TID252).
- haybale-image must import without torch (`tests/image/test_import_without_torch.py` stays green).
- Every file read/write goes through `haywire.core.volumes.resolve()`; paths are bytes-safe: read with `np.fromfile` + `cv2.imdecode`, write with `cv2.imencode` + file write (cv2's path API fails on non-ASCII Windows paths).
- Torch tests: `uv run --with torch python -m pytest …`.
- `uv sync` / `uv lock` removes the local visiongraph link; reinstall with `uv pip install -e ../haybale-visiongraph/barn/haybale-visiongraph`.
- Commit **only with the user's consent** (every "Commit" step below asks first).
- Glossary / ADR / docs text is written in Task 13 from the text collected here, never earlier.

## Review Focus

1. **An empty (0×0) image reaches Save or View** (nothing loaded yet, a wired graph before its first run) → Save raises "image is empty"; View shows its placeholder and never calls the encoder. Tests: Task 9 `test_empty_image_raises`, Task 11 `test_stream_skips_empty`.
2. **Non-ASCII / spaced file names** (`Fotos/Größe 1.png`) → load and save work. Test: Task 6 `test_unicode_path_round_trip`.
3. **A broken or mislabelled file** (truncated PNG, a `.png` that is a text file) → Load raises naming the file, not `NoneType has no attribute`. Test: Task 6 `test_corrupt_file_raises`.
4. **Uppercase / alias extensions** (`.JPG`, `.jpeg`, `.TIF`) → recognised. Test: Task 6 `test_extension_aliases`.
5. **Exotic-but-common sources** (palette PNG with transparency, CMYK JPEG, 16-bit gray PNG) → loaded as RGBA, RGB, GRAY-16 respectively. Tests: Task 6 `test_palette_with_transparency_is_rgba`, `test_cmyk_jpeg_is_rgb`, `test_gray16_png`.

---

## File structure

```
barn/haybale-image/
  pyproject.toml                         modify: deps
  haybale_image/__init__.py              modify: register types/adapters/settings/widgets/nodes
  haybale_image/value/metadata.py        create: ImageMetadata
  haybale_image/value/image_value.py     modify: metadata slot, empty(), with_metadata(), derive()
  haybale_image/value/layout.py          create: convert_layout() (numpy + torch)
  haybale_image/value/_torch_ops.py      modify: layout ops on tensors
  haybale_image/helpers.py               create: PIL / cv BGR / premultiply helpers
  haybale_image/types/image.py           create: IMAGE + derived
  haybale_image/adapters/image_adapters.py create: IMAGE → derived
  haybale_image/io/formats.py            create: extension → Format table, best_depth()
  haybale_image/io/codecs.py             create: read_image(), write_image(), EncodeOptions
  haybale_image/io/placement.py          create: claim_target(), atomic_write()
  haybale_image/settings/image_settings.py create: ImageSettings
  haybale_image/nodes/load_image.py      create
  haybale_image/nodes/image_info.py      create
  haybale_image/nodes/save_image.py      create
  haybale_image/nodes/view_image.py      create
  haybale_image/viewer/backend.py        create: StreamingBackend (ported) + StillBackend
  haybale_image/viewer/image_viewer.js   create: ported numpy_viewer.js + still mode
  haybale_image/widgets/image_viewer_widget.py create
barn/haybale-core/haybale_core/nodes/
  split_path.py                          create
  create_folder.py                       create
  output_path.py                         modify: folder outlet
benchmarks/cases.py                      modify: 6 img_* cases
.sandcastle/Dockerfile                   modify: libgl1, libglib2.0-0
tests/image/…                            create per task
tests/barn/test_split_path_node.py, test_create_folder_node.py, test_output_path_node.py
```

---

### Task 1: Dependencies, library registration, Sandcastle libGL

**Files:**
- Modify: `barn/haybale-image/pyproject.toml`, `barn/haybale-image/haybale_image/__init__.py`, `.sandcastle/Dockerfile:12-16`, `uv.lock`
- Test: `tests/image/test_library.py`

**Interfaces:**
- Produces: `Library.register_components()` registering folders `settings`, `types`, `adapters`, `widgets`, `nodes` with `SettingsRegistry`, `TypeRegistry`, `AdapterRegistry`, `WidgetRegistry`, `NodeRegistry` (pattern: `barn/haybale-core/haybale_core/__init__.py`). Create the five folders with empty `__init__.py`.

- [ ] **Step 1: Failing tests** in `tests/image/test_library.py`:

```python
def test_codec_dependencies_are_present():
    import cv2
    from PIL import features
    assert cv2.__version__.startswith("5.")      # contrib 5.x, not opencv-python 4.x
    assert features.check("avif")

def test_cv2_is_contrib():
    import cv2
    assert hasattr(cv2, "ximgproc")              # contrib-only module
```

- [ ] **Step 2:** `uv run pytest tests/image/test_library.py -v` → passes today only by install-order luck; confirm `uv pip show opencv-contrib-python` lists no haybale-image requirer (expected: not required by haybale-image).
- [ ] **Step 3:** Add `"opencv-contrib-python>=5.0.0.93"`, `"pillow>=12.0"` to dependencies; replace the docstring lines "The IMAGE types … arrive in a later slice" with the new contents; implement `register_components`. Run `uv lock && uv sync`, then reinstall visiongraph (Global Constraints).
- [ ] **Step 4:** Dockerfile: add `libgl1` and `libglib2.0-0` to the apt list.
- [ ] **Step 5:** `uv run pytest tests/image -v` → PASS; `uv run python -c "import haybale_image"` without torch OK.
- [ ] **Step 6: Commit** (ask first): `build(image): depend on opencv-contrib and pillow; register component folders`

---

### Task 2: Metadata on the value, empty images, derive

**Files:**
- Create: `haybale_image/value/metadata.py`
- Modify: `haybale_image/value/image_value.py`, `haybale_image/value/__init__.py`
- Test: `tests/image/test_image_value.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class ImageMetadata: icc: bytes | None = None; exif: bytes | None = None` and `NO_METADATA = ImageMetadata()`; exported from `haybale_image.value`.
  - `ImageValue.from_array(..., metadata: ImageMetadata = NO_METADATA)`, same keyword on `from_tensor`.
  - `ImageValue.metadata -> ImageMetadata` (new slot `_metadata`).
  - `ImageValue.empty(layout: Layout) -> ImageValue` — uint8 0×0 (`(0,0)`, `(0,0,3)`, `(0,0,4)`), source_depth 8.
  - `ImageValue.is_empty -> bool` (`width == 0 or height == 0`).
  - `ImageValue.with_metadata(metadata) -> ImageValue` — same primary and **same cache dict** (shared, no copy).
  - `ImageValue.derive(new: ImageValue) -> ImageValue` — `new.with_metadata(self.metadata)`.

- [ ] **Step 1: Failing tests:**

```python
def test_empty_has_layout_and_no_pixels():
    for layout, shape in ((Layout.GRAY, (0, 0)), (Layout.RGB, (0, 0, 3)), (Layout.RGBA, (0, 0, 4))):
        img = ImageValue.empty(layout)
        assert img.layout is layout and img.is_empty and img.array(np.uint8).shape == shape

def test_metadata_defaults_to_none():
    assert ImageValue.from_array(np.zeros((2, 2), np.uint8)).metadata == NO_METADATA

def test_derive_carries_metadata():
    meta = ImageMetadata(icc=b"icc", exif=b"exif")
    src = ImageValue.from_array(np.zeros((2, 2), np.uint8), metadata=meta)
    out = src.derive(ImageValue.from_array(np.ones((4, 4, 3), np.uint8)))
    assert out.metadata == meta and out.width == 4

def test_with_metadata_shares_cache():
    img = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    a = img.array()
    assert img.with_metadata(ImageMetadata(icc=b"x")).array() is a
```

- [ ] **Step 2:** `uv run pytest tests/image/test_image_value.py -v` → FAIL (`ImportError: ImageMetadata`).
- [ ] **Step 3:** Implement as in Interfaces.
- [ ] **Step 4:** `uv run pytest tests/image -v` and `uv run --with torch python -m pytest tests/image -v` → PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): metadata on ImageValue; empty images; derive`

---

### Task 3: Layout conversion

**Files:**
- Create: `haybale_image/value/layout.py`
- Modify: `haybale_image/value/_numpy_ops.py`, `haybale_image/value/_torch_ops.py`
- Test: `tests/image/test_layout.py`, `tests/image/test_layout_torch.py` (`pytest.importorskip("torch")`)

**Interfaces:**
- Produces: `convert_layout(img: ImageValue, layout: Layout) -> ImageValue` (exported from `haybale_image.value`). Same layout → returns `img` itself. Result keeps the source's residency (numpy stays numpy, tensor stays on its device), stored dtype, channel order, `source_depth` and `metadata`.
- Rules: GRAY→RGB replicate; GRAY/RGB→RGBA alpha = dtype max (255 / 65535 / 1.0); RGBA→RGB slice (drop alpha); RGB/RGBA→GRAY = Rec. 601 on colour channels, honouring stored order (BGR weights reversed), rounded for integer dtypes.

- [ ] **Step 1: Failing tests** (numpy file; the torch file runs the same cases on `"cpu"` tensors and asserts `residency` unchanged):

```python
def test_same_layout_is_identity(): img = rgb(); assert convert_layout(img, Layout.RGB) is img
def test_gray_to_rgb_replicates(): assert (convert_layout(gray([[10]]), Layout.RGB).array(np.uint8) == [[[10, 10, 10]]]).all()
def test_rgba_to_rgb_drops_alpha(): assert (convert_layout(rgba([[[1, 2, 3, 0]]]), Layout.RGB).array(np.uint8) == [[[1, 2, 3]]]).all()
def test_rgb_to_rgba_alpha_is_opaque_u16(): assert convert_layout(rgb_u16(), Layout.RGBA).array(np.uint16)[..., 3].min() == 65535
def test_rgb_to_gray_rec601(): assert convert_layout(rgb([[[255, 0, 0]]]), Layout.GRAY).array(np.uint8)[0, 0] == 76
def test_bgr_storage_weights_follow_order():
    img = ImageValue.from_array(np.array([[[0, 0, 255]]], np.uint8), order=ChannelOrder.BGR)  # red
    assert convert_layout(img, Layout.GRAY).array(np.uint8)[0, 0] == 76
def test_keeps_storage_and_metadata():
    out = convert_layout(rgb_u16(metadata=ImageMetadata(icc=b"i")), Layout.GRAY)
    assert out.source_depth == 16 and out.metadata.icc == b"i" and out.residency == "array"
```

- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** `uv run pytest tests/image/test_layout.py -v` and `uv run --with torch python -m pytest tests/image/test_layout_torch.py -v` → PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): layout conversion on the value's residency`

---

### Task 4: Helpers — PIL, cv BGR, premultiply

**Files:**
- Create: `haybale_image/helpers.py`
- Test: `tests/image/test_helpers.py`

**Interfaces:**
- Produces:
  - `from_pil(im: PIL.Image.Image, metadata: ImageMetadata = NO_METADATA) -> ImageValue` — modes: `1`/`L`→GRAY u8; `LA`→RGBA (gray replicated); `P`→RGBA if `transparency` in `info` else RGB; `RGB`; `RGBA`; `CMYK`/`YCbCr`→RGB; `I;16`/`I;16B`→GRAY u16 depth 16; `I`→GRAY u16 (clipped to 0..65535) depth 16; `F`→GRAY f32 depth 32. Other modes: `im.convert("RGBA" if "A" in im.getbands() else "RGB")`.
  - `to_pil(img: ImageValue, depth: int = 8) -> PIL.Image.Image` — GRAY→`L` (8) / `I;16` (16) / `F` (32); RGB/RGBA→`RGB`/`RGBA` 8-bit (Pillow has no 16-bit RGB; callers needing it use cv2).
  - `from_cv_bgr(a: np.ndarray, metadata=NO_METADATA, source_depth: int | None = None) -> ImageValue` — `from_array(..., order=BGR)`, no copy.
  - `to_cv_bgr(img: ImageValue, dtype=np.uint8) -> np.ndarray` — `img.array(dtype, ChannelOrder.BGR)`.
  - `premultiply(img: ImageValue) -> np.ndarray` / `unpremultiply(rgba: np.ndarray) -> np.ndarray` — float32 H×W×4 RGB order; non-RGBA input raises `ValueError`; unpremultiply leaves alpha-0 pixels at 0.
- Tensor helpers from §2.4 are already `ImageValue.from_tensor` / `.tensor()`; no wrappers (deviation, noted in Task 13).

- [ ] **Step 1: Failing tests** — one per mode row above (`test_from_pil_<mode>` asserting layout, `array` dtype of storage via `source_depth`, and one pixel), `test_to_pil_gray16_round_trip`, `test_cv_bgr_round_trip_no_copy` (`np.shares_memory`), `test_premultiply_round_trip` (alpha 0.5 → colour halves → back within 1e-6), `test_premultiply_rejects_rgb`.
- [ ] **Step 2–4:** run → FAIL; implement; `uv run pytest tests/image/test_helpers.py -v` → PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): PIL, OpenCV and premultiply helpers`

---

### Task 5: IMAGE types and adapters

**Files:**
- Create: `haybale_image/types/image.py`, `haybale_image/adapters/image_adapters.py`
- Test: `tests/image/test_image_types.py` (integration: needs `graph_with_library_system`, `make_node` from `tests/conftest.py`; import barn classes via `importlib.import_module`)

**Interfaces:**
- Produces (in `haybale_image.types.image`):
  - `IMAGE(PrimitiveType[ImageValue])`, `@type(wire_type=DataWire, label="Image", color="#3f8fd2", store_strategy=StoreStrategy.NEVER, default={"value": ImageValue.empty(Layout.GRAY)})`; `IMAGE_GRAY` / `IMAGE_RGB` / `IMAGE_RGBA` subclasses, labels "Gray image" / "RGB image" / "RGBA image", same colour, default the empty image of their layout. Class attribute `LAYOUT: Layout | None` (`None` on IMAGE).
  - `to_dict()` → `{"value": {"width", "height", "layout"}}` (descriptive only); `from_dict()` → `ImageValue.empty(cls.LAYOUT or Layout.GRAY)`.
  - If `@type` refuses a non-dict default value, follow the PATHField pattern: an `IMAGEField(PrimitiveField)` whose `__post_init__` sets `_default = ImageValue.empty(...)`.
- Adapters: `ImageToGrayAdapter`, `ImageToRgbAdapter`, `ImageToRgbaAdapter`, each `converts_from=IMAGE`, `converts_to=<derived>`, `convert(value) = convert_layout(value, LAYOUT)`. No sibling adapters: `AdapterFactory._find_chain_with_ancestors` walks the source's MRO, so `IMAGE_GRAY → IMAGE_RGB` finds `IMAGE → IMAGE_RGB`.

- [ ] **Step 1: Failing tests:**

  Adapters are tested through the adapter factory's chain lookup between registry keys (no nodes yet; edge wiring is tested in Task 9):

```python
def test_defaults_are_empty_of_their_layout(): ...   # IMAGE_RGB(...) default value: layout RGB, is_empty
def test_derived_to_image_is_passthrough(): ...      # IMAGE_RGB → IMAGE: no adapter chain needed
def test_gray_to_rgb_chains_via_image(): ...         # IMAGE_GRAY → IMAGE_RGB resolves to ImageToRgbAdapter; result layout RGB
def test_rgba_to_rgb_drops_alpha(): ...
def test_image_never_stored(): assert IMAGE.class_identity.store_strategy is StoreStrategy.NEVER
```
- [ ] **Step 2–4:** run → FAIL; implement; `uv run pytest tests/image/test_image_types.py -v` → PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): IMAGE types and layout adapters`

---

### Task 6: Formats and codecs

**Files:**
- Create: `haybale_image/io/__init__.py`, `haybale_image/io/formats.py`, `haybale_image/io/codecs.py`
- Test: `tests/image/test_codecs.py` (fixtures written into `tmp_path` by the tests themselves; no repo image files)

**Interfaces:**
- Produces (`formats.py`):
  - `class Format(StrEnum): PNG, JPEG, WEBP, TIFF, BMP, GIF, TGA, AVIF`
  - `FORMAT_BY_EXTENSION: dict[str, Format]` — `.png .jpg .jpeg .jpe .webp .tif .tiff .bmp .gif .tga .avif`; lookup lower-cased.
  - `format_for(path: Path) -> Format` — raises `ValueError("unsupported extension '.xyz'; use .png, .jpg, …")`, `"… has no extension"`.
  - `DEPTHS: dict[Format, tuple[int, ...]]` — PNG (8, 16), TIFF (8, 16, 32), all others (8,).
  - `best_depth(fmt: Format, requested: int) -> int` — deepest in `DEPTHS[fmt]` ≤ requested, else the smallest.
  - `HOLDS_METADATA = {PNG, JPEG, WEBP, TIFF, AVIF}`.
- Produces (`codecs.py`):
  - `@dataclass(frozen=True) class EncodeOptions: depth: int | None = None` (None = source), `jpeg_quality: int = 95`, `png_compression: int = 3`, `webp_quality: int = 90`, `webp_lossless: bool = False`, `tiff_compression: str = "lzw"` (`none|lzw|deflate`), `avif_quality: int = 80`.
  - `read_image(path: Path) -> ImageValue`
  - `encode_image(img: ImageValue, fmt: Format, options: EncodeOptions) -> bytes`
- Read algorithm: bytes via `path.read_bytes()`; Pillow `Image.open(BytesIO)` header-only for `info["icc_profile"]`, `getexif()` and orientation; for GIF/TGA or a Pillow mode in {`P`, `LA`, `I`, `F`, `CMYK`, `1`} decode with Pillow (`from_pil`, first frame), else `cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)` → `from_cv_bgr` (gray 2-D stays gray; 4-channel = BGRA). Apply orientation (tags 2–8 via `np.flip` / `np.rot90` before wrapping) and write Orientation=1 into the carried EXIF. `imdecode` returning `None` / Pillow `UnidentifiedImageError` → `ValueError(f"cannot read image {path.name}")`.
- Write algorithm: `depth = best_depth(fmt, options.depth or img.source_depth)`; use Pillow when `fmt is TGA` or (`fmt in HOLDS_METADATA` and metadata non-empty and depth == 8); else `cv2.imencode` with the format's flags (`IMWRITE_JPEG_QUALITY`, `IMWRITE_PNG_COMPRESSION`, `IMWRITE_WEBP_QUALITY` (101 for lossless), `IMWRITE_TIFF_COMPRESSION` (1 / 5 / 32946), `IMWRITE_AVIF_QUALITY`) on `img.array(dtype_for(depth), BGR)`. JPEG/BMP/etc. RGBA → drop alpha first (`convert_layout`). 16-bit + metadata: cv2, metadata dropped (known limit, Task 13 notes it).

- [ ] **Step 1: Failing tests:**
  - `test_round_trip[fmt-layout-depth]` — parametrized over every supported (format, layout, depth) of `DEPTHS`; lossless formats compare exactly, JPEG/WebP/AVIF within mean abs error 3/255.
  - `test_extension_aliases` (`.JPG`, `.jpeg`, `.TIF`), `test_unknown_extension_raises`, `test_no_extension_raises`.
  - `test_best_depth`: `(PNG, 32) → 16`, `(JPEG, 16) → 8`, `(TIFF, 32) → 32`.
  - `test_unicode_path_round_trip` (`tmp_path / "Größe 1.png"`).
  - `test_corrupt_file_raises` (truncated PNG; a text file named `.png`) — message contains the file name.
  - `test_palette_with_transparency_is_rgba`, `test_cmyk_jpeg_is_rgb`, `test_gray16_png` (`source_depth == 16`), `test_gif_first_frame`, `test_tga_round_trip`.
  - `test_exif_orientation_applied` (write a 2×3 JPEG with Orientation=6 via Pillow → loaded shape 3×2, carried EXIF orientation 1).
  - `test_icc_passthrough[png|jpeg|webp|tiff]` (ICC bytes in → same bytes in the written file).
- [ ] **Step 2–4:** run → FAIL; implement; `uv run pytest tests/image/test_codecs.py -v` → PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): codecs — OpenCV pixels, Pillow metadata and gaps`

---

### Task 7: Target placement — atomic write, if_exists

**Files:**
- Create: `haybale_image/io/placement.py`
- Test: `tests/image/test_placement.py`

**Interfaces:**
- Produces:
  - `class IfExists(StrEnum): OVERWRITE = "overwrite"; SKIP = "skip"; UNIQUE_SUFFIX = "unique-suffix"`
  - `claim_target(target: Path, if_exists: IfExists) -> Path | None` — `None` means skip (target exists, SKIP). Raises `FileNotFoundError("folder … does not exist — add Create Folder before Save")` when `target.parent` is missing. UNIQUE_SUFFIX: if `target` is free claim it, else `stem_1.ext`, `stem_2.ext`…, each claim `os.open(p, O_CREAT | O_EXCL | O_WRONLY)` then close (placeholder).
  - `atomic_write(target: Path, data: bytes) -> None` — write `<parent>/.<name>.<uuid8>.tmp`, `fsync`, `os.replace(tmp, target)`; on exception remove the temp and re-raise (a claimed placeholder stays empty → removed too).

- [ ] **Step 1: Failing tests:** `test_overwrite_returns_target`, `test_skip_existing_returns_none`, `test_unique_suffix_picks_first_free` (`a.png`, `a_1.png` exist → `a_2.png`), `test_unique_suffix_claims_atomically` (two claims in a row return different paths), `test_missing_folder_raises` (message names "Create Folder"), `test_failed_write_leaves_no_file` (monkeypatch `os.replace` to raise → no `a.png`, no `.tmp`).
- [ ] **Step 2–4:** run → FAIL; implement; PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): atomic save placement with if_exists`

---

### Task 8: Load Image and Image Info nodes

**Files:**
- Create: `haybale_image/nodes/load_image.py`, `haybale_image/nodes/image_info.py`
- Test: `tests/image/test_load_image_node.py` (integration; `SCANS` volume fixture as in `tests/barn/test_path_exists_node.py`)

**Interfaces:**
- `LoadImageNode` — `@node(label="Load Image", menu="image/io", node_type=NodeType.DATA, search_tags=[…])`; `FILE_PATH.as_inlet("path", label="Path")`, `IMAGE.as_outlet("image", label="Image")`; worker `self.out("image", read_image(resolve(path)))`.
- `ImageInfoNode` — DATA, `menu="image"`; inlet `IMAGE "image"`; outlets `INT width`, `INT height`, `STRING layout` (`"gray" | "rgb" | "rgba"`), `INT depth` (source depth).
- Docstrings in the For Each File / Output Path style (user-facing, labels not ids).

- [ ] **Step 1: Failing tests:** `test_loads_png_as_rgb`, `test_missing_file_raises_naming_it`, `test_undefined_volume_raises` (`VolumeUndefinedError`), `test_image_info_outlets` (gray16 PNG → `layout "gray"`, `depth 16`).
- [ ] **Step 2–4:** run → FAIL; implement; PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): Load Image and Image Info nodes`

---

### Task 9: ImageSettings and Save Image

**Files:**
- Create: `haybale_image/settings/image_settings.py`, `haybale_image/nodes/save_image.py`
- Test: `tests/image/test_save_image_node.py`

**Interfaces:**
- `@settings(namespace="image", label="Image", description="Defaults for saving images")` `class ImageSettings(LibrarySettings)`: `jpeg_quality` INT 95 (0–100), `png_compression` INT 3 (0–9), `webp_quality` INT 90 (0–100), `webp_lossless` BOOL False, `tiff_compression` STRING "lzw" (`options=["none", "lzw", "deflate"]`), `avif_quality` INT 80 (0–100). Defaults equal `EncodeOptions`'s.
- `SaveImageNode` — CONTROL, `menu="image/io"`. Inlets: `EXEC exec`, `IMAGE image`, `FILE_PATH path` (widget mode save target), config `STRING if_exists` (SelectWidget over `IfExists` values, default `overwrite`), config `STRING depth` (`source|8|16|32`, default `source`). Outlets: `EXEC next`, `FILE_PATH saved`.
- Inner bags, each field `shadow(ImageSettings.<field>)`: `class jpeg(NodeSettings): quality`, `class png(NodeSettings): compression`, `class webp(NodeSettings): quality, lossless`, `class tiff(NodeSettings): compression`, `class avif(NodeSettings): quality`.
- Worker: empty image → `ValueError("image is empty")`; `fmt = format_for(target)`; `claimed = claim_target(resolve(path), if_exists)`; `None` → `self.out("saved", path)`, return `"next"`; else `atomic_write(claimed, encode_image(image, fmt, options))`, `self.out("saved", VolumePath(path.volume, <relative of claimed>))`, return `"next"`.
- Visibility: `hb_refresh_format_bags(path: VolumePath | None)` — known supported extension → that format's bag `NORMAL`, others `HIDDEN`; unknown/None → all `NORMAL`. Called from the `path` inlet's `on_change` and at the start of each worker run (only when the format differs from the last applied one).

- [ ] **Step 1: Failing tests:** `test_saves_png_and_reports_saved`, `test_skip_keeps_existing_and_reports_it`, `test_unique_suffix_reports_suffixed_path`, `test_missing_folder_raises`, `test_empty_image_raises`, `test_depth_source_16_png_stays_16`, `test_depth_16_jpeg_defuses_to_8` (no error), `test_node_quality_overrides_library_default` (JPEG size at quality 20 < at 95), `test_library_default_reaches_node` (set `ImageSettings.jpeg_quality` → node's `jpeg.quality` follows), `test_only_current_format_bag_visible` (`.jpg` → `png` bag fields `HIDDEN`), `test_all_bags_visible_without_path_extension`, `test_load_outlet_wires_into_save` (LoadImage `image` → Save `image` edge links).
- [ ] **Step 2–4:** run → FAIL; implement; PASS.
- [ ] **Step 5: Commit** (ask first): `feat(image): Save Image with per-format settings and if_exists`

---

### Task 10: Path nodes in haybale-core — Split Path, Create Folder, Output Path `folder`

**Files:**
- Create: `barn/haybale-core/haybale_core/nodes/split_path.py`, `barn/haybale-core/haybale_core/nodes/create_folder.py`
- Modify: `barn/haybale-core/haybale_core/nodes/output_path.py` (`init`, `worker`, docstring)
- Test: `tests/barn/test_split_path_node.py`, `tests/barn/test_create_folder_node.py`, `tests/barn/test_output_path_node.py`

**Interfaces:**
- `SplitPathNode` — DATA, `menu="core/paths"`, label "Split Path". Inlet `PATH path`. Outlets: `FOLDER_PATH volume` (`VolumePath(key, "")`), `STRING folder` (POSIX parent of `relative`, `""` at root), `STRING stem`, `STRING extension` (`PurePosixPath(relative).suffix`, with dot), `FOLDER_PATH parent` (`VolumePath(key, folder)`). Pure string work; no resolve.
- `OutputPathNode` gains `FOLDER_PATH.as_outlet("folder", label="Folder")` = `VolumePath(folder.volume, <parent of composed relative>)`; docstring adds the Create Folder line to its example.
- `CreateFolderNode` — CONTROL, `menu="core/paths"`, label "Create Folder". Inlets `EXEC exec`, `FOLDER_PATH path`; outlets `EXEC next`, `FOLDER_PATH folder` (passes `path` on). Worker: `target = resolve(path)`; volume root (`resolve(VolumePath(path.volume, ""))`) missing → `FileNotFoundError("volume '<name>' location <root> does not exist")`; `target.mkdir(parents=True, exist_ok=True)`; an existing file at `target` → the OS error propagates.

- [ ] **Step 1: Failing tests:**
  - Split Path: `test_splits_nested` (`a/b/x.png` → folder `a/b`, stem `x`, ext `.png`, parent `VolumePath(k, "a/b")`, volume `VolumePath(k, "")`), `test_root_file` (`x.png` → folder `""`), `test_round_trips_through_output_path` (Split → Output Path inputs → same `VolumePath`).
  - Output Path: `test_folder_outlet_is_parent`.
  - Create Folder: `test_creates_nested`, `test_existing_is_noop`, `test_missing_volume_root_raises_and_creates_nothing` (location `tmp_path / "unmounted"` → nothing created), `test_escape_raises`, `test_wires_from_output_path_folder`.
- [ ] **Step 2–4:** run → FAIL; implement; `uv run pytest tests/barn/test_split_path_node.py tests/barn/test_create_folder_node.py tests/barn/test_output_path_node.py -v` → PASS.
- [ ] **Step 5: Commit** (ask first): `feat(core): Split Path, Create Folder; Output Path folder outlet`

---

### Task 11: Viewer — ported stream backend, still mode, View Image

**Files:**
- Create: `haybale_image/viewer/__init__.py`, `haybale_image/viewer/backend.py`, `haybale_image/viewer/image_viewer.js`, `haybale_image/widgets/image_viewer_widget.py`, `haybale_image/nodes/view_image.py`
- Test: `tests/image/test_viewer_backend.py` (unit), `tests/image/test_view_image_node.py` (integration)
- Source to port (read, do not modify): `../haybale-visiongraph/barn/haybale-visiongraph/haybale_visiongraph/widgets/components/streaming_viewer.py`, `numpy_viewer.js`, `widgets/numpy_viewer_widget.py`

**Interfaces:**
- `StreamingBackend` — same constructor and `endpoint` as visiongraph's; `stream(img: ImageValue) -> None` encodes `img.array(np.uint8, BGR)` (RGBA → drop alpha) as JPEG; empty image → returns without encoding. Port cleanups: `logging.getLogger(__name__)` instead of `print`, no `__del__` (the widget's `_on_cleanup` calls `cleanup()`).
- `StillBackend(endpoint: str | None = None)` — `show(img: ImageValue) -> int` stores the reference, bumps and returns `version`; `GET <endpoint>` encodes the stored image to PNG (8-bit, alpha kept) on request, `Cache-Control: no-store`; nothing stored → 204. `cleanup()` removes the route.
- `ImageViewerWidget` (`@widget(min_width=160)`) — `properties`: `mode` (`stream|still`), `quality` (80), `frame_width`, `frame_color` as in `NumpyViewerWidget`. `stream` renders `<img src=endpoint>`; `still` renders `<img src=endpoint?v=n>` whose `v` prop is updated on `show()`, click toggles a `hw-image-1to1` class (natural size, scroll container).
- `ViewImageNode` — CONTROL, `menu="image"`, label "View Image". Inlets `EXEC exec`, `IMAGE image` (widget `ImageViewerWidget`, `show_widget=WHEN_LINKED`); config `STRING mode` (`stream|still`, default `stream`) — changing it rebuilds the widget; outlets `EXEC next`, `IMAGE image_out` (pass-through).

- [ ] **Step 1: Failing tests:** `test_stream_skips_empty` (no JPEG encoded: monkeypatch `cv2.imencode` to fail if called), `test_stream_drop1_keeps_latest` (two `stream()` calls, queue holds the second), `test_still_encodes_only_on_request` (`show()` ×100 → `cv2.imencode` called 0 times; one GET → 1 time, PNG magic bytes), `test_still_without_image_is_204`, `test_cleanup_removes_routes`, `test_view_image_passes_image_through`.
- [ ] **Step 2–4:** run → FAIL; implement; PASS.
- [ ] **Step 5: Live check** (haywire-live-studio skill): Load Image → View Image `still` on a 4K PNG; toggle 1:1; then a realtime source in `stream` mode. Report what was seen.
- [ ] **Step 6: Commit** (ask first): `feat(image): View Image with stream and still modes`

---

### Task 12: Benchmarks

**Files:**
- Modify: `benchmarks/cases.py` (`_image_cases`)

**Interfaces:**
- New cases, all `"micro"`, `"ns"`, `_IMG_REPEATS`, inputs from `_bgr_frame(1080, 1920)` encoded once in `prepare` into `tempfile` bytes: `img_load_png8_1080p`, `img_load_jpeg_1080p` (`read_image` on a file), `img_save_png8_1080p`, `img_save_jpeg_1080p` (`encode_image`, default options), `img_adapt_gray_to_rgb_1080p` (`convert_layout`), `img_view_stream_encode_1080p` (`StreamingBackend.stream` encode path, route not served).

- [ ] **Step 1:** add cases; `uv run python benchmarks/run.py img_` (or the haywire-benchmark skill) on a clean tree → six new rows in `benchmarks/results/results.jsonl`.
- [ ] **Step 2: Commit** (ask first) with the result rows: `bench(image): load, save, adapt and stream-encode cases`

---

### Task 13: Docs, glossary, trap, spec status

**Files:**
- Modify: `docs/reference/glossary.md`, `CLAUDE.md` (Traps list), spec §2.4 / §3 / §5
- Create: `.insights/project_cv2_distribution_clash.md`
- Regenerate: `uv run haywire docs barn/haybale-image` and `uv run haywire docs barn/haybale-core`

- [ ] **Step 1: Glossary** — add (glossary format):
  - **Image layout** — which channels an image has: gray, RGB or RGBA. Carried by the image type (`IMAGE_GRAY`, `IMAGE_RGB`, `IMAGE_RGBA`); `IMAGE` accepts any.
  - **Image storage** — how an image's pixels are held: dtype, channel order (RGB/BGR), and residency (array or tensor on a device). Invisible to wires; nodes reach pixels only through the value's accessors. Changing storage is never an Adapter.
  - **Image metadata** — the ICC profile and EXIF block an image carries from Load to Save.
  - Note under **Adapter**: reserved for type-changing conversions; an image's storage conversion is not one.
- [ ] **Step 2: Trap** — `.insights/project_cv2_distribution_clash.md`: `opencv-python`, `opencv-contrib-python` and `-headless` all install into one `cv2/` package; the last install wins. The dev `.venv` carries `opencv-python` 4.x (required by upstream `visiongraph`) beside contrib 5.x; contrib wins by install order. haybale-image declares contrib; check with `cv2.__version__` / `hasattr(cv2, "ximgproc")`. Add a one-line entry to CLAUDE.md "Framework gotchas".
- [ ] **Step 3: Image docs fact** — in haybale-image's library docs (OVERVIEW via docstrings): `cv2.imread(IMREAD_UNCHANGED)` ignores EXIF orientation; Load Image applies it itself. Also: 16-bit saves drop ICC/EXIF (Pillow has no 16-bit RGB writer).
- [ ] **Step 4: Spec** — in §2.4 add "**S5 decisions**" pointing to this plan's table and "**S5 deviations**" (no `format` inlet; AVIF not an extra; no tensor helper wrappers; plus anything found while building). In §4/§2.2 book follow-ups: Delete File/Folder (S5-Q13 note), Resize node. In §3 set S5 to `done` with the merge commit hash and date, link this plan.
- [ ] **Step 5:** Full gate: `uv run ruff check . && uv run ruff format --check .`, the mypy command from CLAUDE.md, `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, `uv run --with torch python -m pytest tests/image -q`. Commit `barn/haybale-testing` changes first if any (docs-test trap).
- [ ] **Step 6: Commit** (ask first): `docs(image): glossary, cv2 trap, S5 done`
