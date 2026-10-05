# Edge rendering and the style bag (edge-kinds step 5.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A wire type can name a style bag, and every edge on it then carries its own colour, dash, width and arrow heads. The user edits them in the edge menu and the Edge inspector, they save with the graph, and they survive paste, Subgraph instantiation, collapse and expand. Paste and those paths also stop dropping an edge's `LAZY` choice.

**Architecture:** `EdgeSettings` is a fifth settings flavour (ADR 0022 template: per-instance cells, `_edge` back-reference, `_node` always `None`). `WireType.style` names a subclass. `EdgeWrapper.build()` binds a bag of that class while the edge passes formal validation and unbinds it when it fails, keeping the values as a plain dict either way. `EdgeWrapper.serialize()` writes them under `"style"`, and every save path calls it. The canvas payload gains the declared colour and dash (through the existing `strokeColor`/`strokeDasharray`) and a `style` dict of width and heads, which `canvas.vue` sets as inline vars on the edge's path and hit area. The per-end vars `--hw-edge-head-start`/`--hw-edge-head-end` replace D's single head var on paths, and the canvas code that read the graph's width and head reads per-edge values (F16).

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest (+ xdist, Playwright browser tier), uv, ruff, mypy.

**Settled in:** [2026-10-02-wire-types.md](2026-10-02-wire-types.md), sections "Edge style", "5.4", "D", decisions Q10, Q20, Q26, Q27, Q48, Q50, Q53, Q58, and follow-up F16. Corrections found while writing this plan are listed in [Corrections to the design](#corrections-to-the-design); **the user confirms them in Task 0 Step 1 before any code.**

## Global Constraints

- **Two repos.**
  - This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`.
  - haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked here as `barn/haybale-visiongraph`. This plan changes nothing there; its tests run as a regression check only.
- **Branch.** Continue on `wire-types-5-1` (5.1, 5.2, 5.3 and D are landed there, unmerged). Never push; the user pushes.
- **Commit trailer.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never commit:**
  - `docs/superpowers/plans/` (plans are left for the user to commit);
  - `internals/`, `.superpowers/`, `.claude/settings.json`;
  - the scratch file `tests/core/test_zz_graph_snapshot.py`.

  Always `git add` explicit paths, never `-A` or `.`.
- **Commit `barn/haybale-testing/` first.** Commit every change there before running the full suite: `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing` in its teardown and discards uncommitted edits.
- **Intended behaviour changes.** These are the only ones, each with its test named in its task. Any other red behavioural test is a bug: stop and report it.
  1. **Style bags** (Q10a, Q50): an edge whose wire type names a style bag has one while it passes formal validation (`EdgeWrapper.style`); its locally set values save under the edge's `"style"` key and load back. No builtin wire type names one in this plan; only haybale-testing's `TestVisualWire` does.
  2. **A style edit marks the file unsaved** and redraws the edge (C2: `ChangeReason.EDGE_STYLE_CHANGED`).
  3. **Carried on re-creation** (Q27, C3): paste, Subgraph instantiation (Macro included), collapse and expand keep an edge's chosen propagation and its style. Today all four drop both: a `LAZY` choice becomes `EAGER`.
  4. **Drawing a styled edge** (Q50, Q53, C5, C6): a declared `color` replaces the pin gradient, a declared `dash` replaces the adapter-chain dash, a declared `width` replaces the graph's edge width, and a declared `arrow_start`/`arrow_end` replaces the computed head at that end. The invalid colour and the warning glow still win.
- **Out of scope:** the annotation wire, type, node and skin (5.5); splitting or dissolving a reroute on a styled edge, and the Group-card bridging edges, which turn one edge into two or two into one (C3, follow-up F22); undoable style edits (C8, F23); Farmhand reading or writing edge style (C10, F24); F13 to F15 and F17 to F21; the fallback glyph (C1).
- **Compare wire types by `.id`**, never with `is` on the class. Bag classes are compared with `is` on purpose: a hot reload makes a new class, and that is exactly when a bag must rebind.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. Docstrings of registered components (nodes, types, panels) are displayed: Markdown, single backticks, no reST.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`; line length 109.
- **Pre-commit gate:** `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"`, then `grep -E "^FAILED|^ERROR" /tmp/t.log` and `tail -1 /tmp/t.log`. Timeout at least 600000 ms. Baseline recorded in Task 0.
- **Browser tier:** `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`. One known intermittent failure, `test_edge_batch_cost` (F13): rerun the tier once before calling it red.
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`.
- **mypy set:** `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/`. Baseline clean.
- **Canvas changes are checked in a browser**, not only in unit tests (`.insights/project_multi_canvas_dom_globals.md`). Paint completeness after a width change is checked with `paintcheck.py`, never fps (`.insights/project_chrome_paint_completeness.md`).
- **Code lookup:** the repo is indexed by CodeGraph. `codegraph explore "<symbols>"` returns verbatim source plus callers.

---

## Corrections to the design

Found while reading the code for this plan. **To be confirmed by the user in Task 0 Step 1**; record the answers as design decisions Q71 onward.

| # | Design said | The code says | This plan |
|---|---|---|---|
| C1 | 5.4 adds "the fallback glyph for an unknown `pin_kind`" | 5.1 already did it: `_from_map` always ends in `fallback` (design status note) | Nothing to do; the design's 5.4 entry is corrected in Task 7 |
| C2 | "A style edit calls `edge.redraw()`" | `redraw()` marks `EDGE_REDRAW_REQUESTED`, which `ChangeReason.is_visual_only()` lists: the app does not mark the file unsaved, so a style edit is lost on close without a prompt | A new reason `EDGE_STYLE_CHANGED`: redraws, persists (not visual-only), at redraw priority. `EdgeWrapper.mark_style_changed()` marks it, the edge-side twin of `NodeWrapper.mark_layout_changed()` |
| C3 | Q27: paste and Subgraph instantiation carry `propagation` and style | Two more paths re-create edges from serialized or live edges and drop both: collapse (`_BuildSubgraphAction` rebuilds interior edges from their dicts) and expand (`ExpandGraphNodeAction` re-adds inner edges with `AddEdgeAction`). Split/dissolve reroute and the card's bridging edges turn one edge into two or two into one, with no single source to copy | Carry both in collapse and expand too: each moves an edge unchanged between graphs. Split, dissolve and bridging stay as they are; follow-up F22 |
| C4 | "The bag saves under the edge's `"style"` key, locally set values only" | A bag's `_to_dict()` is `{"values": …, "promoted": …}`; an edge bag has no promotion | `"style"` holds the values mapping flat, e.g. `{"color": "#ff0000"}`. `EdgeWrapper` wraps it as `{"values": …}` for `_from_dict` |
| C5 | Q53: "a styled edge sets its values as inline vars on its own path" | The payload already carries `strokeColor` (a solid colour replaces the gradient, `_createBezierStroke`) and `strokeDasharray`, and Python's `edge_visual_state` already ranks the invalid and warning overlays above them. The hit area is a sibling path, so a var on the edge's path never reaches it | Colour and dash travel in `strokeColor`/`strokeDasharray`. Width and heads become inline vars, set on the path and on its hit area. One stylesheet rule set still draws every edge |
| C6 | Q50: "a field the bag does not declare falls through to the graph default" | The graph default is one head, at the end `arrow_at` names; a bag declares heads per end | Per end: an undeclared `arrow_start` (`arrow_end`) draws the computed head at the outlet (inlet) end if `arrow_at` names it, else none |
| C7 | Q20: while an edge fails validation "its wire type comes from whichever end resolves, for drawing only (look, pin kind)" | The style bag is bound only while the edge validates | A failing edge draws without its style: danger colour, the graph's width and the computed head. Its saved style is kept verbatim and returns when it validates |
| C8 | (not stated) | Node and graph settings edits through `render_settings` write with `setattr`, outside undo | Style edits are not undoable either; follow-up F23 |
| C9 | "edge menu rendering of the bag" | The edge context menu is a `Popup` (z 7001); `ArrowHeadWidget` opens a `ui.menu` (QMenu, z 6000), which may open beneath it (`.insights/feedback_nicegui_nested_menu_flyouts.md`) | Task 6 checks it in a browser first, and raises the widget's menu with `FLYOUT_Z` if it opens underneath |
| C10 | (not stated) | Farmhand reports an edge's `propagation` and `wire_type` (`editor_tools.py:491-510`) | No style in Farmhand in this plan; follow-up F24 |

## Names this plan introduces

| Name | Where | What |
|---|---|---|
| `EdgeSettings` | `core/settings/settings_edge.py` | The fifth settings flavour; base of every style bag |
| `WireType.style: ClassVar[type[EdgeSettings] \| None]` | `core/types/wire.py` | The bag a wire type's edges carry; `None` by default |
| `STYLE_FIELDS`, `DASH_PATTERNS`, `dash_choices()` | `core/edge/style.py` | The recognised field names, the dash vocabulary and its widget options |
| `EdgeWrapper.style` | `core/edge/edge_wrapper.py` | The bound bag, or `None` |
| `EdgeWrapper.style_values()` | same | The edge's locally set style values, bound or not |
| `EdgeWrapper.mark_style_changed()` | same | Marks `EDGE_STYLE_CHANGED` |
| `ChangeReason.EDGE_STYLE_CHANGED` | `core/graph/types.py` | Redraws the edge and persists |
| `RemappedEdge.style` | `core/graph/utils/node_remap.py` | The edge's saved style |
| `TestVisualStyle` | `haybale_testing/wires.py` | Test-only bag declaring every recognised field |
| `EdgeVisualState.style` | `ui_edge.py` | The canvas-shaped width and heads: `{"width", "arrowStart", "arrowEnd"}`, declared keys only |
| `EdgeStylePanel`, `EdgeStyleMenuPanel` | graph-editor panels | The bag in the Edge inspector and the edge menu |

## File structure

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/core/settings/settings_edge.py` | new: `EdgeSettings` |
| `packages/haywire-core/src/haywire/core/settings/__init__.py` | export `EdgeSettings` |
| `packages/haywire-core/src/haywire/core/types/wire.py` | `style` class attribute and its check |
| `packages/haywire-core/src/haywire/core/edge/style.py` | new: `STYLE_FIELDS`, `DASH_PATTERNS`, `dash_choices` |
| `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` | `style` argument, binding in `build()`, `serialize()`, `mark_style_changed()`, cleanup |
| `packages/haywire-core/src/haywire/core/graph/types.py` | `EDGE_STYLE_CHANGED` |
| `packages/haywire-core/src/haywire/core/graph/base.py` | `create_edge_wrapper(style=)`, load passes `"style"`, `to_dict` uses `serialize()` |
| `packages/haywire-core/src/haywire/core/graph/clipboard.py` | uses `serialize()` |
| `packages/haywire-core/src/haywire/core/graph/utils/node_remap.py` | `RemappedEdge.style` |
| `packages/haywire-core/src/haywire/core/graph/subgraph.py` | `instantiate` passes propagation and style |
| `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` | `AddEdgeAction(propagation=, style=)`; paste, collapse, expand carry them |
| `barn/haybale-testing/haybale_testing/wires.py` | `TestVisualStyle`; `TestVisualWire.style` |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py` | style in state, `__eq__` and payload |
| `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` | `SyncEdgeAdditionEvent.style` |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` | per-edge width and heads (F16), per-end head vars |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py` | `EdgeStylePanel` |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py` | `EdgeStyleMenuPanel` |
| `packages/haywire-core/src/haywire/barn/builtin/widgets/arrow_head_widget.py` | only if Task 6 Step 1 finds the menu underneath |
| tests: `tests/core/test_settings/test_edge_settings.py`, `tests/core/test_edge/test_edge_style.py`, `tests/core/test_graph/test_edge_carry.py`, `tests/ui/harness/test_edge_style.py`, `tests/ui/panels/test_edge_style_panels.py` | new |
| tests: `tests/ui/test_canvas_handlers/test_edge_visual_state.py`, `test_edge_sync_payload.py`, `tests/ui/harness/routes.py` | extended |
| docs: ADR 0047 (new), glossary, settings-arch, setting-canon, edges-arch, the design's status | Task 7 |

---

### Task 0: Baseline (controller)

- [ ] **Step 1: Confirm the corrections.** Present C1 to C10 to the user, lettered options where there is a choice. Record the answers in the design doc as a new section "Decisions of 2026-10-04, 5.4 detail plan (Q71 to Q80)", and fold any changed answer into the tasks below before starting.
- [ ] **Step 2: Clean trees.** `git status --short` in both repos shows nothing but untracked plan files and `.claude/settings.json`.
- [ ] **Step 3: Baselines.** Run the pre-commit gate, the browser tier, the visiongraph tests, the mypy set and `uv run ruff check . && uv run ruff format --check .`. Record the pass counts in `.superpowers/sdd/progress.md` under a new section "5.4". All must be green; if not, stop and start an error-fix session with the user (CLAUDE.md).
- [ ] **Step 4: Benchmark baseline.** Run the `haywire-benchmark` skill on the clean tree; Task 8 compares against it.
- [ ] **Step 5: Saved-graph snapshot.** Recreate the scratch test `tests/core/test_zz_graph_snapshot.py` exactly as in [5.1's Task 0 Step 4](landed/2026-10-03-wire-types-5-1-sweep.md) (never committed), and run `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_before_5_4.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`. Task 8 compares against it: no saved graph in either repo may change, since none has a styled edge.

---

### Task 1: `EdgeSettings`, `WireType.style` and the style vocabulary

**Files:**
- Create: `packages/haywire-core/src/haywire/core/settings/settings_edge.py`
- Create: `packages/haywire-core/src/haywire/core/edge/style.py`
- Create: `tests/core/test_settings/test_edge_settings.py`
- Modify: `packages/haywire-core/src/haywire/core/settings/__init__.py` (imports and `__all__`)
- Modify: `packages/haywire-core/src/haywire/core/types/wire.py` (`WireType` attributes, docstring, `__init_subclass__`)
- Modify: `barn/haybale-testing/haybale_testing/wires.py`

**Interfaces:**
- Produces: `EdgeSettings(registry: SettingsRegistry | None = None, edge: EdgeWrapper | None = None)` with `_edge`; `WireType.style` (default `None`; a non-`EdgeSettings` value raises `TypeError` at class definition); `STYLE_FIELDS: tuple[str, ...] = ("color", "width", "dash", "arrow_start", "arrow_end")`; `DASH_PATTERNS: dict[str, str]`; `dash_choices() -> dict[str, str]`; `TestVisualStyle` with all five fields; `TestVisualWire.style = TestVisualStyle`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_settings/test_edge_settings.py`:

```python
"""A style bag is a settings flavour of its own, named by a wire type."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.settings import EdgeSettings, setting
from haywire.core.types.wire import WireRole, WireType

pytestmark = pytest.mark.unit


class _Style(EdgeSettings):
    width = setting[FLOAT](3.0, label="Width")


def test_an_edge_bag_has_no_node_and_keeps_its_edge():
    edge = object()
    bag = _Style(edge=edge)  # type: ignore[arg-type]
    assert bag._node is None
    assert bag._edge is edge


def test_an_edge_bag_round_trips_its_set_values():
    bag = _Style()
    bag.width = 5.0
    restored = _Style()
    restored._from_dict({"values": bag._to_dict()["values"]})
    assert restored.width == 5.0
    assert restored._is_locally_set("width")


def test_an_unknown_key_is_skipped():
    bag = _Style()
    bag._from_dict({"values": {"colour": "#ff0000", "width": 4.0}})
    assert bag._to_dict()["values"] == {"width": 4.0}


def test_a_wire_type_has_no_style_by_default():
    class _Plain(WireType):
        role = WireRole.VISUAL

    assert _Plain.style is None


def test_a_wire_type_names_its_style_bag():
    class _Styled(WireType):
        role = WireRole.VISUAL
        style = _Style

    assert _Styled.style is _Style


def test_a_style_that_is_no_edge_bag_is_refused():
    with pytest.raises(TypeError, match="EdgeSettings"):

        class _Wrong(WireType):
            role = WireRole.VISUAL
            style = dict  # type: ignore[assignment]


def test_the_test_visual_wire_declares_every_recognised_field():
    from haybale_testing.wires import TestVisualStyle, TestVisualWire

    from haywire.core.edge.style import STYLE_FIELDS
    from haywire.core.settings import settings_fields

    assert TestVisualWire.style is TestVisualStyle
    assert tuple(settings_fields(TestVisualStyle)) == STYLE_FIELDS
```

The two wire classes defined inside tests register in `_WIRE_BY_ID` under `__system__:wire:_Plain` and `_Styled`; that is harmless (the 5.1 tests do the same).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_settings/test_edge_settings.py -q -p no:randomly`
Expected: collection error, `ImportError: cannot import name 'EdgeSettings'`.

- [ ] **Step 3: `EdgeSettings`**

Create `packages/haywire-core/src/haywire/core/settings/settings_edge.py`:

```python
# haywire/core/settings/settings_edge.py
"""
EdgeSettings — base class for an edge's style bag.

The Settings flavour parallel to GraphSettings and NodeSettings:

- Per-instance DataField cells; never registered with SettingsRegistry.
- Named by a wire type's ``style``; each edge on that wire type holds one while
  it validates (see ``EdgeWrapper.style``), saved under the edge's ``"style"`` key.
- Carries an ``_edge`` backref; ``_node`` stays None, so promotion is
  unavailable.
"""

from typing import TYPE_CHECKING

from typing_extensions import dataclass_transform

from .descriptor import setting
from .settings import Settings

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.settings.registry import SettingsRegistry


@dataclass_transform(field_specifiers=(setting,))
class EdgeSettings(Settings):
    """Base class for the look a wire type lets the user set per edge.

    Subclass it, declare the fields the user may edit, and name the subclass in
    a wire type's ``style``. A field's default is that wire type's look. The
    canvas draws the fields named in ``haywire.core.edge.style.STYLE_FIELDS``:
    ``color`` (a colour string), ``width`` (px), ``dash`` (a key of
    ``DASH_PATTERNS``), ``arrow_start`` and ``arrow_end`` (a head name, or
    ``"none"``). A field the bag does not declare falls back to the graph's edge
    defaults. Other fields are saved but not drawn.

    Example::

        class NoteStyle(EdgeSettings):
            color = setting[COLOR]("#8e8e8e", label="Colour")
            dash = setting[CHOICES]("solid", label="Dash", widget_config={"options": dash_choices})
            arrow_end = setting[STRING]("arrow", label="End Head", widget={"key": ARROW_HEAD_WIDGET})

        class NoteWire(WireType):
            role = WireRole.VISUAL
            style = NoteStyle
    """

    def __init__(
        self,
        registry: "SettingsRegistry | None" = None,
        edge: "EdgeWrapper | None" = None,
    ) -> None:
        super().__init__(registry=registry, node=None)
        # Back-reference to the owning edge (None for standalone/test bags).
        self._edge: "EdgeWrapper | None" = edge
```

In `packages/haywire-core/src/haywire/core/settings/__init__.py`, add after the `GraphSettings` import:

```python
from .settings_edge import EdgeSettings
```

and `"EdgeSettings",` after `"GraphSettings",` in `__all__`.

- [ ] **Step 4: The style vocabulary**

Create `packages/haywire-core/src/haywire/core/edge/style.py`:

```python
"""Edge style: the fields a style bag can declare for the canvas to draw, and the dash vocabulary.

A wire type's style bag (``EdgeSettings``) may declare any fields; the canvas
draws the ones named here. Heads come from ``haywire.core.edge.arrow_heads``.
"""

#: The style fields the canvas draws, in the order a bag usually declares them.
STYLE_FIELDS: tuple[str, ...] = ("color", "width", "dash", "arrow_start", "arrow_end")

#: A ``dash`` field's values and the SVG dash pattern each draws, in px.
DASH_PATTERNS: dict[str, str] = {"solid": "", "dashed": "8,4", "dotted": "2,4"}


def dash_choices() -> dict[str, str]:
    """Return the ``dash`` options for a choices widget, value to label."""
    return {"solid": "Solid", "dashed": "Dashed", "dotted": "Dotted"}
```

- [ ] **Step 5: `WireType.style`**

In `packages/haywire-core/src/haywire/core/types/wire.py`:

1. Add under `from __future__ import annotations`:

```python
from typing import TYPE_CHECKING, Any, ClassVar
```

(replacing `from typing import Any, ClassVar`), and after the imports:

```python
if TYPE_CHECKING:
    from haywire.core.settings.settings_edge import EdgeSettings
```

2. In the `WireType` docstring's `Attributes:`, after `holds_absence`:

```
        style: The ``EdgeSettings`` subclass each edge of this wire type carries,
            holding what the user may set per edge, or ``None`` for a computed
            edge whose look comes from its pins and the graph's edge defaults.
```

and under `Raises:` add:

```
        TypeError: When ``style`` is neither ``None`` nor an ``EdgeSettings`` subclass.
```

3. After `holds_absence: ClassVar[bool] = False`:

```python
    style: ClassVar[type[EdgeSettings] | None] = None
```

4. In `__init_subclass__`, directly after the `if getattr(cls, "role", None) is None: return` guard:

```python
        style = cls.__dict__.get("style")
        if style is not None:
            # Imported here: settings import the builtin types, which import wire types.
            from haywire.core.settings.settings_edge import EdgeSettings

            if not (isinstance(style, type) and issubclass(style, EdgeSettings)):
                raise TypeError(
                    f"{cls.__qualname__}.style must be an EdgeSettings subclass or None, got {style!r}"
                )
```

- [ ] **Step 6: The test-only bag**

Replace `barn/haybale-testing/haybale_testing/wires.py` with:

```python
"""Test-only wire types."""

from haywire.barn.builtin.types import CHOICES, COLOR, FLOAT, STRING
from haywire.barn.builtin.widget_keys import ARROW_HEAD_WIDGET
from haywire.core.edge.arrow_heads import NO_HEAD
from haywire.core.edge.style import dash_choices
from haywire.core.settings import EdgeSettings, setting
from haywire.core.types import WireRole, WireType


class TestVisualStyle(EdgeSettings):
    """The style of a test visual edge: every field the canvas draws."""

    color = setting[COLOR]("#8e8e8e", label="Colour")
    width = setting[FLOAT](2.0, label="Width", min=0.5, max=12.0)
    dash = setting[CHOICES]("solid", label="Dash", widget_config={"options": dash_choices})
    arrow_start = setting[STRING](NO_HEAD, label="Start Head", widget={"key": ARROW_HEAD_WIDGET})
    arrow_end = setting[STRING]("arrow", label="End Head", widget={"key": ARROW_HEAD_WIDGET})


class TestVisualWire(WireType):
    """A drawn-only wire for tests: saved and drawn, never executed, styled per edge."""

    role = WireRole.VISUAL
    propagation = ()
    pin_kind = "test_visual"
    style = TestVisualStyle
```

Check the import works before running tests: `uv run python -c "from haybale_testing.wires import TestVisualWire; print(TestVisualWire.style)"`. If it raises a circular import, move the builtin imports inside a function is not possible for class bodies; instead report the cycle to the controller.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/core/test_settings/test_edge_settings.py tests/core/test_types -q -p no:randomly`
Expected: all pass.

- [ ] **Step 8: Ruff, mypy on the touched files, commit**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/settings packages/haywire-core/src/haywire/core/edge/style.py packages/haywire-core/src/haywire/core/types/wire.py barn/haybale-testing/haybale_testing/wires.py tests/core/test_settings/test_edge_settings.py
uv run ruff format --check packages/haywire-core/src/haywire/core/settings packages/haywire-core/src/haywire/core/edge/style.py packages/haywire-core/src/haywire/core/types/wire.py barn/haybale-testing/haybale_testing/wires.py tests/core/test_settings/test_edge_settings.py
uv run mypy packages/haywire-core/src/haywire/core/settings packages/haywire-core/src/haywire/core/types/wire.py barn/haybale-testing/haybale_testing/wires.py
git add barn/haybale-testing/haybale_testing/wires.py
git commit -m "test(testing): the test visual wire declares a style bag

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git add packages/haywire-core/src/haywire/core/settings/settings_edge.py packages/haywire-core/src/haywire/core/settings/__init__.py packages/haywire-core/src/haywire/core/edge/style.py packages/haywire-core/src/haywire/core/types/wire.py tests/core/test_settings/test_edge_settings.py
git commit -m "feat(settings): EdgeSettings, the style bag a wire type names

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(The haybale-testing commit needs `EdgeSettings` importable; if the hook or a test run in between needs it, commit both in one commit instead, haybale-testing path included.)

---

### Task 2: The bag's lifetime on the edge, save and load

**Files:**
- Create: `tests/core/test_edge/test_edge_style.py`
- Modify: `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py` (`__init__` 111-181, `redraw` area 285-300, `build` 540-563, `serialize` 888-898, `cleanup` 918-935)
- Modify: `packages/haywire-core/src/haywire/core/graph/types.py` (enum, `requires_redraw`)
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py` (`create_edge_wrapper` 592-624, `to_dict` 913, `load_from_dict` 1018-1025)
- Modify: `packages/haywire-core/src/haywire/core/graph/clipboard.py:76`
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:1386` (collapse's edge capture)

**Interfaces:**
- Consumes: Task 1's `EdgeSettings`, `WireType.style`, `TestVisualStyle`.
- Produces: `EdgeWrapper(..., style: Mapping[str, Any] | None = None)`; `EdgeWrapper.style -> EdgeSettings | None`; `EdgeWrapper.style_values() -> dict[str, Any]`; `EdgeWrapper.mark_style_changed() -> None`; `EdgeWrapper.serialize()` adds `"style"` when non-empty; `BaseGraph.create_edge_wrapper(..., propagation=..., style: Mapping[str, Any] | None = None)`; `ChangeReason.EDGE_STYLE_CHANGED`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_edge/test_edge_style.py`:

```python
"""An edge's style bag: bound while the edge validates, saved under "style", rebound on a new class."""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.settings import EdgeSettings, setting

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Edge Style Graph", validation_scheduler=SyncScheduler())


def _probe_key():
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _visual_edge(graph, **kwargs):
    source = make_node(graph, _probe_key(), position=(0, 0))
    sink = make_node(graph, _probe_key(), position=(300, 0))
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in", **kwargs)
    graph.force_validation()
    return source, sink, edge


def test_a_styled_edge_has_a_bag_of_its_wire_types_class(graph):
    from haybale_testing.wires import TestVisualStyle

    _, _, edge = _visual_edge(graph)
    assert isinstance(edge.style, TestVisualStyle)
    assert edge.style._edge is edge


def test_a_computed_edge_has_no_bag(graph):
    a = make_node(graph, "haybale-testing:node:TestAddFloatNode", position=(0, 0))
    b = make_node(graph, "haybale-testing:node:TestAddFloatNode", position=(300, 0))
    edge = make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()
    assert edge.style is None
    assert "style" not in edge.serialize()


def test_an_unset_style_saves_no_key(graph):
    _, _, edge = _visual_edge(graph)
    assert "style" not in edge.serialize()


def test_a_set_value_saves_and_loads(graph):
    _, _, edge = _visual_edge(graph)
    assert edge.style is not None
    edge.style.color = "#ff0000"
    assert edge.serialize()["style"] == {"color": "#ff0000"}

    data = graph.to_dict()
    loaded = BaseGraph(filestem="Loaded", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(data)
    loaded.force_validation()
    (reloaded,) = loaded.edge_wrappers.values()
    assert reloaded.style is not None
    assert reloaded.style.color == "#ff0000"


def test_a_style_passed_at_creation_is_bound(graph):
    _, _, edge = _visual_edge(graph, style={"width": 6.0, "unknown": 1})
    assert edge.style is not None
    assert edge.style.width == 6.0
    # Q26: a key the bag does not declare is skipped and gone at the next save.
    assert edge.serialize()["style"] == {"width": 6.0}


def test_a_failing_edge_keeps_its_style_verbatim_and_rebinds_it(graph):
    from haybale_testing.types import TEST_VISUAL

    source = make_node(graph, _probe_key(), position=(0, 0))
    sink = make_node(graph, _probe_key(), position=(300, 0))
    # The inlet does not exist yet: the edge fails formal validation ("Ports not found").
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "late_in", style={"color": "#00ff00"})
    graph.force_validation()
    assert not edge.is_valid()
    assert edge.style is None
    assert edge.serialize()["style"] == {"color": "#00ff00"}

    sink.node.add(TEST_VISUAL.as_inlet("late_in"))
    graph.request_node_revalidation(sink.node_id)
    graph.force_validation()
    assert edge.is_valid()
    assert edge.style is not None
    assert edge.style.color == "#00ff00"


def test_a_new_bag_class_takes_the_old_values(graph, monkeypatch):
    from haybale_testing.wires import TestVisualWire

    from haywire.barn.builtin.types import COLOR

    _, _, edge = _visual_edge(graph)
    assert edge.style is not None
    edge.style.color = "#123456"
    edge.style.width = 4.0
    old_bag = edge.style

    class Narrower(EdgeSettings):
        color = setting[COLOR]("#000000", label="Colour")

    monkeypatch.setattr(TestVisualWire, "style", Narrower)
    graph.request_edge_revalidation(edge.edge_id)
    graph.force_validation()

    assert isinstance(edge.style, Narrower)
    assert edge.style is not old_bag
    assert edge.style.color == "#123456"
    assert edge.serialize()["style"] == {"color": "#123456"}, "width is not declared any more"
    assert old_bag._cleaned_up


def test_a_style_edit_marks_the_edge_style_changed(graph):
    _, _, edge = _visual_edge(graph)
    assert edge.style is not None
    marks = []
    original = graph._validation.mark_edge_dirty
    graph._validation.mark_edge_dirty = lambda edge_id, reason: (  # type: ignore[method-assign]
        marks.append(reason),
        original(edge_id, reason),
    )
    edge.style.dash = "dotted"
    assert ChangeReason.EDGE_STYLE_CHANGED in marks


def test_edge_style_changed_redraws_and_persists():
    reason = ChangeReason.EDGE_STYLE_CHANGED
    assert reason.requires_redraw()
    assert not reason.is_visual_only()


def test_cleanup_releases_the_bag(graph):
    _, _, edge = _visual_edge(graph)
    bag = edge.style
    assert bag is not None
    graph.remove_edge_wrapper(edge.edge_id)
    edge.cleanup()
    assert bag._cleaned_up
```

Notes for the implementer, before running:

- `sink.node.add(...)` after construction: check how a dynamic port is added to a live node in `tests/core/test_types/test_add_type.py`. If a bare `add` needs a `rejig()` block or a `mark_as_structuraly_dirty()` to reach the edge, use what that file does; the assertions stay.
- `graph.force_validation()` versus `force_immediate_validation()`: the graph here uses `SyncScheduler` (ADR 0002); `test_edge_propagation_menu_poll.py` uses `force_validation()` the same way.
- `test_a_style_edit_marks_the_edge_style_changed` patches the instance attribute; if `_validation` is a slotted object, use `monkeypatch.setattr(graph._validation, "mark_edge_dirty", ...)` instead.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_edge/test_edge_style.py -q -p no:randomly`
Expected: failures on `edge.style` (`AttributeError`) and on `EDGE_STYLE_CHANGED`.

- [ ] **Step 3: `EDGE_STYLE_CHANGED`**

In `packages/haywire-core/src/haywire/core/graph/types.py`, after `EDGE_REDRAW_REQUESTED = "edge_redraw_requested"`:

```python

    # Edge reason that persists a look without changing structure
    EDGE_STYLE_CHANGED = "edge_style_changed"
    """An edge's style bag changed: the edge redraws and the graph saves."""
```

Add `ChangeReason.EDGE_STYLE_CHANGED,` to the set in `requires_redraw()`, after `ChangeReason.EDGE_REDRAW_REQUESTED,`. In `is_visual_only()`'s docstring, extend the sentence on `NODE_MOVED` to: "``NODE_MOVED``, ``NODE_LAYOUT_CHANGED`` and ``EDGE_STYLE_CHANGED`` are not visual-only: all three repaint, and all three persist — position as ``props.posX``/``posY``, port order as ``DataPort.order``, an edge's look under its ``"style"`` key." Do not add it to `visual_reasons`.

Check every exhaustive match on `ChangeReason` still holds: `grep -rn "EDGE_REDRAW_REQUESTED" packages barn tests --include='*.py'`. A site that lists edge reasons by hand (a test asserting the full set, a priority table) gets the new member next to `EDGE_REDRAW_REQUESTED`.

- [ ] **Step 4: `EdgeWrapper` binds, unbinds and saves the bag**

In `packages/haywire-core/src/haywire/core/edge/edge_wrapper.py`:

1. Imports: add `Mapping` to the `typing` import, and under `TYPE_CHECKING`:

```python
    from haywire.core.settings.settings_edge import EdgeSettings
```

2. `__init__`: new last parameter `style: Optional[Mapping[str, Any]] = None`, documented in `Args:` as

```
            style: The edge's saved style values by field name, as ``serialize`` writes them under
                ``"style"``. They are bound to the wire type's style bag once the edge validates.
```

and at the end of `__init__`, before the adapter-factory subscription:

```python
        # The style bag, bound while the edge validates; see _bind_style.
        self._style: Optional["EdgeSettings"] = None
        # The style values while no bag holds them: before the first validation, and while the edge fails.
        self._unbound_style: Dict[str, Any] = dict(style or {})
```

3. After the `propagation` setter, a new section:

```python
    # =========================================================================
    # STYLE
    # =========================================================================

    @property
    def style(self) -> Optional["EdgeSettings"]:
        """The edge's style bag, or ``None`` when its wire type declares none or the edge does not validate."""
        return self._style

    def style_values(self) -> Dict[str, Any]:
        """Return the edge's locally set style values by field name, as saved under ``"style"``.

        While the edge does not validate, these are the values it was loaded or
        created with, unchanged.
        """
        if self._style is not None:
            return dict(self._style._to_dict()["values"])
        return dict(self._unbound_style)

    def mark_style_changed(self) -> None:
        """Mark the edge's look changed: it redraws, and the graph records an unsaved change."""
        if self._graph:
            self._graph._validation.mark_edge_dirty(self._edge_id, ChangeReason.EDGE_STYLE_CHANGED)

    def _bind_style(self) -> None:
        """Give the edge a bag of its wire type's style class, carrying the values it holds."""
        wire = self.wire_type
        wanted = wire.style if wire is not None else None
        # Identity on purpose: a hot-reloaded bag class is a new object, and must rebind.
        if self._style is not None and type(self._style) is wanted:
            return
        values = self.style_values()
        self._release_style()
        self._unbound_style = {}
        if wanted is None:
            return
        from haywire.core.di.context import get_settings_registry

        bag = wanted(registry=get_settings_registry(), edge=self)
        bag._from_dict({"values": values})
        bag._subscribe(self._on_style_change)
        self._style = bag

    def _unbind_style(self) -> None:
        """Drop the bag of an edge that no longer validates, keeping its values as they are."""
        if self._style is None:
            return
        self._unbound_style = self.style_values()
        self._release_style()

    def _release_style(self) -> None:
        if self._style is not None:
            self._style._cleanup()
            self._style = None

    def _on_style_change(self, _name: str, _value: Any, _old: Any) -> None:
        self.mark_style_changed()
```

4. `build()`: replace the body from `if self._formal_validation():` to the end with:

```python
        if not self._formal_validation():
            # Q20: an edge that fails keeps its style unchanged until it validates again.
            self._unbind_style()
            logger.debug(".. rebuilding failed with errors.")
            return

        self._fit_propagation()
        self._bind_style()
        if not self.carries_values:
            self._build_drawn_only()
            logger.debug(".. drawn-only edge built.")
            return
        if self._build_adapter_chain():
            if self._test():
                logger.debug(".. rebuilding edge done.")
                return

        logger.debug(".. rebuilding failed with errors.")
```

5. `serialize()`:

```python
    def serialize(self) -> Dict[str, Any]:
        """Return the edge as a graph saves it: ``Edge.to_dict`` plus ``"style"`` when any style value is set."""
        data = self._edge.to_dict()
        style = self.style_values()
        if style:
            data["style"] = style
        return data
```

6. `cleanup()`: after `self.detach()`:

```python
        self._release_style()
```

`get_settings_registry()` raises when DI is not configured. Every construction site of an `EdgeWrapper` is a graph, and `BaseGraph.__init__` calls the same function, so this adds no new precondition.

- [ ] **Step 5: Every save path calls `serialize()`; load and create pass the style**

1. `packages/haywire-core/src/haywire/core/graph/base.py:913`: `wrapper.edge.to_dict()` → `wrapper.serialize()`.
2. `packages/haywire-core/src/haywire/core/graph/clipboard.py:76`: `edge_wrapper.edge.to_dict()` → `edge_wrapper.serialize()`.
3. `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:1386` (collapse's capture of internal edges): `edge.edge.to_dict()` → `edge.serialize()`.
4. Search for any other: `grep -rn "\.edge\.to_dict()" packages barn --include='*.py'`. Expected: none left outside tests.
5. `create_edge_wrapper` (`base.py:592`): new parameter `style: Optional[Mapping[str, Any]] = None` after `propagation`, documented as `style: The edge's saved style values (see ``EdgeWrapper.serialize``).`, passed on as `style=style`. Add `Mapping` to the module's `typing` import.
6. `load_from_dict` (`base.py:1018`): add `style=edge_data.get("style"),` to the `EdgeWrapper(...)` call.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_edge/ tests/core/test_graph/ tests/core/test_undo/ tests/core/test_settings/ -q -p no:randomly`
Expected: all pass. A failure in a test that compares a saved edge dict to a literal is expected only if that edge is on `TestVisualWire` and the test set a style; any other is a bug.

- [ ] **Step 7: Ruff, mypy, commit**

Run the ruff check and mypy on the touched files.

```bash
git add packages/haywire-core/src/haywire/core/edge/edge_wrapper.py packages/haywire-core/src/haywire/core/graph/types.py packages/haywire-core/src/haywire/core/graph/base.py packages/haywire-core/src/haywire/core/graph/clipboard.py packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py tests/core/test_edge/test_edge_style.py
git commit -m "feat(edges): an edge carries its wire type's style bag while it validates, and saves it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Re-created edges keep their propagation and style

**Files:**
- Create: `tests/core/test_graph/test_edge_carry.py`
- Modify: `packages/haywire-core/src/haywire/core/graph/utils/node_remap.py` (`RemappedEdge`, `remap_node_ids`)
- Modify: `packages/haywire-core/src/haywire/core/graph/subgraph.py:212-219`
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` (`AddEdgeAction` 108-170; paste 587-596; `_BuildSubgraphAction` 1086-1092; expand 1566-1575)

**Interfaces:**
- Consumes: Task 2's `create_edge_wrapper(..., style=)`, `EdgeWrapper.serialize()`.
- Produces: `RemappedEdge.style: dict[str, Any]`; `AddEdgeAction(..., propagation: Propagation = Propagation.EAGER, style: Mapping[str, Any] | None = None)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_graph/test_edge_carry.py`:

```python
"""Paste, Subgraph instantiation, collapse and expand keep an edge's propagation and style (Q27, C3)."""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import Propagation

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


_ADD = "haybale-testing:node:TestAddFloatNode"
_CARD = "haywire-core:node:GraphNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Carry Graph", validation_scheduler=SyncScheduler())


def _probe_key():
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _pair(graph):
    """A lazy data edge between two adders, and a styled visual edge between two probes."""
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    lazy = make_edge(graph, a.node_id, "result", b.node_id, "value_a", propagation=Propagation.LAZY)
    p = make_node(graph, _probe_key(), position=(0, 200))
    q = make_node(graph, _probe_key(), position=(300, 200))
    styled = make_edge(graph, p.node_id, "note_out", q.node_id, "note_in", style={"color": "#ff0000"})
    graph.force_validation()
    return [a, b, p, q], lazy, styled


def _edges_by_port(graph):
    return {(e.outlet_port_id, e.inlet_port_id): e for e in graph.edge_wrappers.values()}


def test_remap_carries_style():
    from haywire.core.graph.utils.node_remap import remap_node_ids

    remap = remap_node_ids(
        nodes={"n1": {"registry_key": "k"}, "n2": {"registry_key": "k"}},
        edges={
            "e": {
                "source_node_id": "n1",
                "outlet_port_id": "o",
                "sink_node_id": "n2",
                "inlet_port_id": "i",
                "propagation": "lazy",
                "style": {"color": "#ff0000"},
            }
        },
        mint_id=lambda key: f"new_{id(object())}",
    )
    (edge,) = remap.edges
    assert edge.propagation == "lazy"
    assert edge.style == {"color": "#ff0000"}


def test_paste_keeps_propagation_and_style(graph):
    from haywire.core.graph.clipboard import build_clipboard_payload
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction

    nodes, lazy, styled = _pair(graph)
    payload = build_clipboard_payload(
        graph, [n.node_id for n in nodes], [lazy.edge_id, styled.edge_id], session_id="test"
    )
    paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=0.0, paste_y=600.0)
    paste.execute()
    graph.force_validation()

    pasted = [graph.get_edge_wrapper(edge_id) for edge_id in paste.new_edge_ids]
    lazy_copy = next(e for e in pasted if e is not None and e.outlet_port_id == "result")
    styled_copy = next(e for e in pasted if e is not None and e.outlet_port_id == "note_out")
    assert lazy_copy.propagation is Propagation.LAZY
    assert styled_copy.style is not None and styled_copy.style.color == "#ff0000"


def test_instantiate_keeps_propagation_and_style(graph):
    from haywire.core.graph.subgraph import SubgraphDefinition

    nodes, lazy, styled = _pair(graph)
    definition = graph.add_subgraph(SubgraphDefinition(key="carry", validation_scheduler=SyncScheduler()))
    definition.instantiate(
        {n.node_id: n.serialize(include_data=True) for n in nodes},
        {lazy.edge_id: lazy.serialize(), styled.edge_id: styled.serialize()},
    )
    definition.force_validation()
    edges = _edges_by_port(definition)
    assert edges[("result", "value_a")].propagation is Propagation.LAZY
    styled_copy = edges[("note_out", "note_in")]
    assert styled_copy.style is not None and styled_copy.style.color == "#ff0000"


def test_collapse_and_expand_keep_propagation_and_style(graph):
    from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction, ExpandGraphNodeAction

    nodes, _, _ = _pair(graph)
    collapse = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=[n.node_id for n in nodes],
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label="Group",
    )
    collapse.execute()
    graph.force_validation()
    definition = graph.get_subgraph(collapse.subgraph_key)
    assert definition is not None
    definition.force_validation()
    inside = _edges_by_port(definition)
    assert inside[("result", "value_a")].propagation is Propagation.LAZY
    assert inside[("note_out", "note_in")].style.color == "#ff0000"

    ExpandGraphNodeAction(graph=graph, node_id=collapse.card_node_id).execute()
    graph.force_validation()
    back = _edges_by_port(graph)
    assert back[("result", "value_a")].propagation is Propagation.LAZY
    assert back[("note_out", "note_in")].style.color == "#ff0000"
```

If `add_subgraph` needs the definition built differently (a scheduler check, see `.insights/project_subgraph_scheduler_deadlock.md`), copy the construction from a test that calls `instantiate(` (`grep -rln "\.instantiate(" tests`). The assertions stay.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_graph/test_edge_carry.py -q -p no:randomly`
Expected: `test_remap_carries_style` fails on `RemappedEdge` having no `style`; the other three fail on `Propagation.EAGER` (lazy dropped) and `style is None`.

- [ ] **Step 3: `RemappedEdge.style`**

In `node_remap.py`, add after `chain_adapter_keys`:

```python
    style: dict[str, Any] = field(default_factory=dict)
    """The edge's saved style values, as ``EdgeWrapper.serialize`` writes them under ``"style"``."""
```

and in `remap_node_ids`, add to the `RemappedEdge(...)` call:

```python
                style=dict(edge.get("style") or {}),
```

Update the `edges:` entry of the docstring: "in the shape ``EdgeWrapper.serialize`` produces".

- [ ] **Step 4: `AddEdgeAction` takes propagation and style**

In `graph_actions.py`:

1. Imports: `from typing import Any, Optional, Dict, List, Mapping, Tuple` and `from ...types import Propagation` (check the relative path against `edge.py`'s `from ..types import Propagation`; from `core/undo/actions/` it is `...types`).
2. `AddEdgeAction.__init__`: two new parameters before `description`:

```python
        propagation: Propagation = Propagation.EAGER,
        style: Optional[Mapping[str, Any]] = None,
```

documented in `Args:` as

```
            propagation: The mode chosen for the edge; the wire type fits or locks it.
            style: The edge's saved style values (see ``EdgeWrapper.serialize``).
```

stored as `self.propagation = propagation` and `self.style = dict(style or {})`.
3. `_execute_impl`'s first-execution branch:

```python
            self.wrapper = self.graph.create_edge_wrapper(
                self.source_node_id,
                self.outlet_port_id,
                self.sink_node_id,
                self.inlet_port_id,
                propagation=self.propagation,
                style=self.style,
            )
```

4. A module-level helper below `AddEdgeAction`:

```python
def _carried(edge: Mapping[str, Any]) -> Dict[str, Any]:
    """The propagation and style of a serialized edge, as ``AddEdgeAction`` and ``create_edge_wrapper`` take them."""
    return {
        "propagation": Propagation(edge.get("propagation", Propagation.EAGER.value)),
        "style": edge.get("style"),
    }
```

5. Paste (`PasteClipboardAction`, the loop at 587): add `propagation=Propagation(edge.propagation), style=edge.style,` to `AddEdgeAction(...)`.
6. `_BuildSubgraphAction` (1086): `definition.create_edge_wrapper(edge["source_node_id"], edge["outlet_port_id"], edge["sink_node_id"], edge["inlet_port_id"], **_carried(edge))`.
7. Expand (1566): `AddEdgeAction(graph=graph, source_node_id=..., ..., inlet_pin_id=edge.inlet_port_id, **_carried(edge.serialize()))`.

Leave the other `AddEdgeAction` sites (split, dissolve, the card's bridging edges, Detach-from-Macro and Promote-to-Macro bridging) unchanged (C3, F22).

- [ ] **Step 5: Subgraph instantiation**

In `subgraph.py:214`:

```python
                self.create_edge_wrapper(
                    source_node_id=edge.source_node_id,
                    outlet_port_id=edge.outlet_port_id,
                    sink_node_id=edge.sink_node_id,
                    inlet_port_id=edge.inlet_port_id,
                    propagation=Propagation(edge.propagation),
                    style=edge.style,
                )
```

with `Propagation` imported as the module's other core-type imports are. Update the `edges:` docstring entry of `instantiate` to "in the shape ``EdgeWrapper.serialize`` produces".

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/core/test_graph/ tests/core/test_undo/ -q -p no:randomly`
Expected: all pass.

- [ ] **Step 7: Ruff, mypy, commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/utils/node_remap.py packages/haywire-core/src/haywire/core/graph/subgraph.py packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py tests/core/test_graph/test_edge_carry.py
git commit -m "fix(edges): paste, instantiate, collapse and expand keep propagation and style

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The style in the edge's visual state and payload

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py`
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py:455-480`
- Modify: `tests/ui/test_canvas_handlers/test_edge_visual_state.py`, `tests/ui/test_canvas_handlers/test_edge_sync_payload.py`

**Interfaces:**
- Consumes: Task 1's `STYLE_FIELDS`, `DASH_PATTERNS`, `NO_HEAD`; Task 2's `EdgeWrapper.style`.
- Produces: `EdgeVisualState.style: dict[str, Any]` (keys `width: float`, `arrowStart: str`, `arrowEnd: str`, each present only when the bag declares the field); payload key `"style"`; `SyncEdgeAdditionEvent.style: Dict[str, Any]`. Colour and dash: `stroke_color` is the declared `color` instead of `"auto"`, `stroke_dasharray` the declared dash's pattern instead of the chain dash (valid state); in the warning state only the colour is taken.

- [ ] **Step 1: Write the failing tests**

Read both test files first and follow their fixtures. Add to `tests/ui/test_canvas_handlers/test_edge_visual_state.py` (adapt the wrapper stand-in to the file's existing helper; the stand-in needs `style`, `wire_type`, `is_valid()`, `state.has_warning()`, `edge.chain_adapter_keys`, `edge_id`):

```python
from haybale_testing.wires import TestVisualStyle, TestVisualWire


def _styled(**values):
    bag = TestVisualStyle()
    bag._from_dict({"values": values})
    return bag


def test_a_computed_edge_has_no_style():
    state = edge_visual_state(_wrapper(style=None))
    assert state.style == {}
    assert state.stroke_color == "auto"


def test_a_declared_colour_and_dash_replace_gradient_and_chain_dash():
    state = edge_visual_state(_wrapper(style=_styled(color="#ff0000", dash="dotted"), chain=["a"]))
    assert state.stroke_color == "#ff0000"
    assert state.stroke_dasharray == "2,4"


def test_declared_width_and_heads_go_to_the_canvas_style():
    state = edge_visual_state(_wrapper(style=_styled(width=5.0, arrow_start="open")))
    assert state.style == {"width": 5.0, "arrowStart": "open", "arrowEnd": "arrow"}


def test_an_unknown_dash_keeps_the_chain_dash():
    state = edge_visual_state(_wrapper(style=_styled(dash="wavy"), chain=["a"]))
    assert state.stroke_dasharray == calculate_dasharray(1)


def test_the_warning_state_keeps_its_dash_and_takes_the_colour():
    state = edge_visual_state(_wrapper(style=_styled(color="#ff0000", dash="dotted"), warning=True))
    assert state.stroke_color == "#ff0000"
    assert state.stroke_dasharray == "2,2,2,2,2,5,5,5,5,5,5,5"


def test_a_style_change_alone_is_a_visual_change():
    a = edge_visual_state(_wrapper(style=_styled(arrow_end="open")))
    b = edge_visual_state(_wrapper(style=_styled(arrow_end="bar")))
    assert a != b
```

with `_wrapper(style=..., chain=(), warning=False, valid=True)` returning a `SimpleNamespace` cast to `EdgeWrapper` whose `wire_type` is `TestVisualWire` when `style` is given, else `None`. If the existing file builds stand-ins differently, extend its helper instead of adding a second one.

In `tests/ui/test_canvas_handlers/test_edge_sync_payload.py`, the existing key-set test must keep passing once `style` is on both sides; add:

```python
def test_the_payload_carries_the_style():
    state = replace(_state(), style={"width": 5.0})
    assert edge_sync_payload(_wrapper(), state)["style"] == {"width": 5.0}
```

(`_state()` gains `style={}` in its constructor call.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_edge_visual_state.py tests/ui/test_canvas_handlers/test_edge_sync_payload.py -q -p no:randomly`
Expected: failures on `style` (unexpected keyword / missing attribute).

- [ ] **Step 3: Implement**

In `ui_edge.py`:

1. Imports:

```python
from dataclasses import dataclass, field
from typing import Any

from haywire.core.edge.style import DASH_PATTERNS, STYLE_FIELDS
from haywire.core.settings import settings_fields
```

2. `EdgeVisualState`: after `arrow_at`:

```python
    # The declared width and heads, canvas-shaped: "width", "arrowStart", "arrowEnd"
    style: dict[str, Any] = field(default_factory=dict)
```

Place it after `has_warning` instead if the dataclass's field order requires defaults last (it does: `is_valid` and `has_warning` have no defaults). Add `and self.style == other.style` to `__eq__`, and to its docstring: "``style`` takes part because a styled edge's width and heads are drawn from it."

3. A helper above `edge_visual_state`:

```python
def _declared_style(wrapper: EdgeWrapper) -> dict[str, Any]:
    """The recognised style fields the edge's bag declares, with their values; empty without a bag."""
    bag = wrapper.style
    if bag is None:
        return {}
    declared = settings_fields(bag)
    return {name: getattr(bag, name) for name in STYLE_FIELDS if name in declared}


def _canvas_style(style: dict[str, Any]) -> dict[str, Any]:
    """The width and heads of a declared style, keyed as canvas.vue reads them."""
    out: dict[str, Any] = {}
    if "width" in style:
        out["width"] = float(style["width"])
    if "arrow_start" in style:
        out["arrowStart"] = str(style["arrow_start"])
    if "arrow_end" in style:
        out["arrowEnd"] = str(style["arrow_end"])
    return out
```

4. `edge_visual_state`: compute `style = _declared_style(wrapper)` after `arrow_at`. The invalid branch is unchanged (a failing edge has no bag, C7) but passes `style={}`. The warning branch passes `stroke_color=str(style["color"]) if "color" in style else "auto"` and `style=_canvas_style(style)`. The valid branch:

```python
    dash = DASH_PATTERNS.get(style["dash"]) if "dash" in style else None
    return EdgeVisualState(
        edge_id=wrapper.edge_id,
        stroke_color=str(style["color"]) if "color" in style else "auto",  # "auto": gradient from pins
        stroke_dasharray=(
            dash if dash is not None else calculate_dasharray(len(wrapper.edge.chain_adapter_keys))
        ),
        opacity=1.0,
        arrow_at=arrow_at,
        is_valid=True,
        has_warning=False,
        style=_canvas_style(style),
    )
```

Update the policy docstring: "A styled edge's declared colour replaces the gradient in the valid and warning states, and its declared dash replaces the chain dash in the valid state; its width and heads travel in ``style``."

5. `edge_sync_payload`: add `"style": state.style,` after `"opacity"`.

In `event_definitions.py`, `SyncEdgeAdditionEvent`: after `opacity`:

```python
    style: Dict[str, Any] = field(default_factory=dict)  # declared width and heads: width, arrowStart, arrowEnd
```

and the docstring line `- style: A styled edge's declared width and heads (width, arrowStart, arrowEnd)`. Check `field`, `Dict` and `Any` are imported there.

Check `generated/graph_events.js` does not list event fields: `grep -n "opacity" packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`. Expected: no match, so nothing to regenerate. If it does list them, regenerate with `uv run python scripts/generate_vue_events.py` and commit the file with this task.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/ui/test_canvas_handlers/ -q -p no:randomly`
Expected: all pass.

- [ ] **Step 5: Ruff, mypy, commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_edge.py packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py tests/ui/test_canvas_handlers/test_edge_visual_state.py tests/ui/test_canvas_handlers/test_edge_sync_payload.py
git commit -m "feat(canvas): a styled edge's colour, dash, width and heads travel in its sync payload

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: The canvas draws per-edge width and heads (F16)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (`_syncEdgeAddition` 1222-1320; `_createEdge` 2915-3040; `_endIsHeaded`/`_edgeInsets` 3075-3089; `_edgeGeometryLooksWrong` 3283-3322; the edge stylesheet 4125-4157)
- Modify: `tests/ui/harness/routes.py` (`_build_edge_appearance_graph` 255-278; `/graph-edge-appearance` page 1076-1098)
- Create: `tests/ui/harness/test_edge_style.py`

**Interfaces:**
- Consumes: Task 4's payload `style`.
- Produces (JS): `edgeInfo.style`; `_applyEdgeStyle(edgeInfo)`; `_headAt(edgeInfo, end) -> head name`; `_edgeWidthOf(edgeInfo) -> number`; `_endIsHeaded(edgeInfo, end)` (signature changed: takes `edgeInfo`, not `arrowAt`). CSS vars `--hw-edge-head-start` and `--hw-edge-head-end` on edge paths.

- [ ] **Step 1: The harness fixture**

In `_build_edge_appearance_graph`, before `return graph, editor`, add a styled visual edge:

```python
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    probe_key = VisualProbeNode.class_identity.registry_key
    note_a, note_b = node(probe_key, 3600.0, 4450.0), node(probe_key, 3950.0, 4450.0)
    assert editor.create_edge(note_a.node_id, "note_out", note_b.node_id, "note_in")
```

Update the docstring: "…a callback, an invalid one, and a styled one on the test visual wire."

In `graph_edge_appearance_page`, after the `resync-edges` button:

```python
        def _styled_edge():
            return next(e for e in graph.edge_wrappers.values() if e.outlet_port_id == "note_out")

        for testid, field, value in (
            ("style-width-6", "width", 6.0),
            ("style-end-open", "arrow_end", "open"),
            ("style-end-none", "arrow_end", "none"),
            ("style-start-open", "arrow_start", "open"),
            ("style-color-red", "color", "#ff0000"),
            ("style-dash-dotted", "dash", "dotted"),
        ):
            ui.button(
                testid, on_click=lambda _, f=field, v=value: setattr(_styled_edge().style, f, v)
            ).props(f'data-testid="{testid}"')

        def _send_partial_style() -> None:
            # A crafted payload: only arrowEnd declared, so the start end falls through (C6).
            from haybale_graph_editor.editors.graph_canvas.ui_edge import edge_sync_payload, edge_visual_state
            from haywire.ui.components.graph.event_definitions import SyncAllEdgesEvent

            edge = _styled_edge()
            state = edge_visual_state(edge)
            state.style = {"arrowEnd": "open"}
            manager.canvas_vue.emit_sync_event(SyncAllEdgesEvent(edges=[edge_sync_payload(edge, state)]))

        ui.button("style-partial", on_click=_send_partial_style).props('data-testid="style-partial"')
```

Check the import path of `SyncAllEdgesEvent` against `visual_layer.py:51` and use the same.

- [ ] **Step 2: Write the failing browser tests**

Create `tests/ui/harness/test_edge_style.py`:

```python
"""A styled edge in the browser: its own width, heads, colour and dash, set as inline vars and strokes."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.test_edge_appearance import _computed, _distance, _end_point, _pin

_PATH = "/graph-edge-appearance"
_STYLED = 'path.hw-edge[data-edge-id*="[note_out]->"]'
_STYLED_HIT = 'path.hw-edge-hit[data-edge-id*="[note_out]->"]'
_DATA = 'path.hw-edge[data-edge-id*="[result]->"]'

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_STYLED)
    wait_for_canvas_settled(page)


def _click_until(page: Page, testid: str, selector: str, prop: str, predicate) -> str:
    """Click, then wait until the computed *prop* of *selector* satisfies *predicate*; return it."""
    page.click(f'[data-testid="{testid}"]')
    page.wait_for_function(
        """([sel, prop, src]) => {
            const el = document.querySelector(sel);
            return el && (new Function('v', 'return ' + src))(getComputedStyle(el)[prop]);
        }""",
        arg=[selector, prop, predicate],
        timeout=5000,
    )
    return _computed(page, selector, prop)


def test_the_bag_defaults_draw_an_end_head_and_no_start_head(page: Page, harness) -> None:
    _open(page, harness)
    assert "-arrow" in _computed(page, _STYLED, "markerEnd")
    assert _computed(page, _STYLED, "markerStart") == "none"


def test_a_styled_width_is_the_edges_own_and_widens_its_hit_area(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-width-6", _STYLED, "strokeWidth", "v === '6px'")
    assert _computed(page, _STYLED_HIT, "strokeWidth") == "14px"
    assert _computed(page, _DATA, "strokeWidth") == "2px", "a computed edge keeps the graph width"


def test_a_styled_width_wins_over_the_graph_width(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-width-6", _STYLED, "strokeWidth", "v === '6px'")
    _click_until(page, "set-width-4", _DATA, "strokeWidth", "v === '4px'")
    assert _computed(page, _STYLED, "strokeWidth") == "6px"


def test_heads_at_both_ends_shorten_both_ends(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-end-none", _STYLED, "markerEnd", "v === 'none'")
    bare_out = _end_point(page, _STYLED, "outlet")
    bare_in = _end_point(page, _STYLED, "inlet")
    _click_until(page, "style-start-open", _STYLED, "markerStart", "v.includes('-open')")
    _click_until(page, "style-end-open", _STYLED, "markerEnd", "v.includes('-open')")
    # "open" has inset 4; the bag's width is 2.
    assert abs(_distance(_end_point(page, _STYLED, "outlet"), bare_out) - 4.0 * 2) < 0.5
    assert abs(_distance(_end_point(page, _STYLED, "inlet"), bare_in) - 4.0 * 2) < 0.5
    pin = _pin(page, _STYLED, "inlet")
    assert abs(_distance(_end_point(page, _STYLED, "inlet"), pin) - (4.0 * 2 + pin["half"])) < 0.5


def test_a_declared_colour_and_dash_are_drawn(page: Page, harness) -> None:
    _open(page, harness)
    assert _click_until(page, "style-color-red", _STYLED, "stroke", "v === 'rgb(255, 0, 0)'")
    assert _click_until(page, "style-dash-dotted", _STYLED, "strokeDasharray", "v.startsWith('2')")


def test_an_undeclared_start_head_falls_through_to_the_graph_head(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "set-arrow-open", _DATA, "markerEnd", "v.includes('-open')")
    # The test visual wire's arrow_at is INLET, so the computed head sits at the end, not the start.
    _click_until(page, "style-partial", _STYLED, "markerEnd", "v.includes('-open')")
    assert _computed(page, _STYLED, "markerStart") == "none"


def test_the_geometry_check_accepts_an_edge_headed_at_both_ends(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-start-open", _STYLED, "markerStart", "v.includes('-open')")
    page.click('[data-testid="resync-edges"]')
    page.wait_for_timeout(300)
    warnings = page.evaluate("() => (window.__hwConsoleWarnings || []).filter((w) => w.includes('drawn off'))")
    assert warnings == []
```

The last test needs the console warnings. If the harness has no `__hwConsoleWarnings` collector, use Playwright's `page.on("console", ...)` registered before `_open` instead, and assert no message contains "edges drawn off their pins".

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/ui/harness/test_edge_style.py -q -p no:randomly`
Expected: the defaults test fails (no head on the styled edge), the width tests fail (2px), the colour test may already pass (the payload sends `strokeColor` since Task 4): that is fine, keep it.

- [ ] **Step 4: Implement in `canvas.vue`**

1. `_syncEdgeAddition`: add `style = {}` to the destructured fields; in the update branch, after `edgeInfo.opacity = opacity;`:

```js
                edgeInfo.style = style;
                this._applyEdgeStyle(edgeInfo);
```

and pass `style` as a new last argument to `this._createEdge(...)`.

2. `_createEdge`: new last parameter `style = {}`; add `style: style` to `edgeInfo` after `opacity`; after `this.$refs.svg.appendChild(hitArea);` call `this._applyEdgeStyle(edgeInfo);` (the hit area must be in the DOM for `getElementById`).

3. Replace `_endIsHeaded` and `_edgeInsets` with:

```js
        /** The head drawn at the end named `end` ('inlet' | 'outlet'): the edge's own when its
         *  style declares one there, else the graph's head at the end its wire type names. */
        _headAt(edgeInfo, end) {
            const style = edgeInfo.style || {};
            const declared = end === 'outlet' ? style.arrowStart : style.arrowEnd;
            if (declared !== undefined) return declared;
            return edgeInfo.arrowAt === end ? this.edgeArrow : 'none';
        },

        /** The edge's width in SVG units: its style's, else the graph's. */
        _edgeWidthOf(edgeInfo) {
            const width = (edgeInfo.style || {}).width;
            return width !== undefined ? width : this.edgeWidth;
        },

        /** Whether a head is drawn at the end named `end` ('inlet' | 'outlet'). */
        _endIsHeaded(edgeInfo, end) {
            return this.headInsets[this._headAt(edgeInfo, end)] !== undefined;
        },

        /** How far each end stops short of its pin's centre, [outlet, inlet] in SVG units:
         *  the pin's half-size, plus the head's length at a headed end. */
        _edgeInsets(edgeInfo) {
            const headLength = (end) => this._endIsHeaded(edgeInfo, end)
                ? this.headInsets[this._headAt(edgeInfo, end)] * this._edgeWidthOf(edgeInfo) : 0;
            return [
                edgeInfo.outletPinHalf + headLength('outlet'),
                edgeInfo.inletPinHalf + headLength('inlet'),
            ];
        },

        /** Set a styled edge's width and heads as inline vars on its path and hit area; a computed
         *  edge sets none, so the canvas's vars and the arrow class apply. */
        _applyEdgeStyle(edgeInfo) {
            const style = edgeInfo.style || {};
            const hitArea = document.getElementById(edgeInfo.path.getAttribute('id') + '_hitarea');
            const width = style.width !== undefined ? `${style.width}px` : null;
            for (const el of [edgeInfo.path, hitArea]) {
                if (!el) continue;
                if (width) el.style.setProperty('--hw-edge-width', width);
                else el.style.removeProperty('--hw-edge-width');
            }
            const heads = { '--hw-edge-head-start': style.arrowStart, '--hw-edge-head-end': style.arrowEnd };
            for (const [name, head] of Object.entries(heads)) {
                if (head !== undefined) edgeInfo.path.style.setProperty(name, this._headUrl(head));
                else edgeInfo.path.style.removeProperty(name);
            }
        },
```

4. `_edgeGeometryLooksWrong`: replace `const atInlet = this._endIsHeaded(info.arrowAt, 'outlet');` with:

```js
                const outletHeaded = this._endIsHeaded(info, 'outlet');
                // An edge headed at both ends has no end on its pin's edge to measure.
                if (outletHeaded && this._endIsHeaded(info, 'inlet')) continue;
                const atInlet = outletHeaded;
```

and in its comment block replace "Each edge is checked at an end with no head" with "Each edge is checked at an end with no head, and an edge headed at both ends is skipped".

5. Find every other caller of the old signature: `grep -n "_endIsHeaded(" canvas.vue`. Expected: only the ones above.

6. Stylesheet: replace the `path.hw-edge`, `path.hw-edge.edge-arrow-outlet` and `path.hw-edge.edge-arrow-none` rules with:

```css
/* A head per end. The arrow class puts the graph's head at the end the wire
   type names; a styled edge overrides either end with an inline var. */
path.hw-edge {
    stroke-width: var(--hw-edge-width, 2px);
    --hw-edge-head-start: none;
    --hw-edge-head-end: var(--hw-edge-head, none);
    marker-start: var(--hw-edge-head-start);
    marker-end: var(--hw-edge-head-end);
}

path.hw-edge.edge-arrow-outlet {
    --hw-edge-head-start: var(--hw-edge-head, none);
    --hw-edge-head-end: none;
}

path.hw-edge.edge-arrow-none {
    --hw-edge-head-end: none;
}
```

and extend the comment above `.connection-svg` to: "The canvas sets --hw-edge-width, --hw-edge-hit-padding and --hw-edge-head on its SVG; a styled edge sets --hw-edge-width on its path and hit area and --hw-edge-head-start/-end on its path; selected and active add a theme length."

Inline custom properties beat the class rules because an inline declaration is more specific; that is what lets one rule set serve both kinds of edge.

- [ ] **Step 5: Run the browser tests, D's included**

Run: `uv run pytest tests/ui/harness/test_edge_style.py tests/ui/harness/test_edge_appearance.py -q -p no:randomly`
Expected: all pass. D's tests guard the computed path through the new per-end vars.

- [ ] **Step 6: Paint completeness**

Run `paintcheck.py` (see `.insights/project_chrome_paint_completeness.md` for its location and usage) on the edge-appearance harness page after clicking `style-width-6`. Expected: every card and edge painted. Record the result in `.superpowers/sdd/progress.md`.

- [ ] **Step 7: Ruff on the harness, commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue tests/ui/harness/routes.py tests/ui/harness/test_edge_style.py
git commit -m "feat(canvas): a styled edge draws its own width and a head per end (F16)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: The bag in the Edge inspector and the edge menu

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py`
- Create: `tests/ui/panels/test_edge_style_panels.py`
- Maybe modify: `packages/haywire-core/src/haywire/barn/builtin/widgets/arrow_head_widget.py` (Step 1)

**Interfaces:**
- Consumes: Task 2's `EdgeWrapper.style`; `render_settings`.
- Produces: `EdgeStylePanel` (surface `EdgeInspector`, order 8) and `EdgeStyleMenuPanel` (surface `EdgeMenu`, order 15), both polling `active_edge is not None and active_edge.style is not None`.

- [ ] **Step 1: Verify first: a picker inside the edge menu opens on top (C9)**

Start the studio (`haywire-live-studio` skill), open a graph, place two `Visual Probe` nodes from `testing/testbed`, link `note_out` to `note_in`. Then, with a temporary panel in your working tree (the code of Step 4, not committed yet): right-click the edge, click the End Head picker, click "More", pick a head, and click the colour field.

Expected: each picker opens above the menu, a pick applies, and the menu stays open. If the head picker's menu opens beneath the menu, add `.style(FLYOUT_Z)` to the `ui.menu()` in `ArrowHeadWidget` (`arrow_head_widget.py:44`, `FLYOUT_Z` from `haywire.ui.elements.flyout`) and check again. If the colour picker misbehaves, stop and report: do not patch `ColorWidget` in this plan.

- [ ] **Step 2: Write the failing tests**

Create `tests/ui/panels/test_edge_style_panels.py`:

```python
"""The style panels show for an edge with a style bag, and only for one."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels.graph.menu.edge.edge import EdgeStyleMenuPanel
from haybale_graph_editor.panels.properties.introspect.edge import EdgeStylePanel
from haybale_graph_editor.state.edit_state import EditState

pytestmark = pytest.mark.unit


def _ctx(edge):
    return SimpleNamespace(data={EditState: SimpleNamespace(active_edge=edge)})


@pytest.mark.parametrize("panel", [EdgeStylePanel, EdgeStyleMenuPanel])
def test_an_edge_with_a_bag_polls_true(panel):
    assert panel.poll(_ctx(SimpleNamespace(style=object())))


@pytest.mark.parametrize("panel", [EdgeStylePanel, EdgeStyleMenuPanel])
def test_an_edge_without_a_bag_polls_false(panel):
    assert not panel.poll(_ctx(SimpleNamespace(style=None)))


@pytest.mark.parametrize("panel", [EdgeStylePanel, EdgeStyleMenuPanel])
def test_no_edge_polls_false(panel):
    assert not panel.poll(_ctx(None))
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/ui/panels/test_edge_style_panels.py -q -p no:randomly`
Expected: `ImportError` on both panel names.

- [ ] **Step 4: The panels**

In `introspect/edge.py`, import `from haywire.ui.panel.render_utils import render_settings` and add after `EdgeWarningsPanel`:

```python
@panel(
    surface=EdgeInspector,
    label="Style",
    icon=hui.icon.theme,
    order=8,
    default_open=True,
)
class EdgeStylePanel(BasePanel):
    """The connection's colour, line and arrow heads, for a connection type that lets you set them."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edge = ctx.data[EditState].active_edge
        return edge is not None and edge.style is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None or edge.style is None:
            return
        with layout:
            render_settings(ctx, edge.style)
```

In `menu/edge/edge.py`, import `render_settings` the same way and add after `EdgeWarningsMenuPanel`:

```python
@panel(
    surface=EdgeMenu,
    label="Style",
    icon=hui.icon.theme,
    order=15,
)
class EdgeStyleMenuPanel(BasePanel):
    """The connection's colour, line and arrow heads, editable in place.

    The same fields and writes as the Style panel in the properties editor.
    """

    actions: EdgeActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edge = ctx.data[EditState].active_edge
        return edge is not None and edge.style is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        edge = ctx.data[EditState].active_edge
        if edge is None or edge.style is None:
            return
        with layout:
            with ui.column().classes("hw-panel gap-0").style("min-width: 240px"):
                render_settings(ctx, edge.style)
```

Check `hui.icon.theme` exists (`toolbar/appearance.py` uses it) and that `order=15` does not collide with another `EdgeMenu` panel (`grep -n "order=" menu/edge/edge.py`).

- [ ] **Step 5: Run the tests, then repeat Step 1's check with the committed code**

Run: `uv run pytest tests/ui/panels/ -q -p no:randomly`. Expected: all pass. Then repeat Step 1's studio check, plus: a style edit marks the graph tab unsaved (C2), the inspector's Style panel shows the same values, and a save-and-reopen keeps them.

- [ ] **Step 6: Ruff, mypy, commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/edge.py barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/edge/edge.py tests/ui/panels/test_edge_style_panels.py
git commit -m "feat(graph-editor): edit a connection's style in the edge menu and the inspector

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Add `arrow_head_widget.py` to the commit only if Step 1 changed it, with a message line naming why.

---

### Task 7: ADR, glossary, docs and the design's status

**Files:**
- Create: `docs/adr/0047-edge-settings.md`
- Modify: `docs/reference/glossary.md`, `docs/architecture/settings/settings-arch.md`, `docs/components/settings/setting-canon.md`, `docs/architecture/execution/edges/edges-arch.md` (check the path; `find docs -name "edges-arch.md"`), `docs/adr/0045-edge-appearance.md` (Consequences), `docs/superpowers/plans/2026-10-02-wire-types.md` (not committed)

- [ ] **Step 1: ADR 0047**

Follow `docs/reference/doc-authoring.md` and ADR 0045's front matter. Content:

```markdown
---
name: edge-settings
description: EdgeSettings is the fifth settings flavour; a wire type names one as its style bag, and each edge holds one while it validates
status: accepted
see-also: ADR-0022, ADR-0042, ADR-0045
level: architectural
---

# Edge settings: the style bag

**Context.**

- A diagram edge needs its colour, dash, width and heads set per edge (ADR 0045's styled edge).
- Settings already come in four flavours; a graph's bag (ADR 0022) is the template for one owned by an object rather than registered.

**Decision.**

- **`EdgeSettings` is the fifth flavour.** Per-instance cells, an `_edge` back-reference, `_node` always `None`, so promotion is off. It is never registered.
- **A wire type names its bag** in `style`. Its field defaults are that wire type's look. A wire type without one draws computed edges.
- **Lifetime.** `EdgeWrapper.build()` binds a bag of the wire type's class once the edge passes formal validation, and drops it when the edge fails, keeping the values unchanged. A new class (a hot reload, a port retyped to another wire type) takes the old values; keys it does not declare are skipped and gone at the next save, as in node bags.
- **Saving.** The edge saves its locally set values flat under `"style"`. Every save path goes through `EdgeWrapper.serialize()`. Paste, Subgraph instantiation, collapse and expand carry `"style"` and `"propagation"`.
- **Editing.** A style change marks `EDGE_STYLE_CHANGED`: the edge redraws and the graph records an unsaved change. The edge menu and the Edge inspector render the bag with the shared settings renderer.
- **Drawing.** A declared `color` and `dash` replace the pin gradient and the chain dash in the edge's stroke; a declared `width`, `arrow_start` and `arrow_end` become inline vars on the edge's path and hit area. An undeclared field falls back per field, and per end for heads, to the graph's edge defaults. The invalid colour and the warning glow still win.

**Alternatives.**

- *Colour and dash as inline vars too.* The stroke fields already carry them, and the state policy already ranks the overlays above them.
- *Keeping the bag on an edge that fails validation.* Its wire type may be the wrong one; the values are kept as data until it validates.

**Consequences.**

- A library defines a styled wire with two classes: an `EdgeSettings` subclass and a wire type naming it.
- Style edits are not undoable, like node and graph settings edits.
- Splitting or dissolving a reroute on a styled edge does not carry its style.
```

- [ ] **Step 2: Glossary.** Add a row after **Styled edge**: `| **Style bag** | The `EdgeSettings` subclass a wire type names in `style`: the fields of a **Styled edge** the user may set. Each edge holds one while it validates and saves its set values under `"style"`. See [ADR 0047](../adr/0047-edge-settings.md) | edge style settings |`. In the **Wire type** row, add `style` next to `arrow_at`: "`style` names the **Style bag** of a **Styled edge**".
- [ ] **Step 3: settings-arch.md.** Add `EdgeSettings` to the schema-class table in §6.1 (owner: an edge; registered: no; serialized: the edge's `"style"`; promotion: no) and a paragraph after the `GraphSettings` description with the lifetime rule. Add the Q33 fact: a node or edge bag skips an unknown key on load and drops it at the next save, so a renamed field loses its value.
- [ ] **Step 4: setting-canon.md.** A short "Edge style bags" section: when to declare one, the five recognised fields and their value types, `dash_choices`, `ARROW_HEAD_WIDGET`, the example from `EdgeSettings`'s docstring.
- [ ] **Step 5: edges-arch.md.** The bag's lifetime in `build()`, `serialize()` as the one save path, and `EDGE_STYLE_CHANGED`.
- [ ] **Step 6: ADR 0045.** In Consequences, the bullet "5.4 builds on the same vars…" becomes: "Styled edges set `--hw-edge-width` on their path and hit area and `--hw-edge-head-start`/`--hw-edge-head-end` on their path (ADR 0047); the canvas reads each edge's own width and heads for its insets, hit area and geometry check."
- [ ] **Step 7: The design doc (not committed).** In `2026-10-02-wire-types.md`: status row 5.4 → "**Landed** on branch `wire-types-5-1` <date>, not merged" with this plan's link (moved to `landed/` by the user); the 5.4 section drops the fallback glyph (C1); tick F16; add F22 (split/dissolve/bridging carry nothing), F23 (undoable style edits), F24 (Farmhand edge style) under a new "From 5.4" heading; mark the Small item "Paste and Subgraph instantiation drop an edge's `propagation`" done with this plan's commit; the "Facts found" row "Paste and Subgraph instantiation drop `propagation`" gains "(and collapse, expand; C3)".
- [ ] **Step 8: Build the docs.** `uv run mkdocs build 2>&1 | grep -iE "warning|error" | grep -v "insights"` shows nothing new against the baseline.
- [ ] **Step 9: Commit**

```bash
git add docs/adr/0047-edge-settings.md docs/adr/0045-edge-appearance.md docs/reference/glossary.md docs/architecture/settings/settings-arch.md docs/components/settings/setting-canon.md docs/architecture/execution/edges/edges-arch.md
git commit -m "docs: edge settings, the style bag (ADR 0047)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

(Adjust the edges-arch path to what Step 5 found. If the baked docs need regenerating, as in 5.1, run `scripts/bake_docs.py` and commit its output in this commit.)

---

### Task 8: Verify the plan

- [ ] **Step 1: Full checks.** Pre-commit gate, browser tier, visiongraph tests, mypy set, ruff (both commands). All green; compare counts with Task 0 (new tests only added).
- [ ] **Step 2: Saved graphs unchanged.** `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_after_5_4.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`, then `diff /tmp/graph_snapshot_before_5_4.json /tmp/graph_snapshot_after_5_4.json`. Expected: no difference.
- [ ] **Step 3: Benchmark.** Run the `haywire-benchmark` skill; compare with Task 0. A regression in an edge-heavy case is a finding to report (the bag check runs per edge per validation).
- [ ] **Step 4: Live studio.** With the `haywire-live-studio` skill:
  1. Two Visual Probe nodes linked: the edge draws grey with an end arrow; change colour, dash, width and both heads in the edge menu; each change shows at once and marks the tab unsaved.
  2. Save, close, reopen: the look is kept.
  3. Copy both nodes and paste: the copy keeps the look. Collapse both into a Group, open it: the look is kept inside; expand: kept.
  4. A data edge set to Lazy, copied and pasted: the copy is Lazy.
  5. Remove `note_out` from the source probe through the pin menu: the edge draws invalid (danger colour); add the pin back through the node (or reload the graph): the look returns.
  6. Set the graph's edge arrow and width: computed edges change, the styled edge keeps its own width and heads.
  7. `.scratch/edgecheck.js` in the browser console reports no edge off its pin.
- [ ] **Step 5: Report** to the user: commits, counts, findings, and the follow-ups added.

---

## Self-review (done while writing)

- **Design coverage.** `EdgeSettings` (Task 1); `style` class attribute (Task 1); `"style"` key (Task 2); lifetime in `build()`, bound only while validating, unknown keys skipped (Task 2); `RemappedEdge` carrying style and propagation (Task 3, widened by C3); declared fields in payload and `__eq__` (Task 4); inline vars on the path (Task 5, narrowed by C5); fallback glyph (C1, nothing to do); edge menu and `EdgeInspector` rendering with `ArrowHeadWidget` (Task 6, through `TestVisualStyle`'s widget keys); verify-first hot-reload rebind (Task 2's `test_a_new_bag_class_takes_the_old_values`, which swaps the class the way a reload does; the reload reaching `build()` is 5.1's Task 3 plus the type registry's cascade); paste and Subgraph instantiation keep `LAZY` and style (Task 3); browser checks (Tasks 5, 6, 8); F16's four items (Task 5: insets, hit area width, two head vars, geometry check); ADR "EdgeSettings as the fifth flavour" and the Q33 settings-docs fact (Task 7).
- **Placeholders.** None. Three spots say what to check if a call's shape differs (adding a port to a live node in Task 2, `add_subgraph` in Task 3, the console collector in Task 5); the assertions are fixed.
- **Names.** `style_values()`, `mark_style_changed()`, `EDGE_STYLE_CHANGED`, `_carried()`, `_headAt`, `_edgeWidthOf`, `_applyEdgeStyle`, `--hw-edge-head-start`/`-end` are used with the same spelling in every task.
