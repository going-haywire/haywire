# Edge appearance (design round D) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Computed edges (data, control, callback) take an arrow head and a width from a framework < graph default. A wire type names the end its computed head sits at. Fifteen heads draw as `context-stroke` markers on a path shortened by each head's inset. Every edge state colour comes from a theme token. A width, head or theme change restyles every edge in the browser, with no per-edge redraw.

**Architecture:**
- Rendering runs on CSS custom properties that `canvas.vue` sets on its SVG: `--hw-edge-width`, `--hw-edge-head` and `--hw-edge-hit-padding`. The values reach the canvas as Vue props:
  - the graph's `edge_arrow` and `edge_width`, through a new `GraphCanvasVue.set_edge_defaults`;
  - `edge_hit_padding`, through the existing `CanvasSettings` prop table;
  - the head table, once at mount.
- One stylesheet rule set draws every edge. The server stops sending a hard-coded invalid colour and the stroke width, and starts sending each edge's `arrowAt`.
- Nothing here touches a style bag. 5.4 later sets the same vars inline on a styled edge's path.

**Tech Stack:** Python 3.12, NiceGUI 3.13 (Vue 3 options API in `canvas.vue`), pytest (+ xdist; Playwright browser tier; NiceGUI `user_simulation`), uv, ruff, mypy.

**Settled in:** [2026-10-02-wire-types.md](2026-10-02-wire-types.md), section "D. Edge appearance" and decisions Q48 to Q62. 5.4's detail plan follows this one (Q56).

## Global Constraints

- **Repos.**
  - This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`.
  - haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked here as `barn/haybale-visiongraph`. Run git for it with `git -C ../haybale-visiongraph`.
- **Branch.** Continue on `wire-types-5-1` in both repos (5.1, 5.2 and their follow-ups are landed there, unmerged). Never push; the user pushes.
- **Commit trailer.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- **Never commit:** `docs/superpowers/`, `internals/`, `.superpowers/`, `.claude/settings.json`, and any probe file. Always `git add` explicit paths, never `-A` or `.`.
- **Commit `barn/haybale-testing/` first.** Commit every change there before running the full suite: `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown.
- **Intended behaviour changes.** These are the only ones. Any other red behavioural test is a bug: stop and report it.
  1. A computed edge draws the graph's head at the end its wire type names (`DataWire`, `ControlWire`: inlet; `CallbackWire`: outlet). The default head is `none`, so the default look is unchanged.
  2. A computed edge's width is the graph's `edge_width` (default 2). Selected adds `--hw-edge-selected-extra` (1px); active adds `--hw-edge-active-extra` (2px). These replace the fixed 3 and 4.
  3. The hit area is width + `CanvasSettings.edge_hit_padding` (default 8). This replaces the fixed 10.
  4. State colours read tokens:
     - invalid `--hw-danger` (the server stops sending `#EF4444`);
     - warning glow `--hw-warning`;
     - valid/refused drop target `--hw-success`/`--hw-danger`;
     - selected glow `--hw-edge-selected`;
     - active `--hw-edge-active`;
     - a missing pin colour `--hw-edge-default`, through `currentColor`.
  5. The sync payload drops `strokeWidth` and gains `arrowAt`.
- **Multi-canvas DOM.** Ids inside `canvas.vue` repeat in every mounted canvas (`.insights/project_multi_canvas_dom_globals.md`). Marker ids carry the canvas's `containerId`: `hw-head-<containerId>-<name>`.
- **SVG attributes and `var()`.** A presentation attribute (`stroke="…"`, `stop-color="…"`) cannot hold `var()`, and any stylesheet rule beats an attribute. Token colours therefore reach the edges through stylesheet rules, or through `currentColor` against the SVG's `color`.
- **Styles.** New rules go in `canvas.vue`'s existing `<style>` block, which already styles paths created with `createElementNS` (`.connection-active`). The browser tests in Tasks 7 and 8 prove each rule applies. If a computed style does not change, stop and report.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. Docstrings of registered components (widgets, settings) are displayed: Markdown, single backticks, no reST. Never write history words ("used to", "previously", "no longer").
- **Compare wire types by `.id`**, never with `is` or `issubclass` on the class. Comparing enum members (`WireRole`, the new `ArrowAt`) with `is` is fine.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`; line length 109.
- **Pre-commit gate:**
  - Run `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, then `grep -E "^FAILED|^ERROR" /tmp/t.log` and `tail -1 /tmp/t.log`.
  - Set the Bash timeout to at least 600000 ms.
  - Baseline before this plan: 6105 passed, 2 xfailed.
- **Browser tier:**
  - Run `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`.
  - Baseline: 144 passed.
  - One known intermittent failure, `test_edge_batch_cost`: rerun the tier once before calling it red.
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`. Baseline: 29 passed.
- **mypy set:** `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`. Baseline: clean.
- **Code lookup:** `codegraph explore "<symbols>"` returns verbatim source plus callers.

---

## File structure

| File | Change | Task |
|---|---|---|
| `packages/haywire-core/src/haywire/core/types/wire.py` | `ArrowAt`, `WireType.arrow_at` | 2 |
| `packages/haywire-core/src/haywire/barn/builtin/wires.py` | `CallbackWire.arrow_at = ArrowAt.OUTLET` | 2 |
| `packages/haywire-core/src/haywire/core/edge/arrow_heads.py` (new) | the head table, the single source | 3 |
| `packages/haywire-core/src/haywire/barn/builtin/widgets/arrow_head_widget.py` (new), `widgets/__init__.py`, `widget_keys.py` | `ArrowHeadWidget` | 4 |
| `packages/haywire-core/src/haywire/core/namespaces.py` | `NAMESPACE_UI_EDGE_DEFAULT`, `CATEGORY_EDGES` | 5 |
| `packages/haywire-core/src/haywire/core/edge/settings.py` (new) | `EdgeDefaultSettings` | 5 |
| `packages/haywire-core/src/haywire/core/graph/properties.py` | `edge_arrow`, `edge_width` | 5 |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py` | `arrow_at` in, `stroke_width` out; invalid colour | 6 |
| `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` | `SyncEdgeAdditionEvent` fields | 6 |
| `packages/haywire-core/src/haywire/ui/components/graph/settings.py` | `CanvasSettings.edge_hit_padding` | 6 |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.py` | head-table prop, `set_edge_defaults`, prop-table entry | 6 |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py` | subscribes to the two graph fields | 6 |
| `packages/haywire-core/src/haywire/ui/themes/workbench.py` | two optional width tokens | 7 |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` | vars, width rules, state colours, fallbacks; markers, `arrowAt`, insets | 7, 8 |
| `tests/ui/harness/routes.py`, `tests/ui/harness/test_edge_appearance.py` (new) | the browser fixture and tests | 7, 8 |
| docs, ADR 0045, glossary, generated library docs | | 9 |

---

### Task 0: Baseline (controller)

**Files:** none committed.

- [ ] **Step 1: Branch and tree.** Run `git branch --show-current && git status --short` in both repos. Expected: `wire-types-5-1` in both. The only uncommitted files are the user's plan edits under `docs/superpowers/` and `.claude/settings.json`.
- [ ] **Step 2: Baselines.** Run the ruff check on the whole repo, the mypy set, the pre-commit gate, the browser tier, the visiongraph tests and `uv run pytest -m perf -q`. Record the counts in the ledger. Expected: as in Global Constraints, perf 7 passed.

---

### Task 1: Verify first: markers, `context-stroke` and the width rule in real browsers

**Files:** a probe at `/tmp/d_probe/probe.py`, never committed. No repo change.

**Interfaces:** none. The task's output is a pass/fail table that later tasks rely on.

**Stop rule.**
- If any Chromium check fails, stop and report. The fallback, one marker per colour, is a design change.
- Firefox failures are reported but do not stop the plan.
- Playwright's WebKit is not installed in this environment. Do not install it. Report "WebKit not checked"; the live checks in Task 10 cover Safari if the user wants it.

- [ ] **Step 1: Write the probe**

Create `/tmp/d_probe/probe.py`:

```python
"""Verify-first probe for design round D. Scratch, never committed.

Run: uv run python /tmp/d_probe/probe.py
"""

import io

from PIL import Image
from playwright.sync_api import sync_playwright

HTML = """<!doctype html><html><body style="margin:0;background:#ffffff">
<svg id="s" width="300" height="130" style="--w: 6px">
 <defs>
  <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="20" y1="40" x2="260" y2="40">
   <stop offset="0%" stop-color="#ff0000"/><stop offset="100%" stop-color="#0000ff"/>
  </linearGradient>
  <marker id="tri" viewBox="-2 -4 9 8" refX="0" refY="0" markerWidth="9" markerHeight="8"
          markerUnits="strokeWidth" orient="auto-start-reverse" overflow="visible">
   <path d="M0,-3 L5,0 L0,3 Z" fill="context-stroke"/>
  </marker>
  <marker id="ring" viewBox="-2 -4 8.5 8" refX="0" refY="0" markerWidth="8.5" markerHeight="8"
          markerUnits="strokeWidth" orient="auto-start-reverse" overflow="visible">
   <circle cx="2.25" cy="0" r="1.75" fill="none" stroke="context-stroke" stroke-width="1"/>
  </marker>
 </defs>
 <style>
  #end { stroke-width: var(--w); marker-end: url(#tri); }
  #start { stroke-width: var(--w); marker-start: url(#tri); }
  #hollow { stroke-width: var(--w); marker-end: url(#ring); }
 </style>
 <path id="end" d="M20,40 L230,40" stroke="url(#g)" fill="none"/>
 <path id="start" d="M50,80 L260,80" stroke="#00aa00" fill="none"/>
 <path id="hollow" d="M20,110 L200,110" stroke="#00aa00" fill="none"/>
</svg></body></html>"""


def _pixel(shot: bytes, x: int, y: int) -> tuple[int, int, int]:
    image = Image.open(io.BytesIO(shot)).convert("RGB")
    return image.getpixel((x, y))


def run(browser_type) -> dict[str, bool]:
    browser = browser_type.launch()
    page = browser.new_page(viewport={"width": 320, "height": 140})
    page.set_content(HTML)
    shot = page.screenshot()
    results = {}
    # The end head spans x 230..260 (5 units x 6px); the gradient there is blue.
    r, g, b = _pixel(shot, 250, 40)
    results["gradient head takes the end colour"] = b > 150 and r < 120
    # marker-start with auto-start-reverse points back over x 20..50.
    r, g, b = _pixel(shot, 30, 80)
    results["start head is drawn and points back"] = g > 120 and r < 100 and b < 100
    # No stroke-width attribute: the stylesheet rule's var() decides.
    width = page.evaluate("() => getComputedStyle(document.getElementById('end')).strokeWidth")
    results["CSS width rule applies without the attribute"] = width == "6px"
    # Hollow ring: its centre (200 + 2.25 x 6) shows the white background.
    r, g, b = _pixel(shot, 213, 110)
    results["hollow head is hollow"] = min(r, g, b) > 200
    browser.close()
    return results


with sync_playwright() as p:
    for name in ("chromium", "firefox", "webkit"):
        try:
            outcome = run(getattr(p, name))
        except Exception as exc:  # a browser that is not installed
            print(f"{name}: not checked ({type(exc).__name__})")
            continue
        for check, ok in outcome.items():
            print(f"{name}: {'PASS' if ok else 'FAIL'} - {check}")
```

- [ ] **Step 2: Run it**

Run: `uv run python /tmp/d_probe/probe.py`
Expected: four `chromium: PASS` lines; four `firefox:` lines; `webkit: not checked`.

If a pixel check fails, save the screenshot (`page.screenshot(path="/tmp/d_probe/<browser>.png")`) and look at it before reporting. A check can fail because a coordinate is off, not because of the browser.

- [ ] **Step 3: Report.** Write the table into the report. Nothing is committed in this task.

---

### Task 2: `WireType.arrow_at`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/wire.py`, `packages/haywire-core/src/haywire/barn/builtin/wires.py`, and the module that re-exports `WireRole` (`packages/haywire-core/src/haywire/core/types/__init__.py`).
- Test: create `tests/core/test_types/test_arrow_at.py`.

**Interfaces:**
- Produces:
  - `ArrowAt(Enum)` with members `INLET = "inlet"`, `OUTLET = "outlet"`, `NONE = "none"`, exported from `haywire.core.types` next to `WireRole`;
  - `WireType.arrow_at: ClassVar[ArrowAt] = ArrowAt.INLET`;
  - `CallbackWire.arrow_at = ArrowAt.OUTLET`.
- The enum values are the canvas class suffixes `edge-arrow-inlet`, `edge-arrow-outlet` and `edge-arrow-none` (Task 8).

- [ ] **Step 1: Write the failing test**

```python
"""Where a computed edge draws its arrow head: a fact its wire type declares."""

import pytest

from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire
from haywire.core.types import ArrowAt

pytestmark = pytest.mark.unit


def test_a_wire_type_draws_its_computed_head_at_the_inlet_by_default():
    assert DataWire.arrow_at is ArrowAt.INLET
    assert ControlWire.arrow_at is ArrowAt.INLET


def test_a_callback_edge_draws_its_head_at_the_outlet():
    assert CallbackWire.arrow_at is ArrowAt.OUTLET


def test_the_values_are_the_canvas_class_suffixes():
    assert [member.value for member in ArrowAt] == ["inlet", "outlet", "none"]
```

- [ ] **Step 2: Run it.** `uv run pytest tests/core/test_types/test_arrow_at.py -q`. Expected: FAIL, `ImportError: cannot import name 'ArrowAt'`.

- [ ] **Step 3: Implement**

In `wire.py`, after `WireRole`:

```python
class ArrowAt(Enum):
    """The end of a computed edge its arrow head is drawn at.

    A computed edge's wire type declares no style bag; its head comes from the
    graph's edge defaults and sits where the wire type's ``arrow_at`` says.

    - ``INLET``: at the inlet, pointing into it.
    - ``OUTLET``: at the outlet, pointing into it.
    - ``NONE``: no head, whatever the graph sets.
    """

    INLET = "inlet"
    OUTLET = "outlet"
    NONE = "none"
```

In `WireType`:
- Add the class attribute after `pin_kind`: `arrow_at: ClassVar[ArrowAt] = ArrowAt.INLET`.
- Add this entry to the `Attributes:` list after `pin_kind`:

  ```text
  arrow_at: The end a computed edge of this wire type draws its arrow head at;
      see ``ArrowAt``.
  ```

In `wires.py`:
- Import `ArrowAt` from `haywire.core.types.wire`.
- In `CallbackWire`, add `arrow_at = ArrowAt.OUTLET`.
- Replace its docstring with:

  ```text
  Subscriptions, which take effect as soon as they are written.

  A computed head points at the outlet: the listener the callback returns to.
  ```

Export `ArrowAt` wherever `WireRole` is exported in `haywire/core/types/__init__.py`, both the import and `__all__`.

- [ ] **Step 4: Run, ruff check, mypy.** `uv run pytest tests/core/test_types/test_arrow_at.py tests/core/test_types/test_wire.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/types/wire.py packages/haywire-core/src/haywire/core/types/__init__.py packages/haywire-core/src/haywire/barn/builtin/wires.py tests/core/test_types/test_arrow_at.py
git commit -m "feat(wires): a wire type names the end its computed arrow head sits at

ArrowAt (inlet, outlet, none) and WireType.arrow_at, inlet by default.
CallbackWire draws its head at the outlet: the listener the callback
returns to.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The head table

**Files:**
- Create: `packages/haywire-core/src/haywire/core/edge/arrow_heads.py`. `haywire/core/edge/` is a namespace package with no `__init__.py`; keep it that way.
- Test: create `tests/core/test_edge/test_arrow_heads.py`.

**Interfaces:**
- Produces, in `haywire.core.edge.arrow_heads`:
  - `NO_HEAD = "none"`;
  - `ArrowHead`, a frozen dataclass with fields `name`, `label`, `common`, `inset`, `svg`, and the method `to_payload() -> dict`, whose keys are `name`, `inset`, `svg`, `view_box`, `width`, `height`;
  - `ARROW_HEADS: tuple[ArrowHead, ...]`, fifteen entries in picker order;
  - `get_arrow_head(name: str | None) -> ArrowHead | None`.

- [ ] **Step 1: Write the failing tests**

```python
"""The arrow-head vocabulary: one table for the canvas markers and the picker."""

import pytest

from haywire.core.edge.arrow_heads import ARROW_HEADS, NO_HEAD, ArrowHead, get_arrow_head

pytestmark = pytest.mark.unit


def test_fifteen_heads_with_unique_names():
    names = [head.name for head in ARROW_HEADS]
    assert len(names) == 15
    assert len(set(names)) == 15
    assert NO_HEAD not in names


def test_the_picker_shows_four_common_arrows_first():
    assert [head.name for head in ARROW_HEADS if head.common] == ["arrow", "sharp", "open", "triangle"]


@pytest.mark.parametrize("head", ARROW_HEADS, ids=lambda h: h.name)
def test_a_head_paints_with_the_edge_stroke_only(head: ArrowHead):
    assert head.inset > 0
    assert "context-stroke" in head.svg
    assert "#" not in head.svg  # no literal colour: a head takes the edge's paint


def test_lookup_answers_none_for_no_head_and_unknown_names():
    assert get_arrow_head(NO_HEAD) is None
    assert get_arrow_head("not-a-head") is None
    assert get_arrow_head(None) is None
    head = get_arrow_head("open")
    assert head is not None and head.label == "Open arrow"  # noqa: PT018


def test_the_payload_carries_the_marker_geometry():
    head = get_arrow_head("triangle")
    assert head is not None
    assert head.to_payload() == {
        "name": "triangle",
        "inset": 5.0,
        "svg": head.svg,
        "view_box": "-2 -4 9.0 8",
        "width": 9.0,
        "height": 8,
    }
```

- [ ] **Step 2: Run it.** `uv run pytest tests/core/test_edge/test_arrow_heads.py -q`. Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Arrow heads: the vocabulary of glyphs an edge can draw at either end.

One table is the single source for the canvas markers and the
``ArrowHeadWidget`` previews. Coordinates are in edge widths
(``markerUnits="strokeWidth"``): a head is drawn from its attach point at
x = 0, where the shortened edge ends, to its tip at x = ``inset``, which
touches the pin. The canvas shortens the edge by ``inset × width`` at every end
that has a head, so no head overlaps its line. A head paints with
``context-stroke``, so it takes the stroke of the edge that draws it.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The value meaning "no head", as stored in a setting.
NO_HEAD = "none"

# Space around a glyph inside its marker viewport, in edge widths.
_PAD = 2
_HALF_HEIGHT = 4


@dataclass(frozen=True)
class ArrowHead:
    """One arrow head: its stored name, the label the picker shows, and its glyph.

    Attributes:
        name: The value a setting stores, such as ``"open"``.
        label: What the picker shows.
        common: Shown before the picker's "More" item.
        inset: The glyph's length in edge widths; the edge ends this far before the pin.
        svg: The glyph's SVG children, painted with ``context-stroke``.
    """

    name: str
    label: str
    common: bool
    inset: float
    svg: str

    def to_payload(self) -> dict:
        """Return what the canvas needs to build this head's ``<marker>``."""
        width = self.inset + 2 * _PAD
        return {
            "name": self.name,
            "inset": self.inset,
            "svg": self.svg,
            "view_box": f"{-_PAD} {-_HALF_HEIGHT} {width} {2 * _HALF_HEIGHT}",
            "width": width,
            "height": 2 * _HALF_HEIGHT,
        }


def _fill(d: str) -> str:
    return f'<path d="{d}" fill="context-stroke"/>'


def _line(d: str) -> str:
    return f'<path d="{d}" fill="none" stroke="context-stroke" stroke-width="1" stroke-linejoin="round"/>'


def _disc(cx: float, r: float) -> str:
    return f'<circle cx="{cx}" cy="0" r="{r}" fill="context-stroke"/>'


def _ring(cx: float, r: float) -> str:
    return f'<circle cx="{cx}" cy="0" r="{r}" fill="none" stroke="context-stroke" stroke-width="1"/>'


_CROW = "M{x},0 L{tip},-3 M{x},0 L{tip},0 M{x},0 L{tip},3"

ARROW_HEADS: tuple[ArrowHead, ...] = (
    ArrowHead("arrow", "Arrow", True, 4.5, _fill("M0,-2.25 L4.5,0 L0,2.25 Z")),
    ArrowHead("sharp", "Sharp arrow", True, 4.0, _fill("M0,0 L-1.2,-2.5 L4,0 L-1.2,2.5 Z")),
    ArrowHead("open", "Open arrow", True, 4.0, _line("M0,-2.5 L3.5,0 L0,2.5 M0,0 L3.5,0")),
    ArrowHead("triangle", "Triangle", True, 5.0, _fill("M0,-3 L5,0 L0,3 Z")),
    ArrowHead("triangle_hollow", "Hollow triangle", False, 5.0, _line("M0.5,-2.7 L4.5,0 L0.5,2.7 Z")),
    ArrowHead("diamond", "Diamond", False, 6.0, _fill("M0,0 L3,-2.5 L6,0 L3,2.5 Z")),
    ArrowHead("diamond_hollow", "Hollow diamond", False, 6.0, _line("M0.5,0 L3,-2.1 L5.5,0 L3,2.1 Z")),
    ArrowHead("circle", "Circle", False, 4.5, _disc(2.25, 2.25)),
    ArrowHead("circle_hollow", "Hollow circle", False, 4.5, _ring(2.25, 1.75)),
    ArrowHead("bar", "Bar", False, 2.5, _line("M0,0 L2.5,0 M1,-3 L1,3")),
    ArrowHead("many", "Many", False, 4.0, _line(_CROW.format(x=0, tip=4))),
    ArrowHead(
        "one_or_many", "One or many", False, 5.5, _line("M0,0 L5.5,0 M1,-3 L1,3 " + _CROW.format(x=1.5, tip=5.5))
    ),
    ArrowHead("one_only", "Exactly one", False, 4.0, _line("M0,0 L4,0 M1,-3 L1,3 M2.5,-3 L2.5,3")),
    ArrowHead("zero_or_many", "Zero or many", False, 7.5, _ring(1.75, 1.25) + _line(_CROW.format(x=3.5, tip=7.5))),
    ArrowHead("zero_or_one", "Zero or one", False, 6.0, _ring(1.75, 1.25) + _line("M3.5,0 L6,0 M4.75,-3 L4.75,3")),
)

_BY_NAME = {head.name: head for head in ARROW_HEADS}


def get_arrow_head(name: str | None) -> ArrowHead | None:
    """Return the head called *name*; ``None`` for ``NO_HEAD``, ``None`` or an unknown name."""
    if name is None:
        return None
    return _BY_NAME.get(name)
```

Keep the coordinates as written. Each glyph's outer edge lies at x = 0 and its tip at x = `inset`, with half-stroke and round joins taken into account. Task 10's live check confirms the line meets each glyph's edge.

- [ ] **Step 4: Run, ruff check, mypy.** Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/edge/arrow_heads.py tests/core/test_edge/test_arrow_heads.py
git commit -m "feat(edges): the arrow-head vocabulary, one table for markers and picker

Fifteen heads in edge-width units, each painted with context-stroke and
spanning x = 0 (where the shortened edge ends) to x = inset (the pin).

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `ArrowHeadWidget`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/widgets/arrow_head_widget.py`.
- Modify:
  - `packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py` (import and `__all__`);
  - `packages/haywire-core/src/haywire/barn/builtin/widget_keys.py` (the key constant).
- Test: create `tests/ui/widget/test_arrow_head_widget.py`. Also extend `tests/core/test_widget_keys.py` if it lists the constants explicitly.

**Interfaces:**
- Consumes: Task 3's `ARROW_HEADS`, `NO_HEAD`, `ArrowHead`, `get_arrow_head`.
- Produces:
  - `ArrowHeadWidget`, registered as `haywire-core:widget:ArrowHeadWidget` (the builtin library scans the `widgets/` folder);
  - `ARROW_HEAD_WIDGET = "haywire-core:widget:ArrowHeadWidget"` in `widget_keys.py`;
  - `preview_svg(head: ArrowHead | None) -> str`.
- Element markers:
  - each pick is `arrow-head-<name>`, including `arrow-head-none`;
  - the reveal item is `arrow-head-more`.

- [ ] **Step 1: Write the failing tests**

```python
"""ArrowHeadWidget: None and the common arrows first; More reveals every head."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets.arrow_head_widget import ArrowHeadWidget, preview_svg
from haywire.core.edge.arrow_heads import get_arrow_head
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


def _port() -> DataPort:
    port = DataPort(
        registry_id="head",
        registry_key=STRING.class_identity.registry_key,
        label="Head",
        id="head",
        type_cls=STRING,
        port_type=PortType.INLET,
    )
    port.set_value("none")
    return port


@pytest.mark.unit
def test_a_preview_draws_the_glyph_in_the_current_colour():
    svg = preview_svg(get_arrow_head("triangle"))
    assert "currentColor" in svg
    assert "context-stroke" not in svg
    assert "M0,-3 L5,0 L0,3 Z" in svg


@pytest.mark.unit
@pytest.mark.anyio
async def test_picking_a_common_head_stores_its_name(user: User) -> None:
    port = _port()

    @ui.page("/")
    def page() -> None:
        ArrowHeadWidget(port).render()

    await user.open("/")
    user.find(marker="arrow-head-open").click()

    assert port.get_value() == "open"


@pytest.mark.unit
@pytest.mark.anyio
async def test_more_reveals_the_rest_of_the_heads(user: User) -> None:
    port = _port()

    @ui.page("/")
    def page() -> None:
        ArrowHeadWidget(port).render()

    await user.open("/")
    await user.should_not_see(marker="arrow-head-zero_or_one")
    user.find(marker="arrow-head-more").click()
    user.find(marker="arrow-head-zero_or_one").click()

    assert port.get_value() == "zero_or_one"


@pytest.mark.unit
@pytest.mark.anyio
async def test_the_button_previews_the_stored_head(user: User) -> None:
    port = _port()
    captured: dict[str, ArrowHeadWidget] = {}

    @ui.page("/")
    def page() -> None:
        captured["widget"] = ArrowHeadWidget(port)
        captured["widget"].render()

    await user.open("/")
    port.set_value("diamond")

    head = get_arrow_head("diamond")
    assert head is not None
    assert captured["widget"]._preview.content == preview_svg(head)
```

If `user.should_not_see(marker=...)` does not take a marker in NiceGUI 3.13, assert with `user.find(marker=...)` raising instead. Change only the call; keep what it asserts.

- [ ] **Step 2: Run it.** `uv run pytest tests/ui/widget/test_arrow_head_widget.py -q`. Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""ArrowHeadWidget — picks an arrow head from the shared head vocabulary."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.core.edge.arrow_heads import ARROW_HEADS, NO_HEAD, ArrowHead, get_arrow_head
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget


def preview_svg(head: ArrowHead | None) -> str:
    """Return an inline SVG of *head* at the end of a short line, drawn in ``currentColor``.

    ``None`` draws the line alone. The glyph is the head's own markup with
    ``context-stroke`` swapped for ``currentColor``, since ``context-stroke``
    paints only inside a marker.
    """
    inset = head.inset if head is not None else 6.0
    glyph = head.svg.replace("context-stroke", "currentColor") if head is not None else ""
    line_end = 0 if head is not None else inset
    return (
        f'<svg width="44" height="16" viewBox="-8 -4 {8 + inset + 1} 8" style="overflow: visible">'
        f'<path d="M-8,0 L{line_end},0" stroke="currentColor" stroke-width="1" fill="none"/>'
        f"{glyph}</svg>"
    )


@widget(description="Arrow head picker")
class ArrowHeadWidget(BaseWidget):
    """Picks the arrow head an edge draws at one end.

    The button shows the current head. Its menu lists *None* and the four
    common arrows; *More* reveals every head. The value is the head's name,
    or `none` for no head.
    """

    def build(self) -> Any:
        button = ui.button().props("flat dense no-caps").classes("w-full")
        with button:
            self._preview = ui.html("")
            with ui.menu() as self._menu:
                with ui.grid(columns=5).classes("p-1 gap-0"):
                    self._item(None)
                    for head in ARROW_HEADS:
                        if head.common:
                            self._item(head)
                self._more = (
                    ui.button("More", on_click=self._show_all)
                    .props("flat dense no-caps")
                    .classes("w-full")
                    .mark("arrow-head-more")
                )
                with ui.grid(columns=5).classes("p-1 gap-0") as self._all:
                    for head in ARROW_HEADS:
                        if not head.common:
                            self._item(head)
                self._all.set_visibility(False)
        return button

    def _item(self, head: ArrowHead | None) -> None:
        name = head.name if head is not None else NO_HEAD
        label = head.label if head is not None else "None"
        with (
            ui.button(on_click=lambda _, n=name: self._pick(n))
            .props("flat dense")
            .tooltip(label)
            .mark(f"arrow-head-{name}")
        ):
            ui.html(preview_svg(head))

    def _show_all(self) -> None:
        self._all.set_visibility(True)
        self._more.set_visibility(False)

    def _pick(self, name: str) -> None:
        self._menu.close()
        self.set_value(name)

    def on_model_changed(self, value: Any) -> None:
        """Show the stored head on the button."""
        self._preview.set_content(preview_svg(get_arrow_head(value)))
```

`ui.html` here passes no `sanitize` argument, the same as `haybale_testing/widgets/oversized_content_widget.py:40` does on NiceGUI 3.13. If it warns or raises, follow that call's exact form.

Then:
- In `widget_keys.py`, add `ARROW_HEAD_WIDGET = "haywire-core:widget:ArrowHeadWidget"`.
- In `widgets/__init__.py`, import and export `ArrowHeadWidget`.

- [ ] **Step 4: Run, ruff check, mypy.** Run `uv run pytest tests/ui/widget/test_arrow_head_widget.py tests/core/test_widget_keys.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/widgets/arrow_head_widget.py packages/haywire-core/src/haywire/barn/builtin/widgets/__init__.py packages/haywire-core/src/haywire/barn/builtin/widget_keys.py tests/ui/widget/test_arrow_head_widget.py
git commit -m "feat(widgets): ArrowHeadWidget, common arrows first and More for the rest

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

Add `tests/core/test_widget_keys.py` to the commit if you changed it.

---

### Task 5: Edge defaults: framework < graph

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/namespaces.py`, `packages/haywire-core/src/haywire/core/graph/properties.py`.
- Create: `packages/haywire-core/src/haywire/core/edge/settings.py`.
- Test: create `tests/core/test_graph/test_edge_defaults.py`.

**Interfaces:**
- Consumes: Task 4's `ARROW_HEAD_WIDGET` key constant. Core references the widget by key, not by importing the NiceGUI class.
- Produces:
  - `EdgeDefaultSettings` with fields `arrow` (`STRING`, default `"none"`) and `width` (`FLOAT`, default `2.0`). Registry keys: `ui.edge.default.arrow`, `ui.edge.default.width`.
  - `GraphProperties.edge_arrow` and `GraphProperties.edge_width`, each `shadow()`ing the field above.

- [ ] **Step 1: Write the failing tests**

```python
"""Edge defaults: a graph's computed edges take their head and width from framework < graph."""

import pytest

from haywire.barn.builtin.widget_keys import ARROW_HEAD_WIDGET
from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph

ARROW_KEY = "ui.edge.default.arrow"
WIDTH_KEY = "ui.edge.default.width"


@pytest.fixture(autouse=True)
def _clean_framework_tier(library_system):
    """The registry is process-shared: clear the framework tier around every test."""
    registry = get_settings_registry()
    for key in (ARROW_KEY, WIDTH_KEY):
        registry.reset_global(key)
    yield
    for key in (ARROW_KEY, WIDTH_KEY):
        registry.reset_global(key)


@pytest.mark.integration
class TestEdgeDefaults:
    def test_a_graph_starts_with_todays_look(self, graph_with_library_system):
        props = graph_with_library_system.props
        assert props.edge_arrow == "none"
        assert props.edge_width == 2.0

    def test_an_unset_graph_tracks_the_studio_value(self, graph_with_library_system):
        get_settings_registry().set_global(ARROW_KEY, "arrow")
        get_settings_registry().set_global(WIDTH_KEY, 3.0)

        assert graph_with_library_system.props.edge_arrow == "arrow"
        assert graph_with_library_system.props.edge_width == 3.0

    def test_a_graph_value_wins_and_reset_falls_back(self, graph_with_library_system):
        props = graph_with_library_system.props
        get_settings_registry().set_global(ARROW_KEY, "arrow")
        props.edge_arrow = "open"
        assert props.edge_arrow == "open"

        props._reset("edge_arrow")
        assert props.edge_arrow == "arrow"

    def test_a_graph_value_survives_save_and_load(self, graph_with_library_system):
        graph_with_library_system.props.edge_width = 3.5
        data = graph_with_library_system.to_dict()

        loaded = BaseGraph(filestem="G2")
        assert loaded.load_from_dict(data) is True
        assert loaded.props.edge_width == 3.5
        assert not loaded.props._is_locally_set("edge_arrow")

    def test_both_tiers_pick_the_head_with_the_arrow_head_widget(self, graph_with_library_system):
        from haywire.core.edge.settings import EdgeDefaultSettings

        graph_fields = type(graph_with_library_system.props)._settings_descriptors()
        assert graph_fields["edge_arrow"].widget_key == ARROW_HEAD_WIDGET
        assert EdgeDefaultSettings._settings_descriptors()["arrow"].widget_key == ARROW_HEAD_WIDGET
```

- [ ] **Step 2: Run it.** `uv run pytest tests/core/test_graph/test_edge_defaults.py -q`. Expected: FAIL, `AttributeError: … edge_arrow`.

- [ ] **Step 3: Implement**

`namespaces.py`, next to the other `NAMESPACE_UI_*` and `CATEGORY_*` constants:

```python
NAMESPACE_UI_EDGE_DEFAULT = "ui.edge.default"
CATEGORY_EDGES = "edges"
```

`packages/haywire-core/src/haywire/core/edge/settings.py`:

```python
"""Edge defaults: the arrow head and width computed edges draw with, before a graph overrides them.

A pure ``FrameworkSettings`` schema in core, because ``GraphProperties`` (core)
shadows it and core never imports ui. The canvas reads the effective values
from ``GraphProperties``.
"""

from haywire.barn.builtin.types import FLOAT, STRING
from haywire.barn.builtin.widget_keys import ARROW_HEAD_WIDGET
from haywire.core.namespaces import CATEGORY_EDGES, NAMESPACE_UI_EDGE_DEFAULT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class EdgeDefaultSettings(FrameworkSettings, namespace=NAMESPACE_UI_EDGE_DEFAULT):
    """How computed edges look in the studio, before a graph overrides it.

    A computed edge is one whose wire type declares no style bag: data, control
    and callback edges. Its colour comes from its pins and its dash from its
    adapter chain. Its arrow head and width come from here, and each graph may
    override both.
    """

    arrow = setting[STRING](
        "none",
        label="Edge Arrow",
        description="Arrow head computed edges draw, at the end their wire type names",
        category=CATEGORY_EDGES,
        widget={"key": ARROW_HEAD_WIDGET},
    )
    width = setting[FLOAT](
        2.0,
        label="Edge Width",
        description="Line width of computed edges, in pixels",
        category=CATEGORY_EDGES,
        min=0.5,
        max=12.0,
    )
```

`properties.py`: import `EdgeDefaultSettings` and `ARROW_HEAD_WIDGET`, then append to `GraphProperties`:

```python
    edge_arrow = shadow(
        src=EdgeDefaultSettings.arrow,
        label="Edge Arrow",
        description=(
            "Arrow head on the computed edges of THIS graph. Overrides the "
            "studio default."
        ),
        category="appearance",
        order=40,
        widget={"key": ARROW_HEAD_WIDGET},
    )

    edge_width = shadow(
        src=EdgeDefaultSettings.width,
        label="Edge Width",
        description=(
            "Line width of the computed edges in THIS graph. Overrides the "
            "studio default."
        ),
        category="appearance",
        order=50,
    )
```

- If `shadow()` does not accept `widget=`, check how a mirror gets its widget (`_stamp_widget` in `haywire/core/settings/descriptor.py`) and pass the key the way that code reads it. Keep the test.
- If `setting[STRING](…, widget={"key": …})` needs a `"config"` entry, add `"config": {}`.
- Fix any import cycle the new core module causes by matching how `haywire/core/skin/settings.py` imports from `haywire.barn.builtin`.

- [ ] **Step 4: Run, ruff check, mypy.** `uv run pytest tests/core/test_graph/test_edge_defaults.py tests/core/test_node -q -n 4`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/namespaces.py packages/haywire-core/src/haywire/core/edge/settings.py packages/haywire-core/src/haywire/core/graph/properties.py tests/core/test_graph/test_edge_defaults.py
git commit -m "feat(settings): edge defaults, studio < graph, for computed edges

EdgeDefaultSettings (ui.edge.default: arrow, width) and two GraphProperties
fields that shadow it. The defaults are today's look: no head, width 2.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Server side: payload, canvas props, the graph subscription

**Files:**
- Modify:
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py`
  - `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` (`SyncEdgeAdditionEvent`)
  - `packages/haywire-core/src/haywire/ui/components/graph/settings.py` (`CanvasSettings`)
  - `packages/haywire-core/src/haywire/ui/components/graph/canvas.py`
  - `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py`
- Test:
  - modify `tests/ui/test_canvas_handlers/test_edge_sync_payload.py`;
  - create `tests/ui/test_canvas_handlers/test_edge_visual_state.py` and `tests/ui/test_canvas_edge_props.py`.

**Interfaces:**
- Consumes: Task 2's `ArrowAt`, Task 3's `ARROW_HEADS`, Task 5's `GraphProperties.edge_arrow` and `edge_width`.
- Produces:
  - `EdgeVisualState` loses `stroke_width` and gains `arrow_at: str` (an `ArrowAt` value), which takes part in `__eq__`;
  - `SyncEdgeAdditionEvent` loses `strokeWidth` and gains `arrowAt: str = "inlet"`;
  - `CanvasSettings.edge_hit_padding: INT = 8`, mapped to prop `edge-hit-padding`;
  - `GraphCanvasVue` sets the prop `arrow-heads` once at construction, a list of `ArrowHead.to_payload()`;
  - `GraphCanvasVue.set_edge_defaults(arrow: str, width: float) -> None` sets props `edge-arrow` and `edge-width`.

- [ ] **Step 1: Write the failing tests**

In `test_edge_sync_payload.py`:
- In `_state()`, drop `stroke_width=2` and add `arrow_at="inlet"`.
- In `test_batch_entry_carries_the_wrapper_and_state_values`, replace `assert payload["strokeWidth"] == 2` with `assert payload["arrowAt"] == "inlet"`.

Create `tests/ui/test_canvas_handlers/test_edge_visual_state.py`:

```python
"""An edge's visual state: where its computed head sits, and no hard-coded state colour."""

import pytest

from haybale_graph_editor.editors.graph_canvas.ui_edge import edge_visual_state
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def test_a_data_edge_draws_its_head_at_the_inlet(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source, sink = make_node(graph, key), make_node(graph, key)
    edge = make_edge(graph, source.node_id, "result", sink.node_id, "value_a")
    graph.force_validation()

    assert edge_visual_state(edge).arrow_at == "inlet"


def test_a_callback_edge_draws_its_head_at_the_outlet(graph_with_library_system):
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    graph = graph_with_library_system
    listener = make_node(graph, TestCustomCallbackNode.class_identity.registry_key)
    emitter = make_node(graph, TestEmitCallbackNode.class_identity.registry_key)
    edge = make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    graph.force_validation()

    assert edge_visual_state(edge).arrow_at == "outlet"


def test_an_invalid_edge_leaves_its_colour_to_the_theme(graph_with_library_system):
    from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

    graph = graph_with_library_system
    key = AddPortTestNode.class_identity.registry_key
    source, sink = make_node(graph, key), make_node(graph, key)
    edge = graph.create_edge_wrapper(source.node_id, "add_out_0", sink.node_id, "add_in_0")
    assert edge is not None
    graph._validation.force_immediate_validation()

    state = edge_visual_state(edge)
    assert state.is_valid is False
    assert state.stroke_color == "auto"
```

Create `tests/ui/test_canvas_edge_props.py`:

```python
"""Canvas props behind edge appearance: the hit padding setting and the head table."""

import pytest

from haywire.ui.components.graph.canvas import _CANVAS_SETTING_PROPS
from haywire.ui.components.graph.settings import CanvasSettings

pytestmark = pytest.mark.unit


def test_the_hit_padding_reaches_the_canvas_as_a_prop():
    assert _CANVAS_SETTING_PROPS["edge_hit_padding"] == "edge-hit-padding"
    assert CanvasSettings._settings_descriptors()["edge_hit_padding"].default == 8
```

If a descriptor's default is not exposed as `.default`, read it the way `tests/core/test_settings` reads descriptor defaults. Keep the assertion that the default is 8.

- [ ] **Step 2: Run them.** `uv run pytest tests/ui/test_canvas_handlers tests/ui/test_canvas_edge_props.py -q`. Expected: FAIL. `EdgeVisualState` has no `arrow_at` and still requires `stroke_width`, and the prop mapping is missing.

- [ ] **Step 3: `ui_edge.py`**

`EdgeVisualState`:
- Remove `stroke_width: int`.
- Add `arrow_at: str` after `opacity`, with the comment `# ArrowAt value: the end a computed head is drawn at`.
- In `__eq__`, drop the `stroke_width` comparison and add `and self.arrow_at == other.arrow_at`.
- Add one docstring line: "`arrow_at` takes part, because a rebuild can change the wire type."

`edge_visual_state`:
- Compute once, at the top:

```python
    wire = wrapper.wire_type
    arrow_at = wire.arrow_at.value if wire is not None else ArrowAt.INLET.value
```

- Import `ArrowAt` from `haywire.core.types`.
- In each of the three returns, drop `stroke_width=2` and pass `arrow_at=arrow_at`.
- In the INVALID return, `stroke_color="#EF4444"` becomes `stroke_color="auto"`, with the comment `# The canvas paints an invalid edge with the --hw-danger token`.
- Update the docstring's state list: "INVALID: dashed, reduced opacity, drawn in the theme's danger colour by the canvas".

`edge_sync_payload`: replace `"strokeWidth": state.stroke_width,` with `"arrowAt": state.arrow_at,`.

- [ ] **Step 4: `SyncEdgeAdditionEvent`**

- Replace `strokeWidth: int = 2` with `arrowAt: str = "inlet"  # ArrowAt value: where a computed head sits`.
- In the docstring, replace the `strokeWidth` bullet with `- arrowAt: The end a computed edge's arrow head sits at (inlet, outlet, none)`.

`generated/graph_events.js` holds event names only, so it does not change.

- [ ] **Step 5: `CanvasSettings` and `canvas.py`**

Append to `CanvasSettings`:

```python
    edge_hit_padding = setting[INT](
        8,
        label="Edge Hit Padding",
        description="Clickable width around an edge beyond its line, in pixels",
        category="ui.canvas",
        min=0,
        max=24,
    )
```

In `canvas.py`:
- Add `"edge_hit_padding": "edge-hit-padding",` to `_CANVAS_SETTING_PROPS`.
- Import `ARROW_HEADS` from `haywire.core.edge.arrow_heads`.
- In `__init__`, next to `self._apply_canvas_setting_props()`, add:

```python
        # The head table is static: canvas.vue builds one <marker> per head from it.
        self._props["arrow-heads"] = [head.to_payload() for head in ARROW_HEADS]
```

- Add the method:

```python
    def set_edge_defaults(self, arrow: str, width: float) -> None:
        """Push the graph's computed-edge arrow head (a head name or ``none``) and width in pixels."""
        self._props["edge-arrow"] = arrow
        self._props["edge-width"] = width
        self.update()
```

- [ ] **Step 6: `GraphCanvasManager`**

After the `node_theme` subscription in setup:

```python
        # Computed-edge defaults: pushed as canvas props; canvas.vue turns them
        # into CSS vars and path insets, so a change costs one push per canvas.
        self._apply_edge_defaults()
        for field in ("edge_arrow", "edge_width"):
            self.graph.props._subscribe_field(field, self._on_edge_default_changed)
```

and the methods:

```python
    def _on_edge_default_changed(self, _value, _old) -> None:
        self._apply_edge_defaults()

    def _apply_edge_defaults(self) -> None:
        """Push this graph's computed-edge arrow head and width to the canvas."""
        props = self.graph.props
        self.canvas_vue.set_edge_defaults(props.edge_arrow, float(props.edge_width))
```

Check `cleanup()` (around line 319) for how the `node_theme` subscription is released. Release these two the same way. If nothing releases `node_theme`, add nothing and say so in the report.

- [ ] **Step 7: Run, then the gate**

Run: `uv run pytest tests/ui/test_canvas_handlers tests/ui/test_canvas_edge_props.py -q`. Expected: PASS.

Then grep: `grep -rn "strokeWidth\|stroke_width" --include='*.py' packages barn tests`. Expected: no hits.

Run the ruff check and mypy on the changed files, then the pre-commit gate. `canvas.vue` still reads `strokeWidth` from the payload with a default of 2 until Task 7, so the canvas keeps drawing.

- [ ] **Step 8: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py packages/haywire-core/src/haywire/ui/components/graph/settings.py packages/haywire-core/src/haywire/ui/components/graph/canvas.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py tests/ui/test_canvas_handlers/test_edge_sync_payload.py tests/ui/test_canvas_handlers/test_edge_visual_state.py tests/ui/test_canvas_edge_props.py
git commit -m "feat(canvas): edge payload carries arrowAt; graph edge defaults reach the canvas

The sync payload drops strokeWidth and the invalid colour, and gains the
wire type's arrowAt. The canvas gets the head table once, the graph's
edge_arrow/edge_width on change, and CanvasSettings.edge_hit_padding.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Canvas: width, selection, hit area and state colours from vars and tokens

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`, `packages/haywire-core/src/haywire/ui/themes/workbench.py`, `tests/ui/harness/routes.py`.
- Test:
  - create `tests/ui/harness/test_edge_appearance.py` (auto-marked `browser`);
  - extend the theme token-map test that asserts `_CSS_TOKEN_MAP` entries (grep `edge_active` in `tests/ui`).

**Interfaces:**
- Consumes: Task 6's props `edge-width`, `edge-arrow`, `edge-hit-padding`, `arrow-heads` and the payload's `arrowAt`.
- Produces:
  - edge paths with class `hw-edge`, hit areas with class `hw-edge-hit`;
  - the SVG carries `--hw-edge-width`, `--hw-edge-hit-padding` and `--hw-edge-head`;
  - theme tokens `edge_selected_extra` → `--hw-edge-selected-extra` and `edge_active_extra` → `--hw-edge-active-extra`;
  - harness route `/graph-edge-appearance`, with buttons `set-width-4`, `set-arrow-open`, `set-arrow-ring` and `set-arrow-none`.

- [ ] **Step 1: The harness fixture**

In `tests/ui/harness/routes.py`, near `_build_layout_graph`:

```python
_ADD_FLOAT_KEY = "haybale-testing:node:TestAddFloatNode"
_LISTENER_KEY = "haybale-testing:node:TestCustomCallbackNode"
_EMITTER_KEY = "haybale-testing:node:TestEmitCallbackNode"
_ADD_PORT_KEY = "haybale-testing:node:AddPortTestNode"


def _build_edge_appearance_graph(node_factory):
    """One edge of each kind the edge-appearance tests read: data, control, callback, and an invalid one."""
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor

    graph = BaseGraph("Edge Appearance Fixture")
    editor = Editor(graph, node_factory)

    def node(key: str, x: float, y: float):
        wrapper = graph.create_node_wrapper(key, position=(x, y))
        assert wrapper is not None, f"could not create {key}"
        return wrapper

    add_a, add_b = node(_ADD_FLOAT_KEY, 3600.0, 3600.0), node(_ADD_FLOAT_KEY, 3950.0, 3600.0)
    begin, printer = node(_RECONNECT_SOURCE_KEY, 3600.0, 3800.0), node(_RECONNECT_SINK_KEY, 3950.0, 3800.0)
    listener, emitter = node(_LISTENER_KEY, 3600.0, 4000.0), node(_EMITTER_KEY, 3950.0, 4000.0)
    slot_a, slot_b = node(_ADD_PORT_KEY, 3600.0, 4250.0), node(_ADD_PORT_KEY, 3950.0, 4250.0)

    assert editor.create_edge(add_a.node_id, "result", add_b.node_id, "value_a")
    assert editor.create_edge(begin.node_id, "exec", printer.node_id, "exec")
    assert editor.create_edge(listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
    # Two bare ADD slots never link: the edge stays, and fails validation.
    graph.create_edge_wrapper(slot_a.node_id, "add_out_0", slot_b.node_id, "add_in_0")
    return graph, editor
```

And the route, next to `/graph-layout`:

```python
    # -------------------------------------------------------------------------
    # GET /graph-edge-appearance
    #
    # A data, a control, a callback and an invalid edge, plus buttons setting
    # the graph's edge defaults. Fixed token values make colours assertable.
    # Backs test_edge_appearance.py.
    # -------------------------------------------------------------------------

    @ui.page("/graph-edge-appearance")
    async def graph_edge_appearance_page():
        graph, editor = _build_edge_appearance_graph(library_service.get_node_factory())
        ui.add_css(":root:root { --hw-danger: rgb(200, 10, 10); --hw-edge-default: rgb(10, 120, 200); }")

        for testid, field, value in (
            ("set-width-4", "edge_width", 4.0),
            ("set-arrow-open", "edge_arrow", "open"),
            ("set-arrow-ring", "edge_arrow", "circle_hollow"),
            ("set-arrow-none", "edge_arrow", "none"),
        ):
            ui.button(testid, on_click=lambda _, f=field, v=value: setattr(graph.props, f, v)).props(
                f'data-testid="{testid}"'
            )

        _mount_graph_canvas(library_service, graph, editor, testid="edge-appearance")
        _stamp_synced()
```

- [ ] **Step 2: Write the failing browser tests**

Create `tests/ui/harness/test_edge_appearance.py`:

```python
"""Edge appearance in the browser: width, selection, hit area, state colours and arrow heads.

Everything here lives in canvas.vue's stylesheet and path math, which the
Python tiers cannot see. Colours are compared against fixed token values the
harness page sets on :root.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled

_PATH = "/graph-edge-appearance"

_DATA = 'path.hw-edge[data-edge-id*="[result]->"]'
_CONTROL = 'path.hw-edge[data-edge-id*="[exec]->"]'
_CALLBACK = 'path.hw-edge[data-edge-id*="[listen_callback]->"]'
_INVALID = 'path.hw-edge[data-edge-id*="[add_out_0]->"]'
_DATA_HIT = 'path.hw-edge-hit[data-edge-id*="[result]->"]'

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_DATA)
    wait_for_canvas_settled(page)


def _click(page: Page, testid: str) -> None:
    page.click(f'[data-testid="{testid}"]')
    page.wait_for_timeout(600)


def _computed(page: Page, selector: str, prop: str) -> str:
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('missing ' + sel);
            return getComputedStyle(el)[prop];
        }""",
        [selector, prop],
    )


def _with_class(page: Page, selector: str, cls: str, prop: str) -> str:
    """Add *cls* to the element, read a computed property, then remove the class again."""
    return page.evaluate(
        """([sel, cls, prop]) => {
            const el = document.querySelector(sel);
            el.classList.add(cls);
            const value = getComputedStyle(el)[prop];
            el.classList.remove(cls);
            return value;
        }""",
        [selector, cls, prop],
    )


def test_a_computed_edge_draws_at_the_graph_width(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _DATA, "strokeWidth") == "2px"
    assert page.evaluate("(sel) => document.querySelector(sel).getAttribute('stroke-width')", _DATA) is None

    _click(page, "set-width-4")

    assert _computed(page, _DATA, "strokeWidth") == "4px"


def test_selected_and_active_widen_relative_to_the_edge_width(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-width-4")

    assert _with_class(page, _DATA, "connection-selected", "strokeWidth") == "5px"
    assert _with_class(page, _DATA, "connection-active", "strokeWidth") == "6px"


def test_the_hit_area_is_the_width_plus_the_canvas_padding(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _DATA_HIT, "strokeWidth") == "10px"


def test_an_invalid_edge_is_drawn_in_the_danger_token(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _INVALID, "stroke") == "rgb(200, 10, 10)"


def test_a_missing_pin_colour_falls_back_to_the_edge_default_token(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, ".connection-svg", "color") == "rgb(10, 120, 200)"
```

- [ ] **Step 3: Run them.** `uv run pytest tests/ui/harness/test_edge_appearance.py -q -p no:randomly`. Expected: FAIL. No `hw-edge` class exists, so the selector waits time out.

- [ ] **Step 4: The theme tokens**

In `workbench.py`'s `_CSS_TOKEN_MAP`, under `# Edges`, after `"edge_active": "--hw-edge-active",`:

```python
        # Optional lengths added to the edge width while selected / active;
        # canvas.vue falls back to 1px and 2px when a theme sets none.
        "edge_selected_extra": "--hw-edge-selected-extra",
        "edge_active_extra": "--hw-edge-active-extra",
```

Extend the token-map test you found with the two entries.

- [ ] **Step 5: `canvas.vue`: props, the SVG vars, the payload field**

Props, after `hoverExitDelay`:

```js
        // Edge appearance (design round D): the graph's computed-edge defaults,
        // the studio's hit padding and the static head table.
        edgeWidth:      { type: Number, default: 2 },
        edgeArrow:      { type: String, default: 'none' },
        edgeHitPadding: { type: Number, default: 8 },
        arrowHeads:     { type: Array,  default: () => [] },
```

Computed, after `canvasSizeStyle`:

```js
        edgeStyleVars() {
            return {
                '--hw-edge-width': `${this.edgeWidth}px`,
                '--hw-edge-hit-padding': `${this.edgeHitPadding}px`,
                '--hw-edge-head': this._headUrl(this.edgeArrow),
            };
        },

        headInsets() {
            const insets = {};
            for (const head of this.arrowHeads) insets[head.name] = head.inset;
            return insets;
        },
```

Methods (anywhere in `methods`):

```js
        _headMarkerId(name) {
            return `hw-head-${this.containerId}-${name}`;
        },

        _headUrl(name) {
            return this.headInsets[name] === undefined ? 'none' : `url(#${this._headMarkerId(name)})`;
        },
```

Template: `<svg id="connection-svg" ref="svg" class="connection-svg" :style="[canvasSizeStyle, edgeStyleVars]">`.

`_syncEdgeAddition`:
- In the destructured `data`, replace `strokeWidth = 2,` with `arrowAt = 'inlet',`.
- In the existing-edge branch, replace `edgeInfo.strokeWidth = strokeWidth;` with:

```js
                edgeInfo.arrowAt = arrowAt;
                this._applyArrowClass(edgeInfo);
```

- Pass `arrowAt` instead of `strokeWidth` to `_createEdge`.

`_createEdge`:
- In the parameter list, replace `strokeWidth = 2,` with `arrowAt = 'inlet',`.
- In `edgeInfo`, replace `strokeWidth: strokeWidth,` with `arrowAt: arrowAt,`.
- After `path.setAttribute('fill', 'none');`, add `path.classList.add('hw-edge');`.
- After `edgeInfo` is built, add `this._applyArrowClass(edgeInfo);`.
- On the hit area, delete `hitArea.setAttribute('stroke-width', '10');` and add `hitArea.classList.add('hw-edge-hit');`.
- Grep `_createEdge(` for every call site and pass `arrowAt` where `strokeWidth` went.

Add the method (Task 8's stylesheet rules give the classes their meaning):

```js
        _applyArrowClass(edgeInfo) {
            const path = edgeInfo.path;
            path.classList.remove('edge-arrow-inlet', 'edge-arrow-outlet', 'edge-arrow-none');
            path.classList.add(`edge-arrow-${edgeInfo.arrowAt}`);
        },
```

`_updateEdge`:
- Delete the `edgeInfo.path.setAttribute('stroke-width', edgeInfo.strokeWidth);` call.
- Delete the `if (hitArea) { hitArea.setAttribute('stroke-width', edgeInfo.strokeWidth + 8); }` block.
- Keep stroke, dasharray and opacity.

`_updateEdgeVisualSelection`: delete both `edgeInfo.path.style.strokeWidth = …` lines. Keep the class toggles.

Then: `grep -n "strokeWidth" packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`. Expected: no hits.

- [ ] **Step 6: `canvas.vue`: colour fallbacks through `currentColor`**

A presentation attribute cannot hold `var()`. The fallback is therefore `currentColor`, which resolves against the SVG's `color` (set to `--hw-edge-default` in Step 7).

| Site | Before | After |
|---|---|---|
| `_createEdge` | `outletPin.dataset.pinColor \|\| '#bbbbbb'` | `\|\| 'currentColor'` |
| `_createEdge` | `inletPin.dataset.pinColor \|\| '#333333'` | `\|\| 'currentColor'` |
| `_updateEdge` | `edgeInfo.outletColor = outletPin.dataset.pinColor;` | `edgeInfo.outletColor = outletPin.dataset.pinColor \|\| 'currentColor';` |
| `_updateEdge` | the same for `inletColor` | `\|\| 'currentColor'` |
| `_createBezierStroke` | `return '#000000';` (edge not found) | `return 'currentColor';` |
| `_createBezierStroke` | `return startColor \|\| '#ff0000';` | `return startColor \|\| 'currentColor';` |
| edge-drag start | `pin.dataset.pinColor \|\| '#000000'` | `\|\| 'currentColor'` |
| suggestion path | `… \|\| '#4CAF50'` | `\|\| 'currentColor'` |

At the edge-drag start, delete `previewPath.setAttribute('stroke-width', '2');`. In the suggestion path, delete `suggestionPath.setAttribute('stroke-width', '2');`. Their width comes from the stylesheet (Step 7).

Then: `grep -n "#000000\|#ff0000\|#bbbbbb\|#333333\|#4CAF50\|#f44336\|#EF4444" packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`. Expected: only stylesheet hits that Step 7 replaces.

- [ ] **Step 7: `canvas.vue`: the stylesheet**

Replace the existing rules as follows. Keep each rule's other declarations (z-index, transform, opacity) exactly as they are.

```css
.connection-pin.connection-valid {
    box-shadow: 0 0 15px var(--hw-success) !important;
    border-color: var(--hw-success) !important;
    z-index: 10002 !important;
}

.connection-pin.connection-invalid {
    transform: var(--hw-pin-rotate, ) scale(0.8) !important;
    box-shadow: 0 0 15px var(--hw-danger) !important;
    border-color: var(--hw-danger) !important;
    z-index: 10002 !important;
    opacity: 0.8 !important;
}
```

In `.connection-pin.connection-compatible`, use `color-mix(in srgb, var(--hw-success) 60%, transparent)` for the box-shadow and `80%` for the border colour. Keep its transform and z-index lines.

`.connection-selected` and `path.connection-selected`: in both filters, replace `rgba(74, 144, 226, 0.6)` with `color-mix(in srgb, var(--hw-edge-selected) 60%, transparent)`.

```css
.connection-active {
    stroke: var(--hw-edge-active) !important;
    stroke-width: calc(var(--hw-edge-width, 2px) + var(--hw-edge-active-extra, 2px)) !important;
}

path.connection-invalid {
    stroke: var(--hw-danger);
    filter: drop-shadow(0 0 4px color-mix(in srgb, var(--hw-danger) 50%, transparent));
}

path.connection-warning {
    filter: drop-shadow(0 0 4px color-mix(in srgb, var(--hw-warning) 50%, transparent));
}
```

In `.connection-suggestion`, use `stroke-width: var(--hw-edge-width, 2px) !important;`. In `.connection-suggestion-nearest`, use `stroke-width: calc(var(--hw-edge-width, 2px) + 1px) !important;`.

Add, after the `path.connection-warning` rule:

```css
/* Edge appearance (design round D). The canvas sets --hw-edge-width,
   --hw-edge-hit-padding and --hw-edge-head on its SVG; selected and active
   add a theme length. A missing pin colour is drawn as currentColor. */
.connection-svg {
    color: var(--hw-edge-default);
}

path.hw-edge {
    stroke-width: var(--hw-edge-width, 2px);
}

path.hw-edge.connection-selected {
    stroke-width: calc(var(--hw-edge-width, 2px) + var(--hw-edge-selected-extra, 1px));
}

path.hw-edge-hit {
    stroke-width: calc(var(--hw-edge-width, 2px) + var(--hw-edge-hit-padding, 8px));
}
```

The drag preview path carries no class. Give it `this.edgeDrag.previewPath.classList.add('hw-edge-preview');` where it is created, and add the rule below. It takes the width but not `hw-edge`, whose arrow-head rule (Task 8) would put a head at the cursor end.

```css
path.hw-edge-preview {
    stroke-width: var(--hw-edge-width, 2px);
}
```

- [ ] **Step 8: Run, then the tiers**

Run: `uv run pytest tests/ui/harness/test_edge_appearance.py -q -p no:randomly`. Expected: 5 passed.

Run the browser tier, the ruff check and mypy on `workbench.py` and `routes.py`, and the pre-commit gate. Expected: green. Edge-drag and reconnect tests exercise the preview and suggestion paths.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue packages/haywire-core/src/haywire/ui/themes/workbench.py tests/ui/harness/routes.py tests/ui/harness/test_edge_appearance.py <the theme token test file>
git commit -m "feat(canvas): edge width, selection, hit area and state colours from vars and tokens

Every edge reads --hw-edge-width; selected and active add a theme length;
the hit area adds the canvas setting. Invalid, warning, drop targets,
selection and the missing-pin fallback read theme tokens.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Canvas: arrow heads, `arrowAt` and path insets

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`.
- Test: extend `tests/ui/harness/test_edge_appearance.py`.

**Interfaces:**
- Consumes:
  - Task 7's `hw-edge` class, `_applyArrowClass`, `edgeStyleVars`, `headInsets` and `_headMarkerId`;
  - Task 6's `arrowHeads` payloads (`name`, `inset`, `svg`, `view_box`, `width`, `height`).
- Produces: one `marker.hw-edge-head` per head in each canvas's `<defs>`, and a computed edge shortened at its headed end by `inset × edgeWidth`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/harness/test_edge_appearance.py`:

```python
def _end_point(page: Page, selector: str, end: str) -> dict:
    """The path's point at its inlet ('inlet') or outlet ('outlet') end, in SVG coordinates."""
    return page.evaluate(
        """([sel, end]) => {
            const path = document.querySelector(sel);
            const point = path.getPointAtLength(end === 'inlet' ? path.getTotalLength() : 0);
            return { x: point.x, y: point.y };
        }""",
        [selector, end],
    )


def _distance(a: dict, b: dict) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def test_every_head_has_one_marker_in_the_canvas(page: Page, harness) -> None:
    _open(page, harness)
    assert page.evaluate("() => document.querySelectorAll('marker.hw-edge-head').length") == 15


def test_no_head_by_default(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _DATA, "markerEnd") == "none"
    assert _computed(page, _DATA, "markerStart") == "none"


def test_a_graph_head_sits_at_the_inlet_of_data_and_control_edges(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-arrow-open")
    for selector in (_DATA, _CONTROL):
        assert "-open" in _computed(page, selector, "markerEnd")
        assert _computed(page, selector, "markerStart") == "none"


def test_a_callback_edge_draws_its_head_at_the_outlet(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-arrow-open")
    assert "-open" in _computed(page, _CALLBACK, "markerStart")
    assert _computed(page, _CALLBACK, "markerEnd") == "none"


def test_the_path_stops_short_of_the_inlet_by_the_head_inset(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-width-4")
    full = _end_point(page, _DATA, "inlet")

    _click(page, "set-arrow-open")
    assert abs(_distance(_end_point(page, _DATA, "inlet"), full) - 4.0 * 4) < 0.5

    _click(page, "set-arrow-none")
    assert _distance(_end_point(page, _DATA, "inlet"), full) < 0.5


def test_a_callback_head_shortens_the_outlet_end(page: Page, harness) -> None:
    _open(page, harness)
    full = _end_point(page, _CALLBACK, "outlet")

    _click(page, "set-arrow-ring")

    assert abs(_distance(_end_point(page, _CALLBACK, "outlet"), full) - 4.5 * 2) < 0.5


def test_a_hollow_head_is_hollow(page: Page, harness) -> None:
    _open(page, harness)
    fill = page.evaluate(
        "() => getComputedStyle(document.querySelector('marker.hw-edge-head[id$=\"-circle_hollow\"] circle')).fill"
    )
    assert fill == "none"


def test_arrow_at_none_draws_no_head(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-arrow-open")
    assert _with_class(page, _DATA, "edge-arrow-none", "markerEnd") == "none"
```

- [ ] **Step 2: Run them.** Expected: the new tests FAIL, because there are no markers and no `marker-end` rule. Task 7's tests still pass.

- [ ] **Step 3: Build the markers**

Add the method:

```js
        _buildHeadMarkers() {
            const defs = this.$refs.defs;
            if (!defs) return;
            defs.querySelectorAll('marker.hw-edge-head').forEach((marker) => marker.remove());
            for (const head of this.arrowHeads) {
                const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
                marker.setAttribute('id', this._headMarkerId(head.name));
                marker.setAttribute('class', 'hw-edge-head');
                marker.setAttribute('viewBox', head.view_box);
                marker.setAttribute('refX', '0');
                marker.setAttribute('refY', '0');
                marker.setAttribute('markerWidth', String(head.width));
                marker.setAttribute('markerHeight', String(head.height));
                marker.setAttribute('markerUnits', 'strokeWidth');
                // One definition serves both ends: at marker-start it turns to
                // point back into the outlet.
                marker.setAttribute('orient', 'auto-start-reverse');
                marker.setAttribute('overflow', 'visible');
                marker.innerHTML = head.svg;
                defs.appendChild(marker);
            }
        },

        _relayoutEdges() {
            for (const [edge_id] of this.edgePaths) this._updateEdge(edge_id);
        },
```

At the end of `mounted()`, add `this._buildHeadMarkers();`.

`canvas.vue` already contains two identical loops, `for (const [edge_id] of this.edgePaths) this._updateEdge(edge_id);` (grep for it). Replace both with `this._relayoutEdges();`.

Add a `watch` option after `computed`. `canvas.vue` has none yet.

```js
    watch: {
        // A width or head change moves every computed edge's end: re-lay-out.
        edgeWidth() { this._relayoutEdges(); },
        edgeArrow() { this._relayoutEdges(); },
        arrowHeads() {
            this._buildHeadMarkers();
            this._relayoutEdges();
        },
    },
```

- [ ] **Step 4: Shorten the path at the headed end**

Replace `_createBezierPathForEdge`'s `return this._createBezierPath(…)` with:

```js
            // A head is drawn from where the path ends to the pin, so the path
            // stops short by the head's length along the end's own direction.
            const [startInset, endInset] = this._edgeInsets(edgeInfo);
            const [ox, oy] = edgeInfo.outletConnectDir;
            const [ix, iy] = edgeInfo.inletConnectDir;
            const start = { x: edgeInfo.outletPos.x + ox * startInset, y: edgeInfo.outletPos.y + oy * startInset };
            const end = { x: edgeInfo.inletPos.x + ix * endInset, y: edgeInfo.inletPos.y + iy * endInset };
            return this._createBezierPath(start, end, edgeInfo.outletConnectDir, edgeInfo.inletConnectDir);
```

and add:

```js
        _edgeInsets(edgeInfo) {
            const inset = this.headInsets[this.edgeArrow];
            if (inset === undefined || edgeInfo.arrowAt === 'none') return [0, 0];
            const length = inset * this.edgeWidth;
            return edgeInfo.arrowAt === 'outlet' ? [length, 0] : [0, length];
        },
```

The gradient keeps its pin-to-pin coordinates (`_createBezierStroke` reads `outletPos`/`inletPos`), so the head's `context-stroke` takes the colour at the pin end.

- [ ] **Step 5: The marker rules**

Add after the `path.hw-edge` rule:

```css
path.hw-edge {
    marker-end: var(--hw-edge-head, none);
}

path.hw-edge.edge-arrow-outlet {
    marker-end: none;
    marker-start: var(--hw-edge-head, none);
}

path.hw-edge.edge-arrow-none {
    marker-end: none;
    marker-start: none;
}
```

Merge the first `marker-end` line into Task 7's existing `path.hw-edge` block rather than writing the selector twice.

- [ ] **Step 6: Run, then the tiers**

Run: `uv run pytest tests/ui/harness/test_edge_appearance.py -q -p no:randomly`. Expected: 13 passed.

Run the browser tier and the pre-commit gate. Expected: green.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue tests/ui/harness/test_edge_appearance.py
git commit -m "feat(canvas): arrow heads as context-stroke markers on a path shortened by the head

One marker per head and canvas, used at either end. A computed edge's head
sits at the end its wire type's arrowAt names, and the path stops short by
the head's inset times the width, so the line meets the glyph's edge.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: ADR, glossary, docs and the generated library docs

**Files:**
- Create: `docs/adr/0045-edge-appearance.md`.
- Modify:
  - `docs/reference/glossary.md`, `docs/reference/design-guide.md`;
  - `docs/components/themes/theme-canon.md`, `docs/architecture/graph/graph-arch.md`, `docs/components/settings/setting-canon.md`;
  - generated library docs in both repos.

- [ ] **Step 1: ADR 0045**

Read `docs/reference/doc-authoring.md` and ADR 0044 for the frontmatter shape. Create `docs/adr/0045-edge-appearance.md`:

```markdown
---
name: edge-appearance
description: Edges render through CSS custom properties; computed edges take an arrow head and width from framework < graph defaults at the end their wire type names; state colours are theme tokens; heads are context-stroke markers on a path shortened by the head
status: accepted
see-also: ADR-0022, ADR-0030, ADR-0031, ADR-0042, ADR-0044
level: architectural
---

# Edge appearance

**Context.**
- An edge's look was fixed in code: width 2 sent by the server, selection and active widths 3 and 4, a hit area of 10, an invalid colour of `#EF4444`, and hard-coded fallbacks in the canvas. There were no arrow heads.
- Diagram edges (the annotation wire) need their colour, dash and heads set per edge.
- Execution edges carry information in their computed look: the pin gradient and the adapter-chain dash.

**Decision.**
- **Two kinds of edge.**
  - A **styled edge**'s wire type declares a style bag, and each edge sets the fields its bag declares.
  - A **computed edge**'s wire type declares none: data, control and callback edges. Their colour and dash stay computed, and their arrow head and width come from the **edge defaults**.
- **Edge defaults: framework < graph.**
  - The framework tier is `EdgeDefaultSettings` (`ui.edge.default`: `arrow`, `width`), a core schema.
  - The graph tier is the `GraphProperties` shadows `edge_arrow` and `edge_width` ("unset tracks, set ignores").
  - A Group interior uses its own graph props.
- **A wire type names the end of its computed head.** `WireType.arrow_at` is `INLET` by default; it can also be `OUTLET` or `NONE`. `CallbackWire` declares `OUTLET`, the listener the callback returns to. No role is checked.
- **Rendering runs on CSS custom properties.**
  - The canvas receives the graph values as props. It sets `--hw-edge-width`, `--hw-edge-head` and `--hw-edge-hit-padding` on its SVG.
  - One stylesheet rule set draws every edge.
  - A change is one write per canvas plus a client-side re-layout of its paths. There is no per-edge server work.
- **State colours are theme tokens:**

  | State | Token |
  |---|---|
  | invalid | `--hw-danger` |
  | warning glow | `--hw-warning` |
  | drop targets | `--hw-success` / `--hw-danger` |
  | selected glow | `--hw-edge-selected` |
  | active | `--hw-edge-active` |
  | a missing pin colour | `--hw-edge-default`, through `currentColor` |

- **Widths.** Selected and active widths add the optional tokens `--hw-edge-selected-extra` and `--hw-edge-active-extra` (1px, 2px). The hit area adds `CanvasSettings.edge_hit_padding`, an ergonomic studio setting rather than part of a theme.
- **Heads.**
  - Fifteen heads form one vocabulary. One `context-stroke` marker per head serves both ends (`orient="auto-start-reverse"`), and heads scale with the width (`markerUnits="strokeWidth"`).
  - The path is shortened at a headed end by the head's inset, so the line meets the glyph's edge. Hollow heads are hollow.
  - `ArrowHeadWidget` picks a head: common arrows first, the rest behind "More".
- **Styled edges set the same vars inline** on their own path. A field their bag declares wins; one it does not declare falls through to the graph default.

**Alternatives.**
- *Colours as settings with a graph tier.* This duplicates the theme cascade, which already tiers colours.
- *Per-role defaults.* Six fields for a choice nobody asked for. They can be added without breaking anything.
- *A role check for callback heads.* A framework special case, where a fact on the wire type does the same.
- *One marker per colour.* This needs marker bookkeeping on every colour change, and `context-stroke` makes it unnecessary.
- *Masking hollow heads with the canvas background.* This hides the grid under a head.

**Consequences.**
- A graph can turn arrows on for all its execution edges.
- Themes restyle edge states live.
- 5.4's style bag only binds values to the inline vars.
- Saved graphs carry `edge_arrow` and `edge_width` under `"props"` only when set.
```

- [ ] **Step 2: Glossary**

In `docs/reference/glossary.md`, add these rows, keeping alphabetical order and the table's avoid column:

```markdown
| **Arrow head** | A glyph drawn at an edge end, from the shared vocabulary of fifteen heads (arrow, open V, triangle, diamond, circle, bar, the ERD cardinalities). Drawn as a `context-stroke` marker on a path shortened by the head's inset. See [ADR 0045](../../adr/0045-edge-appearance.md) | arrow type, marker |
| **Computed edge** | An edge whose wire type declares no style bag (data, control, callback). Its colour comes from its pins, its dash from its adapter chain, and its arrow head and width from the **Edge defaults** | default edge, plain edge |
| **Edge defaults** | The arrow head and width every **Computed edge** draws with: `EdgeDefaultSettings` in the studio, overridden per graph by `edge_arrow` and `edge_width` on the graph props. The head sits at the end the wire type's `arrow_at` names | edge settings, edge style |
| **Styled edge** | An edge whose wire type declares a style bag; each edge sets the fields its bag declares (colour, dash, width, arrow heads). A field it does not declare falls through to the **Edge defaults** | annotated edge, custom edge |
```

In the existing **Wire type** row, append: "; `arrow_at` names the end a **Computed edge** draws its arrow head at (`CallbackWire`: the outlet)".

- [ ] **Step 3: Design guide, theme canon, graph-arch, settings canon**

**`design-guide.md`.** Replace the three `--hw-edge-*` rows of the token table with these rows:

```markdown
| `--hw-edge-default`        | Edge colour where a pin gives none (the edge SVG's `color`, drawn as `currentColor`) |
| `--hw-edge-selected`       | Glow of a selected edge |
| `--hw-edge-selected-extra` | Optional length added to an edge's width while selected (default `1px`) |
| `--hw-edge-active`         | Stroke of the single *active* edge; mutually exclusive with `--hw-node-active` |
| `--hw-edge-active-extra`   | Optional length added to an edge's width while active (default `2px`) |
```

Below the table, add: "Edge states read the semantic status tokens: an invalid edge `--hw-danger`, a warning glow `--hw-warning`, drop targets `--hw-success` / `--hw-danger`. An edge's width and arrow head are graph settings, not tokens (ADR 0045)."

**`theme-canon.md`.** Where the edge tokens are listed, add the two optional length tokens and the same sentence.

**`graph-arch.md`.** Where `GraphProperties` fields are listed, add `edge_arrow` and `edge_width` (shadowing `EdgeDefaultSettings`). If no such list exists, add one sentence where `graph.props` is introduced.

**`setting-canon.md`.** Where `graph()` / `GraphProperties` is described (§3b), add `edge_arrow` and `edge_width` as further shadows, and the `CanvasSettings.edge_hit_padding` field if `CanvasSettings` fields are listed.

Then run: `grep -rn "EF4444\|stroke_width\|strokeWidth" docs .codemap --include='*.md' | grep -v "docs/superpowers\|docs/archive\|docs/adr/00[0-3]"`
Expected: no hits that describe current behaviour.

- [ ] **Step 4: Regenerate the library docs**

Run `uv run haywire docs --all`, then `uv run haywire docs barn/haybale-visiongraph`. Use `git status --short` in both repos for the changed paths. Expected: a doc for `ArrowHeadWidget`, and graph-props and settings docs naming the new fields.

- [ ] **Step 5: Docs build**

Run: `uv run mkdocs build --strict > /tmp/mk.log 2>&1; echo "exit=$?"; grep -n "WARNING" /tmp/mk.log`
Expected: only the known warning (`guides/panels.md` links into `.insights/`).

- [ ] **Step 6: Commit**

```bash
git add docs/adr/0045-edge-appearance.md docs/reference/glossary.md docs/reference/design-guide.md docs/components/themes/theme-canon.md docs/architecture/graph/graph-arch.md docs/components/settings/setting-canon.md <generated docs paths from git status>
git status --short
git commit -m "docs: edge appearance (ADR 0045), glossary, tokens and settings

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

In the visiongraph repo, commit its regenerated docs if any changed (`docs: regenerate for edge appearance`, with the trailer).

---

### Task 10: Verify the plan

**Files:**
- Modify (uncommitted, for the user): `docs/superpowers/plans/2026-10-02-wire-types.md` (status).

- [ ] **Step 1: Full checks.** Run the ruff check on the whole repo, the mypy set, the pre-commit gate, the browser tier, the visiongraph tests and `uv run pytest -m perf -q`. Report the counts against Task 0's.

- [ ] **Step 2: The running studio, step by step with the user**

Unit and browser tests do not cover every look. Hand the user these checks one at a time, waiting for each result:

1. **Studio default.** In the studio settings, set Edge Arrow to *Arrow* and Edge Width to 3.
   - Every data and control edge in an open graph shows an arrow at its inlet.
   - Callback edges show one at the listener's outlet.
   - All edges are 3px wide.
2. **Graph override.** In the graph properties, set Edge Arrow to *None*.
   - This graph's edges lose their heads.
   - Another open graph keeps the studio arrows.
   - Reset the graph field: the arrows come back.
3. **Picker.** The arrow picker shows *None* and four arrows; *More* reveals the rest. Pick *Hollow circle*: the edge line meets the circle's edge, and the grid shows through it. Zoom in to check.
4. **Every head.** Step through all fifteen heads at width 3 and at width 8. Each glyph's tip touches its pin, and no line runs into or past a glyph. Note any head whose geometry needs a nudge (the inset or the coordinates in `arrow_heads.py`).
5. **Selection and active.** Select an edge: it widens by 1 and glows in the theme's selected colour. Make it active: it widens by 2. At width 8, both stay relative.
6. **Hit area.** In the canvas settings, set Edge Hit Padding to 0: clicking needs to land on the line itself. Set it to 20: a click near the line selects it.
7. **States and themes.** An invalid edge, for example a saved edge between two bare `ADD` slots, is drawn in the theme's danger colour. Switch the workbench theme: the colour follows without a reload.
8. **Group interior.** Enter a Group: its edges follow the Group's own graph props, not the host's.
9. **Paint.** After a width change on a large graph (`graphs/10x512n_5x448e.haywire`), run `paintcheck.py` (`.insights/project_chrome_paint_completeness.md`). Every edge is painted.

Report each check as passed or failed. A failure is a bug: stop and report.

- [ ] **Step 3: Status**

In `docs/superpowers/plans/2026-10-02-wire-types.md`, set the D row to:

```markdown
| D | Edge appearance: defaults (framework < graph), arrow heads, UX colours | **Landed** on branch `wire-types-5-1`, not merged | [2026-10-04-wire-types-d-edge-appearance.md](2026-10-04-wire-types-d-edge-appearance.md) | 5.4 detail plan |
```

Leave both plan files uncommitted for the user. Report the branch state and the commits made.

---

## Self-review (done while writing)

**Spec coverage** (Q48 to Q62):

| Decision | Task |
|---|---|
| computed edges get graph-tier `arrow` and `width` (Q48, Q49) | 5, 6, 7, 8 |
| precedence (Q50, Q53) | 7, 8: the `path.hw-edge` rules read vars; 5.4 sets them inline |
| state colours as tokens (Q51, Q52) | 6 (server), 7 (canvas) |
| `context-stroke` markers (Q54) | 1 (verify), 8 |
| Group interiors (Q55) | follows from per-graph props; checked live in 10.2.8 |
| code before 5.4 (Q56) | this plan |
| heads on reroute segments (Q57) | no code: every `hw-edge` path takes the rule |
| head vocabulary and picker (Q58) | 3, 4 |
| `arrow_at` (Q59, Q60) | 2, 6, 7, 8 |
| width tokens and hit padding (Q61) | 6, 7 |
| insets and props (Q62) | 6, 8 |

**Behaviour guards.**
- Each intended change has a test that fails before it: Tasks 2 to 8.
- The default look is unchanged (head `none`, width 2, selected +1, active +2, hit padding 8). The gate and the browser tier guard the rest.

**Names.** These are spelled the same in every task:
- Python: `ArrowAt`, `arrow_at`/`arrowAt`, `ARROW_HEADS`, `NO_HEAD`, `get_arrow_head`, `to_payload`, `ArrowHeadWidget`, `ARROW_HEAD_WIDGET`, `EdgeDefaultSettings`, `edge_arrow`, `edge_width`, `edge_hit_padding`, `set_edge_defaults`.
- CSS classes: `hw-edge`, `hw-edge-hit`, `hw-edge-preview`, `hw-edge-head`.
- CSS custom properties: `--hw-edge-width`, `--hw-edge-head`, `--hw-edge-hit-padding`, `--hw-edge-selected-extra`, `--hw-edge-active-extra`.
