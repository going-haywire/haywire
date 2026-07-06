# Visiongraph Round 6 Implementation Plan — Sample Depth + Colorize Depth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two new haybale-visiongraph nodes — **Sample Depth** (median Z-depth in meters at a normalized coordinate of a `DEPTH_FRAME`) and **Colorize Depth** (`DEPTH_FRAME` → viewable colormapped frame) — implementing the design settled in the round-6 inquisition (Q1-Q10), plus the notes.md vocabulary/non-goals record.

**Architecture:** Both are plain EXEC-driven worker nodes consuming `DEPTH_FRAME` from the existing event-node chain — **no handle type, no probe node, no requirement-union change** (the event node's `depth=True` subscription IS the depth requirement; the edge already carries the same buffer `OakDInput.distance()` reads). Each node's numeric core is a **pure module-level function** (`sample_depth_m`, `colorize_depth`) so the logic is unit-testable with synthetic numpy arrays and no framework/hardware. The `DEPTH_FRAME` uint16-millimetres contract is fixed; both nodes validate `dtype` loudly. Colorize's `min_depth`/`max_depth` are gated with `enabled_when: ("range_mode", "fixed")` — the first declarative consumer of the reactive-panel-disabling feature.

**Tech Stack:** Python, numpy, OpenCV (`cv2.applyColorMap`, already a transitive dependency via visiongraph), haywire node API (`@node`, `init()`/`worker()`/`self.out()`, worker-returns-outlet-name), `NodeSettings` bags.

## Global Constraints

- **Sequencing:** runs AFTER the reactive-panel-disabling rev-2 plan (Colorize's `enabled_when` metadata needs it to actually gray out; the settings still *work* without it, but the dogfood verification step assumes it landed).
- **Repo discipline:** all edits land in the haybale-visiongraph repository. Quality commands and `git add`/`git commit` run from `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph` (the monorepo's `barn/haybale-visiongraph` is a gitignored symlink — a `git add` from haywire-repo silently hits the ignore rule). Tests and the app run from haywire-repo (`uv run pytest`, `uv run haywire`) against the live framework, per the library's own CLAUDE.md.
- **DEPTH_FRAME contract (Q3):** fixed uint16 millimetres. Consumers validate `data.dtype == np.uint16` and fail loud (Sample Depth → `invalid` pulse; Colorize → warn once + no pulse). No `depth_scale` metadata.
- **Vocabulary (Q9):** *depth* = Z-value at a pixel. The word *distance* must not appear in node labels, port ids, or docstrings except in the notes.md deferral ("euclidean distance requires intrinsics — see space-stream").
- **Channel order:** the viewer pipeline is **BGR** (OpenCV convention — `streaming_viewer.py` documents "Numpy BGR frame" and `cv2.imencode`s directly), so `cv2.applyColorMap` output passes through with NO `cvtColor`. `RGB_FRAME`'s name notwithstanding, its `data` is de-facto BGR ecosystem-wide; do not "fix" this per-node (recorded in notes.md).
- **Pure helpers:** `sample_depth_m` / `colorize_depth` take numpy + plain params, return `Optional` results, never log, never touch node state. All logging/warn-once lives in the workers.
- New test directory `barn/haybale-visiongraph/tests/` (the library has none yet). Tests run from haywire-repo: `uv run pytest barn/haybale-visiongraph/tests -v` — the explicit path overrides `testpaths = ["tests"]`, and the `unit` marker is registered by the monorepo's pyproject (`--strict-markers` satisfied). Note: the monorepo's default `uv run pytest` will NOT pick these up (by design — the symlink is gitignored and absent on CI).
- Test files start with `import haywire.core.graph.editor  # noqa: F401` (CLAUDE.md circular-import trap), since importing the node modules pulls haywire core.
- Node-module import discipline: numpy at module top (established pattern), `cv2` lazily inside the worker (nothing in the library imports cv2 at module scope today; keep cold-start clean).
- Ruff + mypy stay clean on every touched file (run from the haybale-visiongraph repo, as in prior rounds).

---

## File Structure

| File | Responsibility |
|---|---|
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/sample_depth_node.py` | `sample_depth_m()` pure helper + `SampleDepthNode` (`vision/measure`). |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/colorize_depth_node.py` | `colorize_depth()` pure helper + `ColorizeDepthNode` (`vision/draw`). |
| `barn/haybale-visiongraph/haybale_visiongraph/nodes/__init__.py` | Import + `__all__` entries for both nodes (folder scan registers them; `__init__` exports keep the convention). |
| `barn/haybale-visiongraph/tests/test_sample_depth.py` | Synthetic-numpy unit tests for `sample_depth_m`. |
| `barn/haybale-visiongraph/tests/test_colorize_depth.py` | Synthetic-numpy unit tests for `colorize_depth`. |
| `barn/haybale-visiongraph/notes.md` | Round-6 record: decisions, depth-vs-distance vocabulary, BGR convention note, non-goals with space-stream references. |

(All paths relative to the haybale-visiongraph repo root.)

---

### Task 1: Sample Depth node

**Files:**
- Create: `barn/haybale-visiongraph/haybale_visiongraph/nodes/sample_depth_node.py`
- Test: `barn/haybale-visiongraph/tests/test_sample_depth.py` (new file + new directory)

**Interfaces:**
- Consumes: `DEPTH_FRAME`/`BaseFrame` from `haybale_visiongraph.types.frame_type`; `EXEC` from `haybale_core.types`; `FLOAT`/`INT` from `haywire.barn.builtin.types`.
- Produces: `sample_depth_m(data: np.ndarray | None, x: float, y: float, window: int = 1) -> float | None` (module-level, imported by tests); `SampleDepthNode` registered via the nodes folder scan.

- [ ] **Step 1: Baseline check**

Run:
```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
uv run ruff check barn/haybale-visiongraph/haybale_visiongraph/nodes/
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/
```
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Create `barn/haybale-visiongraph/tests/test_sample_depth.py`:

```python
# barn/haybale-visiongraph/tests/test_sample_depth.py
"""
sample_depth_m() — the pure numeric core of the Sample Depth node.

Synthetic uint16-mm buffers only: no framework fixtures, no hardware.
Contract under test (round-6 inquisition Q3/Q5/Q6/Q7):
- normalized 0-1 coordinates, clamped, mapped like OakDInput._calculate_depth_coordinates
- uint16-mm in, float meters out
- window k: median over the k*k neighborhood, ignoring 0 = no-data pixels
- None (never a sentinel number) for anything unanswerable
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import numpy as np
import pytest

from haybale_visiongraph.nodes.sample_depth_node import sample_depth_m

pytestmark = pytest.mark.unit


def _flat(depth_mm: int, h: int = 10, w: int = 20) -> np.ndarray:
    return np.full((h, w), depth_mm, dtype=np.uint16)


class TestCoordinateMapping:
    def test_center_pixel_mm_to_m(self):
        data = _flat(1500)
        assert sample_depth_m(data, 0.5, 0.5) == pytest.approx(1.5)

    def test_specific_pixel(self):
        data = _flat(1000)
        data[2, 15] = 3000  # iy=round(0.2*10)=2, ix=round(0.75*20)=15
        assert sample_depth_m(data, 0.75, 0.2) == pytest.approx(3.0)

    def test_coordinates_clamp_to_frame(self):
        data = _flat(1000)
        data[9, 19] = 2000  # bottom-right pixel
        assert sample_depth_m(data, 1.0, 1.0) == pytest.approx(2.0)
        assert sample_depth_m(data, 1.5, 99.0) == pytest.approx(2.0)  # clamp beyond
        data[0, 0] = 4000
        assert sample_depth_m(data, -0.5, -0.5) == pytest.approx(4.0)


class TestWindow:
    def test_window_median_ignores_zero_holes(self):
        data = _flat(0)  # everything no-data...
        data[4:7, 9:12] = [[0, 1000, 0], [1200, 0, 1400], [0, 1600, 0]]  # ...except 4 valid
        # window=3 around center (5,10): valid = {1000, 1200, 1400, 1600} -> median 1.3m
        assert sample_depth_m(data, 10 / 20, 5 / 10, window=3) == pytest.approx(1.3)

    def test_window_1_on_hole_is_none_even_with_valid_neighbors(self):
        data = _flat(1000)
        data[5, 10] = 0
        assert sample_depth_m(data, 10 / 20, 5 / 10, window=1) is None

    def test_window_3_rescues_the_same_hole(self):
        data = _flat(1000)
        data[5, 10] = 0
        assert sample_depth_m(data, 10 / 20, 5 / 10, window=3) == pytest.approx(1.0)

    def test_even_window_normalizes_up_to_odd(self):
        data = _flat(1000)
        data[5, 10] = 0
        # window=2 behaves as 3 (documented normalization), so the hole is rescued
        assert sample_depth_m(data, 10 / 20, 5 / 10, window=2) == pytest.approx(1.0)

    def test_window_clips_at_frame_edge(self):
        data = _flat(0)
        data[0, 0] = 500
        assert sample_depth_m(data, 0.0, 0.0, window=5) == pytest.approx(0.5)


class TestUnanswerable:
    def test_none_data(self):
        assert sample_depth_m(None, 0.5, 0.5) is None

    def test_all_zero_window(self):
        assert sample_depth_m(_flat(0), 0.5, 0.5, window=5) is None

    def test_wrong_dtype_rejected(self):
        bad = np.full((10, 20), 1.5, dtype=np.float32)
        assert sample_depth_m(bad, 0.5, 0.5) is None

    def test_wrong_ndim_rejected(self):
        bad = np.zeros((10, 20, 3), dtype=np.uint16)
        assert sample_depth_m(bad, 0.5, 0.5) is None

    def test_empty_rejected(self):
        assert sample_depth_m(np.zeros((0, 0), dtype=np.uint16), 0.5, 0.5) is None
```

- [ ] **Step 3: Run tests to verify they fail**

From haywire-repo:

Run: `uv run pytest barn/haybale-visiongraph/tests/test_sample_depth.py -v`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'haybale_visiongraph.nodes.sample_depth_node'`.

- [ ] **Step 4: Implement the node**

Create `barn/haybale-visiongraph/haybale_visiongraph/nodes/sample_depth_node.py`:

```python
"""
Sample Depth Node - reads the metric Z-depth (meters) at a normalized
coordinate of a DEPTH_FRAME, with an optional median window over no-data holes.

Camera-agnostic by design (round-6 inquisition Q2): it consumes the
DEPTH_FRAME already flowing from any event-node chain — the same buffer
``OakDInput.distance()`` reads — so there is no device handle, no probe
node, and no requirement-union change; the event node's ``depth=True``
subscription IS the depth requirement.

Vocabulary (Q9): this node reports *depth* — the Z-value at a pixel.
Euclidean *distance* to the 3D point needs camera intrinsics and is a
deliberate non-goal (see notes.md; reference: cansik/space-stream).

Failure is control flow (Q7): ``sampled`` / ``invalid`` EXEC outlets via the
worker-returns-outlet-name pattern; ``depth_m`` only updates on success, so
it never carries a sentinel and holds the last good measurement.
"""

import logging
from typing import Optional

import numpy as np

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import INT

logger = logging.getLogger(__name__)


def sample_depth_m(
    data: "np.ndarray | None", x: float, y: float, window: int = 1
) -> Optional[float]:
    """Median Z-depth in meters at normalized (*x*, *y*) of a uint16-mm buffer.

    Pure function (no logging, no state) — the node's testable numeric core.

    - Coordinates are normalized 0-1, clamped, and mapped exactly like
      ``OakDInput._calculate_depth_coordinates`` (round to nearest pixel).
    - *window* is the sampling kernel k: median over the k*k neighborhood
      ignoring 0 = no-data pixels. Even values normalize up to the next odd;
      the patch clips at frame edges. 1 = single pixel.
    - Returns ``None`` when unanswerable: no/empty/non-uint16-mm buffer
      (DEPTH_FRAME contract, see frame_type.py), or no valid depth in the
      window. Never a sentinel number.
    """
    if (
        data is None
        or not isinstance(data, np.ndarray)
        or data.dtype != np.uint16
        or data.ndim != 2
        or data.size == 0
    ):
        return None

    h, w = data.shape[:2]
    ix = min(max(round(float(x) * w), 0), w - 1)
    iy = min(max(round(float(y) * h), 0), h - 1)

    k = max(1, int(window))
    if k % 2 == 0:
        k += 1
    r = k // 2

    patch = data[max(0, iy - r) : iy + r + 1, max(0, ix - r) : ix + r + 1]
    valid = patch[patch > 0]
    if valid.size == 0:
        return None
    return float(np.median(valid)) / 1000.0


@node(
    label="Sample Depth",
    description="Reads the metric Z-depth (meters) at a normalized coordinate of a depth frame",
    menu="vision/measure",
    search_tags=["depth", "sample", "measure", "meters", "probe", "z", "oak", "stereo"],
    node_type=NodeType.CONTROL,
)
class SampleDepthNode(BaseNode):
    """
    Samples a DEPTH_FRAME at a normalized coordinate and outputs meters.

    Inputs:
        sample: Control flow in — sample the current frame now.
        depth: DEPTH_FRAME to sample (uint16 millimetres per pixel).
        x, y: Normalized coordinate (0-1), clamped. Live data pins — a
              tracker/detection output can drive them between pulses.

    Outputs:
        sampled: Pulsed when a valid depth was read; depth_m is updated.
        invalid: Pulsed when there is no valid answer (no frame, no valid
                 depth in the window, or a non-uint16 buffer violating the
                 DEPTH_FRAME contract). depth_m keeps its last good value.
        depth_m: Median Z-depth in meters at (x, y).
    """

    class sampling(NodeSettings):
        window = setting[INT](
            1,
            min=1,
            max=15,
            label="Window",
            category="Sampling",
            description=(
                "Sampling kernel k: median over the k×k neighborhood, ignoring "
                "no-data (0) pixels — rescues single-pixel depth holes. Even "
                "values round up to odd. 1 = exact single pixel."
            ),
        )

    def init(self):
        from haywire.barn.builtin.types import FLOAT
        from haybale_core.types import EXEC
        from ..types.frame_type import DEPTH_FRAME

        self.add(EXEC.as_inlet("sample", label="Sample"))
        self.add(DEPTH_FRAME.as_inlet("depth", label="Depth"))
        self.add(
            FLOAT.as_inlet(
                "x",
                default=0.5,
                label="X (0-1)",
                description="Normalized horizontal coordinate, 0 = left, 1 = right. Clamped.",
            )
        )
        self.add(
            FLOAT.as_inlet(
                "y",
                default=0.5,
                label="Y (0-1)",
                description="Normalized vertical coordinate, 0 = top, 1 = bottom. Clamped.",
            )
        )

        self.add(EXEC.as_outlet("sampled", label="Sampled"))
        self.add(EXEC.as_outlet("invalid", label="Invalid"))
        self.add(FLOAT.as_outlet("depth_m", label="Depth (m)"))

    def post_init(self):
        self.hb_warned_dtype = False

    def worker(self, context: ExecutionContext, depth, x, y) -> Optional[str]:
        from ..types.frame_type import BaseFrame

        data = depth.data if isinstance(depth, BaseFrame) else depth

        # DEPTH_FRAME contract: uint16 millimetres (frame_type.py). A wrong
        # dtype is a producer bug — warn once, then report via control flow.
        if isinstance(data, np.ndarray) and data.size and data.dtype != np.uint16:
            if not self.hb_warned_dtype:
                logger.warning(
                    "Sample Depth received a %s buffer; DEPTH_FRAME is uint16 "
                    "millimetres by contract — pulsing 'invalid'.",
                    data.dtype,
                )
                self.hb_warned_dtype = True
            return "invalid"

        result = sample_depth_m(
            data,
            0.5 if x is None else float(x),
            0.5 if y is None else float(y),
            self.sampling.window,
        )
        if result is None:
            return "invalid"

        self.out("depth_m", result)
        return "sampled"
```

- [ ] **Step 5: Run tests to verify they pass**

From haywire-repo:

Run: `uv run pytest barn/haybale-visiongraph/tests/test_sample_depth.py -v`
Expected: PASS, all 13 tests green.

- [ ] **Step 6: Register the export**

In `barn/haybale-visiongraph/haybale_visiongraph/nodes/__init__.py`, add (matching the existing style):

```python
from .sample_depth_node import SampleDepthNode
```

and `"SampleDepthNode"` to `__all__`.

- [ ] **Step 7: Quality checks**

Run:
```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
uv run ruff check barn/haybale-visiongraph/
uv run ruff format --check barn/haybale-visiongraph/
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/sample_depth_node.py
```
Expected: all clean. From haywire-repo: `uv run pytest -m "not integration" -q` — unchanged pass count (the monorepo suite doesn't collect the new tests; this run proves the new module import breaks nothing at library scan).

- [ ] **Step 8: Commit (haybale-visiongraph repo)**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/haybale_visiongraph/nodes/sample_depth_node.py barn/haybale-visiongraph/haybale_visiongraph/nodes/__init__.py barn/haybale-visiongraph/tests/test_sample_depth.py
git commit -m "feat(nodes): Sample Depth — median Z-depth (m) at a normalized coordinate"
```

---

### Task 2: Colorize Depth node

**Files:**
- Create: `barn/haybale-visiongraph/haybale_visiongraph/nodes/colorize_depth_node.py`
- Test: `barn/haybale-visiongraph/tests/test_colorize_depth.py`

**Interfaces:**
- Consumes: `DEPTH_FRAME`/`RGB_FRAME`/`BaseFrame` from `frame_type`; `EXEC` from `haybale_core.types`; `CHOICES`/`FLOAT` from builtin types; cv2 (lazy).
- Produces: `colorize_depth(data, colormap: int, range_mode: str = "auto", min_depth_m: float = 0.3, max_depth_m: float = 8.0) -> np.ndarray | None` (module-level; *colormap* is a `cv2.COLORMAP_*` constant); `ColorizeDepthNode` registered via folder scan.

- [ ] **Step 1: Baseline check**

Run (from haybale-visiongraph): `uv run ruff check barn/haybale-visiongraph/haybale_visiongraph/nodes/ && uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/`
Expected: clean.

- [ ] **Step 2: Write the failing tests**

Create `barn/haybale-visiongraph/tests/test_colorize_depth.py`:

```python
# barn/haybale-visiongraph/tests/test_colorize_depth.py
"""
colorize_depth() — the pure numeric core of the Colorize Depth node.

Synthetic uint16-mm buffers only. Contract (round-6 inquisition Q3/Q8):
- uint16-mm in, (H, W, 3) uint8 BGR out (viewer pipeline is BGR — it
  cv2.imencode's frames directly; no cvtColor anywhere)
- no-data (0) pixels are black in the output
- auto mode normalizes over VALID pixels per frame; fixed mode maps
  [min_depth_m, max_depth_m] and clips outside
- None for unanswerable input (wrong dtype/ndim/empty)
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import cv2
import numpy as np
import pytest

from haybale_visiongraph.nodes.colorize_depth_node import colorize_depth

pytestmark = pytest.mark.unit

CM = cv2.COLORMAP_TURBO


def _flat(depth_mm: int, h: int = 8, w: int = 12) -> np.ndarray:
    return np.full((h, w), depth_mm, dtype=np.uint16)


class TestOutputShape:
    def test_shape_and_dtype(self):
        out = colorize_depth(_flat(1000), CM)
        assert out.shape == (8, 12, 3)
        assert out.dtype == np.uint8

    def test_no_data_pixels_are_black(self):
        data = _flat(1000)
        data[0, 0] = 0
        out = colorize_depth(data, CM)
        assert (out[0, 0] == 0).all()
        assert (out[4, 6] != 0).any()  # valid pixel got a color

    def test_all_no_data_is_all_black_not_none(self):
        out = colorize_depth(_flat(0), CM)
        assert out is not None
        assert not out.any()


class TestRangeMapping:
    def test_auto_spans_valid_range(self):
        data = _flat(1000)
        data[:, 6:] = 3000
        out = colorize_depth(data, CM, range_mode="auto")
        # near half and far half must get different colors
        assert (out[0, 0] != out[0, 11]).any()

    def test_auto_constant_frame_does_not_divide_by_zero(self):
        out = colorize_depth(_flat(1500), CM, range_mode="auto")
        assert out is not None
        assert out.shape == (8, 12, 3)

    def test_fixed_clips_outside_range(self):
        data = _flat(500)  # 0.5 m — below min
        data[:, 6:] = 60000  # 60 m — above max
        out = colorize_depth(data, CM, range_mode="fixed", min_depth_m=1.0, max_depth_m=8.0)
        # below-min pixels clamp to the colormap's low end, above-max to its
        # high end — both valid colors (not black), and distinct from each other
        assert (out[0, 0] != out[0, 11]).any()
        assert (out[0, 0] != 0).any() and (out[0, 11] != 0).any()

    def test_fixed_degenerate_range_survives(self):
        out = colorize_depth(_flat(1000), CM, range_mode="fixed", min_depth_m=2.0, max_depth_m=2.0)
        assert out is not None


class TestUnanswerable:
    def test_none_data(self):
        assert colorize_depth(None, CM) is None

    def test_wrong_dtype(self):
        assert colorize_depth(np.zeros((4, 4), dtype=np.float32), CM) is None

    def test_wrong_ndim(self):
        assert colorize_depth(np.zeros((4, 4, 3), dtype=np.uint16), CM) is None

    def test_empty(self):
        assert colorize_depth(np.zeros((0, 0), dtype=np.uint16), CM) is None
```

- [ ] **Step 3: Run tests to verify they fail**

From haywire-repo:

Run: `uv run pytest barn/haybale-visiongraph/tests/test_colorize_depth.py -v`
Expected: FAIL at collection — `ModuleNotFoundError: No module named 'haybale_visiongraph.nodes.colorize_depth_node'`.

- [ ] **Step 4: Implement the node**

Create `barn/haybale-visiongraph/haybale_visiongraph/nodes/colorize_depth_node.py`:

```python
"""
Colorize Depth Node - maps a DEPTH_FRAME (uint16 millimetres) onto an OpenCV
colormap so depth becomes viewable in the existing frame viewer.

Deliberately a NODE, never an adapter (frame_type.py / notes.md Q3/Q5):
colorization is lossy and parameterized, so it must be an explicit,
configurable step in the graph.

Range mapping (round-6 inquisition Q8): ``auto`` normalizes each frame over
its VALID (nonzero) pixels — zero-config, but colors are not comparable
across frames; ``fixed`` maps [min_depth, max_depth] meters — stable colors
for real inspection. ``min_depth``/``max_depth`` carry
``enabled_when: ("range_mode", "fixed")`` so the panel grays them out live
while ``auto`` is selected (the first declarative consumer of the reactive
panel-disabling feature).

Channel order: the viewer pipeline is BGR (streaming_viewer cv2.imencode's
frames directly), so cv2.applyColorMap output passes through unconverted.
Simple linear mapping only — intrinsics-aware encoding is a non-goal
(notes.md; reference: cansik/space-stream).
"""

import logging
from typing import Optional

import numpy as np

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import CHOICES, FLOAT

logger = logging.getLogger(__name__)

# cv2.COLORMAP_* names offered in the panel; resolved lazily via
# getattr(cv2, f"COLORMAP_{name}") in the worker so cv2 stays a lazy import.
_COLORMAP_OPTIONS = ["TURBO", "JET", "VIRIDIS", "INFERNO", "MAGMA", "PLASMA", "HOT", "BONE"]

_RANGE_MODES = ["auto", "fixed"]


def colorize_depth(
    data: "np.ndarray | None",
    colormap: int,
    range_mode: str = "auto",
    min_depth_m: float = 0.3,
    max_depth_m: float = 8.0,
) -> "Optional[np.ndarray]":
    """Map a uint16-mm depth buffer to an (H, W, 3) uint8 BGR image.

    Pure function (no logging, no state) — the node's testable numeric core.

    - ``auto``: per-frame min/max over VALID (nonzero) pixels. A constant or
      all-invalid frame degrades gracefully (no divide-by-zero; all-invalid
      yields an all-black image, not ``None``).
    - ``fixed``: linear map of [*min_depth_m*, *max_depth_m*], clipped.
      A degenerate range (max <= min) widens by 1 mm instead of dividing by 0.
    - No-data (0) pixels are always black in the output.
    - Returns ``None`` for unanswerable input: no/empty/non-uint16-mm buffer
      (DEPTH_FRAME contract, see frame_type.py).
    """
    import cv2

    if (
        data is None
        or not isinstance(data, np.ndarray)
        or data.dtype != np.uint16
        or data.ndim != 2
        or data.size == 0
    ):
        return None

    valid = data > 0
    if range_mode == "fixed":
        lo = float(min_depth_m) * 1000.0
        hi = float(max_depth_m) * 1000.0
    else:
        if not valid.any():
            return np.zeros((*data.shape, 3), dtype=np.uint8)
        lo = float(data[valid].min())
        hi = float(data[valid].max())
    if hi <= lo:
        hi = lo + 1.0

    norm = np.clip((data.astype(np.float32) - lo) / (hi - lo), 0.0, 1.0)
    u8 = (norm * 255.0).astype(np.uint8)
    colored = cv2.applyColorMap(u8, colormap)  # BGR — the ecosystem's order
    colored[~valid] = 0
    return colored


@node(
    label="Colorize Depth",
    description="Maps a depth frame onto a colormap so it becomes viewable in the frame viewer",
    menu="vision/draw",
    search_tags=["depth", "colorize", "colormap", "turbo", "viewer", "visualize", "display"],
    node_type=NodeType.CONTROL,
)
class ColorizeDepthNode(BaseNode):
    """
    Colorizes a DEPTH_FRAME into a viewable frame.

    Inputs:
        execute: Control flow in — colorize the current frame.
        depth: DEPTH_FRAME (uint16 millimetres per pixel).

    Outputs:
        frame_ready: Pulsed when a colorized frame was produced.
        frame: The colorized frame (uint8, viewer-ready). Timestamp and
               frame number pass through from the depth frame.
    """

    class display(NodeSettings):
        colormap = setting[CHOICES](
            "TURBO",
            label="Colormap",
            category="Display",
            description="OpenCV colormap. TURBO is perceptually uniform (recommended).",
            widget_config={"options": _COLORMAP_OPTIONS},
        )
        range_mode = setting[CHOICES](
            "auto",
            label="Range Mode",
            category="Display",
            description=(
                "auto: normalize each frame over its valid pixels (zero-config, "
                "colors flicker between frames). fixed: map Min/Max Depth "
                "(stable, comparable colors)."
            ),
            widget_config={"options": _RANGE_MODES},
        )
        min_depth = setting[FLOAT](
            0.3,
            min=0.0,
            max=65.0,
            label="Min Depth (m)",
            category="Display",
            description="Near end of the fixed color range. Only used in fixed mode.",
            metadata={"enabled_when": ("range_mode", "fixed")},
        )
        max_depth = setting[FLOAT](
            8.0,
            min=0.0,
            max=65.0,
            label="Max Depth (m)",
            category="Display",
            description="Far end of the fixed color range. Only used in fixed mode.",
            metadata={"enabled_when": ("range_mode", "fixed")},
        )

    def init(self):
        from haybale_core.types import EXEC
        from ..types.frame_type import DEPTH_FRAME, RGB_FRAME

        self.add(EXEC.as_inlet("execute", label="Colorize"))
        self.add(DEPTH_FRAME.as_inlet("depth", label="Depth"))
        self.add(EXEC.as_outlet("frame_ready", label="Frame Ready"))
        self.add(RGB_FRAME.as_outlet("frame", label="Frame"))

    def post_init(self):
        self.hb_warned_invalid = False

    def worker(self, context: ExecutionContext, depth) -> Optional[str]:
        import cv2

        from ..types.frame_type import BaseFrame, RGB_FRAME

        data = depth.data if isinstance(depth, BaseFrame) else depth
        colormap = getattr(cv2, f"COLORMAP_{self.display.colormap}", cv2.COLORMAP_TURBO)
        colored = colorize_depth(
            data,
            colormap,
            range_mode=self.display.range_mode,
            min_depth_m=self.display.min_depth,
            max_depth_m=self.display.max_depth,
        )
        if colored is None:
            # No pulse: a viewer chain has nothing to branch on (unlike the
            # Sample Depth probe) — warn once and skip the frame.
            if not self.hb_warned_invalid:
                logger.warning(
                    "Colorize Depth received an invalid buffer (%s); DEPTH_FRAME "
                    "is uint16 millimetres by contract — skipping frames.",
                    None if data is None else getattr(data, "dtype", type(data)),
                )
                self.hb_warned_invalid = True
            return None

        timestamp = depth.timestamp if isinstance(depth, BaseFrame) else 0.0
        frame_number = depth.frame_number if isinstance(depth, BaseFrame) else 0
        self.out(
            "frame",
            RGB_FRAME(data=colored, timestamp=timestamp, frame_number=frame_number),
        )
        return "frame_ready"
```

- [ ] **Step 5: Run tests to verify they pass**

From haywire-repo:

Run: `uv run pytest barn/haybale-visiongraph/tests/ -v`
Expected: PASS — all Task 1 + Task 2 tests (24 total) green.

- [ ] **Step 6: Register the export**

In `barn/haybale-visiongraph/haybale_visiongraph/nodes/__init__.py`, add:

```python
from .colorize_depth_node import ColorizeDepthNode
```

and `"ColorizeDepthNode"` to `__all__`.

- [ ] **Step 7: Quality checks**

Run (from haybale-visiongraph):
```bash
uv run ruff check barn/haybale-visiongraph/
uv run ruff format --check barn/haybale-visiongraph/
uv run mypy barn/haybale-visiongraph/haybale_visiongraph/nodes/colorize_depth_node.py
```
From haywire-repo: `uv run pytest -m "not integration" -q`.
Expected: all clean/passing.

- [ ] **Step 8: Commit (haybale-visiongraph repo)**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/haybale_visiongraph/nodes/colorize_depth_node.py barn/haybale-visiongraph/haybale_visiongraph/nodes/__init__.py barn/haybale-visiongraph/tests/test_colorize_depth.py
git commit -m "feat(nodes): Colorize Depth — colormapped viewable frames from DEPTH_FRAME"
```

---

### Task 3: App verification + round-6 record in notes.md

**Files:**
- Modify: `barn/haybale-visiongraph/notes.md`

**Interfaces:**
- Consumes: both nodes from Tasks 1-2; the `enabled_when` behavior from the disabling rev-2 plan.
- Produces: nothing — documentation and verification.

- [ ] **Step 1: Verify in the running app (no hardware needed for most of it)**

From haywire-repo: `uv run haywire`.

1. Both nodes appear: `vision/measure → Sample Depth`, `vision/draw → Colorize Depth`.
2. **`enabled_when` dogfood (works without any camera):** open Colorize Depth's properties panel. With `Range Mode = auto`, `Min Depth`/`Max Depth` render disabled; switching to `fixed` enables them live, switching back disables them — no redraw.
3. Wiring sanity: `Sample Depth.depth` accepts only a `DEPTH_FRAME` outlet; `Colorize Depth.frame` wires into the `Frame Info Display` viewer.
4. **With an OAK-D attached** (hardware step — skip if unavailable and say so in the task report): camera → Frame Event (`depth=True`) → Colorize Depth → Frame Info Display shows a colormapped depth stream; Frame Event `frame_ready` → Sample Depth `sample` with the same depth edge reports a plausible `depth_m`, and pointing x/y at a hole (window=1) pulses `invalid` while `window=5` recovers.

- [ ] **Step 2: Append the round-6 record to notes.md**

Append to `barn/haybale-visiongraph/notes.md`:

```markdown
## Depth sampling + colorization (sixth round — BUILT)

Two nodes, both plain DEPTH_FRAME consumers on the existing event-node chain:

- **Sample Depth** (`vision/measure`): median Z-depth (meters) at a
  normalized 0-1 coordinate; `window` setting (median over k×k, ignoring
  0 = no-data) rescues depth holes; `sampled`/`invalid` EXEC outlets carry
  the outcome as control flow — `depth_m` never holds a sentinel.
- **Colorize Depth** (`vision/draw`): uint16-mm → colormapped viewer-ready
  frame; `range_mode` auto/fixed with `min_depth`/`max_depth` gated via
  `enabled_when: ("range_mode", "fixed")` — the first declarative consumer
  of the framework's reactive panel disabling. Explicitly a node, never an
  adapter (lossy + parameterized; see frame_type.py).

**Why no handle/probe node:** the originally sketched "OakDInput handle
outlet + Distance Probe" died under its own requirements analysis —
`cam.depth_buffer` on the event edge IS `_last_depth_frame`, the exact
buffer `OakDInput.distance()` reads, minus provenance (timestamp/frame
number) and plus a race. A DEPTH_FRAME sampler is camera-agnostic, needs no
requirement-union change (the event node's `depth=True` subscription is the
depth requirement), and its numeric core tests run on synthetic numpy with
no hardware. Revisit a handle only when a NON-frame query (IMU, device
temperature) has a concrete consumer.

**Vocabulary:** *depth* = Z-value at a pixel (what these nodes report).
*distance* = euclidean camera-to-point measure — requires camera
intrinsics; deferred, reference implementation:
https://github.com/cansik/space-stream (intrinsics-aware RGB-D encoding).
`OakDInput.distance()` is, by this vocabulary, misnamed — it returns depth.

**Channel order:** the viewer pipeline is BGR end-to-end (streaming_viewer
cv2.imencode's frames directly). RGB_FRAME's `data` is de-facto BGR despite
the type name; Colorize passes `cv2.applyColorMap` output through
unconverted. Don't "fix" this per-node — if it ever gets fixed, it's an
ecosystem-wide change.

**Non-goals (deliberate, with upgrade paths):** euclidean distance +
intrinsics outlet (space-stream); intrinsics-aware / reconstruction-grade
depth encoding (space-stream); device-handle query surface (until a
non-frame query exists); sensor-resolution micromanagement (reaffirmed).

**Test infra:** `barn/haybale-visiongraph/tests/` (first tests in this
repo) — pure-helper tests on synthetic buffers, run from the monorepo:
`uv run pytest barn/haybale-visiongraph/tests`. Not collected by the
monorepo's default run (testpaths + gitignored symlink, by design).
```

- [ ] **Step 3: Quality re-check**

Run (from haybale-visiongraph): `uv run ruff check barn/haybale-visiongraph/ && uv run ruff format --check barn/haybale-visiongraph/`
From haywire-repo: `uv run pytest barn/haybale-visiongraph/tests -q && uv run pytest -m "not integration" -q`
Expected: all clean/passing.

- [ ] **Step 4: Commit (haybale-visiongraph repo)**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph
git add barn/haybale-visiongraph/notes.md
git commit -m "docs(notes): round-6 record — depth sampling/colorization decisions, vocabulary, non-goals"
```

---

## Self-Review

**Spec coverage (against the inquisition decisions Q1-Q10):**
- ✅ Q1/Q2: no handle, no probe, no union change — neither node touches `oak_d_camera_node.py`; rationale recorded in notes.md.
- ✅ Q3: fixed uint16-mm contract — both helpers reject wrong dtype/ndim (`TestUnanswerable` in both test files); workers warn once.
- ✅ Q4: EXEC-driven workers, worker-returns-outlet-name — both nodes.
- ✅ Q5: normalized 0-1 coordinates, clamped, `OakDInput._calculate_depth_coordinates`-style rounding — `TestCoordinateMapping`.
- ✅ Q6: `window` setting, median-over-nonzero, even→odd normalization, edge clipping, default 1 — `TestWindow`.
- ✅ Q7: `sampled`/`invalid` branching; `depth_m` never a sentinel, holds last-good — Sample Depth worker + docstring. Colorize's no-branch variant (warn once + no pulse) stated with its reason.
- ✅ Q8: `range_mode` auto/fixed, `min_depth`/`max_depth` with `enabled_when` gating, TURBO default, zero-masked no-data, degenerate-range guards — Colorize node + `TestRangeMapping`; the dogfood is verified hardware-free in Task 3 Step 1.
- ✅ Q9: "Sample Depth"/`vision/measure`, "Colorize Depth"/`vision/draw`, `depth_m` naming; *distance* appears only in the notes.md deferral.
- ✅ Q10: all five non-goals recorded with upgrade paths in notes.md.
- ✅ BGR finding recorded and honored (no `cvtColor`).

**Placeholder scan:** none — literal code in every step, including full test files.

**Type consistency:** `sample_depth_m(data, x, y, window=1) -> Optional[float]` matches worker call and every test; `colorize_depth(data, colormap, range_mode, min_depth_m, max_depth_m) -> Optional[np.ndarray]` matches worker call (settings mapped positionally-by-name) and tests; both nodes' `worker(self, context, <inlet names>)` signatures match their declared inlet ids (`depth`, `x`, `y` / `depth`) per the framework's parameter-injection convention (`FrameDisplayNode.worker(self, context, frame)` precedent); `RGB_FRAME(data=..., timestamp=..., frame_number=...)` matches the `BaseFrame` dataclass fields.
