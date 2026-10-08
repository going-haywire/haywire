# The annotation wire, type, node and skin (edge-kinds step 5.5) Implementation Plan

> **Superseded** by [2026-10-05-diagram-annotations.md](2026-10-05-diagram-annotations.md): built and live-checked on branch `diagram-annotations`, but its pin model (an inlet and an outlet slot per side) is the blocker that plan addresses. Kept as the record of what was built.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Builtin ships a diagram layer. The user drops annotation nodes (boxes of text) on any graph and links them with styled arrows. The arrows are drawn and saved but never executed. Each card edge grows pins where the user connects. The text is edited in the properties panel or, after a double-click on the card, in the text modal.

**Architecture:**

- **Wire and type.** `AnnotationWire` is a `VISUAL` wire with a style bag, `AnnotationStyle`, that declares all five recognised fields. `ANNOTATION` is a `STRING` on that wire. It has no widget and stores nothing.
- **Node.** `AnnotationNode` is a builtin `CONTROL` node:
  - an `exec`/`done` pair that passes control and its payload through;
  - eight growing `ADD[ANNOTATION]` slots, one inlet and one outlet per card side. The side is recorded in the port-id prefix, and indices are never reused;
  - a props subclass that binds the skin by key string and adds `text` and `show_control_pins`.
- **Skin.** `AnnotationSkin` lives in builtin and subclasses `BaseSkin`:
  - each card side gets an absolutely positioned pin strip, on the reroute skin's pattern;
  - every pin is rendered through `render_pin` with the one `LayoutDirection` that puts it on its side;
  - the skin renders the ghost pins, the text, and a `dblclick` listener that opens `text_modal`.
- **Canvas.** `canvas.vue` gains two generic pieces: an `edge-dragging` container class while an edge drag is active, and a `hw-pin-reveal` pin class that is `visibility: hidden` except while its card is hovered or an edge drag is active.

**Tech Stack:** Python 3.12, NiceGUI/Vue 3 (`canvas.vue`), pytest (+ xdist, Playwright browser tier), uv, ruff, mypy.

**Settled in:** [2026-10-02-wire-types.md](2026-10-02-wire-types.md): sections "The annotation node (Q16 to Q16e)", "Visual wires", "Edge style", "5.5" and "D", and decisions Q16, Q28, Q48, Q50 and Q58. Corrections found while writing this plan are listed in [Corrections to the design](#corrections-to-the-design). **The user confirms them in Task 0 Step 1, before any code.**

## Global Constraints

- **Two repos.**
  - This repo: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`.
  - haybale-visiongraph: `/Volumes/Ddrive/06_open_tracking_tool/haywire/haybale-visiongraph`, linked here as `barn/haybale-visiongraph`. This plan changes nothing there. Its tests run as a regression check only.
- **Branch.** Continue on `wire-types-5-1`, where 5.1 to 5.4 and D are landed but not merged. Never push; the user pushes.
- **Commit trailer.** Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Never commit:**
  - `docs/superpowers/plans/` (the user commits plans);
  - `internals/`, `.superpowers/`, `.claude/settings.json`;
  - the scratch file `tests/core/test_zz_graph_snapshot.py`.

  Always `git add` explicit paths, never `-A` or `.`.
- **Commit `barn/haybale-testing/` first.** This plan should not touch it. If a task does, commit that change before running the full suite. The teardown of `tests/studio/test_docs/test_generate.py` runs `git checkout -- barn/haybale-testing`.
- **Intended behaviour changes.** These are the only ones, and each has its test named in its task. Any other red behavioural test is a bug: stop and report it.
  1. **A new builtin wire, type and node.** `AnnotationWire`, `ANNOTATION` and `AnnotationNode` exist and register. The node appears in the add-node menu under its menu path (C10).
  2. **The canvas reveals hover-only pins.** A pin with `hw-pin-reveal` is hidden until its card is hovered or an edge drag is active. Today no pin carries the class, so no existing pin changes.
  3. **`edge-dragging`** is set on the canvas container while an edge drag is active (`edgeDrag.mode === 'active'`).
- **Out of scope:**
  - linking a note to an ordinary node ("pins anywhere", a follow-up);
  - Markdown in the text;
  - undoable pin removal (Q28);
  - undoable text edits (C8);
  - F13 to F15 and F17 to F24. The design closes F13 to F15 after 5.5 lands, in a round of their own.
- **Compare wire types by `.id`**, never with `is` on the class.
- **Docstrings and comments** follow `.claude/rules/python-docs.md`. The docstrings of `AnnotationNode`, `ANNOTATION` and `AnnotationSkin` are displayed: Markdown, single backticks, no reST.
- **"Ruff check"** means both `uv run ruff check <paths>` and `uv run ruff format --check <paths>`. Line length is 109.
- **Pre-commit gate:**
  1. Run `uv run pytest -m "not browser and not perf" -n 4 -q > /tmp/t.log 2>&1; echo "exit=$?"` with a timeout of at least 600000 ms.
  2. Then run `grep -E "^FAILED|^ERROR" /tmp/t.log` and `tail -1 /tmp/t.log`.
  3. Task 0 records the baseline.
- **Browser tier:** `uv run pytest -m browser -n 4 -q > /tmp/b.log 2>&1; echo "exit=$?"`. One failure is known to be intermittent, `test_edge_batch_cost` (F13). Rerun the tier once before calling it red.
- **visiongraph tests:** from this repo, `uv run pytest ../haybale-visiongraph/tests -q -p no:randomly`.
- **mypy set:** the CLAUDE.md command. The baseline is clean.
- **Canvas changes are checked in a browser**, not only in unit tests (`.insights/project_multi_canvas_dom_globals.md`).
- **Code lookup:** the repo is indexed by CodeGraph. `codegraph explore "<symbols>"` returns verbatim source plus callers.

---

## Corrections to the design

These were found while reading the code for this plan. **The user confirms them in Task 0 Step 1.** Record the answers as design decisions Q81 onward.

| # | Design said | The code says | This plan |
|---|---|---|---|
| C1 | "Builtin ships four wire types… `AnnotationWire` (`VISUAL`, with a style bag)". The other three live in `builtin/wires.py` | Every builtin type module imports `..wires`, so `wires.py` is loaded while `builtin.types` is still being initialised. `AnnotationStyle` needs `COLOR`, `FLOAT`, `CHOICES` and `STRING` from `builtin.types`, so declaring it in `wires.py` is an import cycle | `AnnotationStyle`, `AnnotationWire` and `ANNOTATION` live together in `builtin/types/annotation.py`. The docstring of `wires.py` names it as the fourth builtin wire |
| C2 | "A plain multi-line `text` setting… edited in the properties panel", plus "a setting" for hidden control pins | A node's card rebuilds only for the fields in `NodeProperties.REDRAW_FIELDS`. `RerouteNode` already binds its skin through a props subclass | Both fields go on the node's props subclass (`text`, `show_control_pins`, category `"annotation"`) and join `REDRAW_FIELDS`. A change rebuilds the card |
| C3 | "Double-clicking the card opens the existing `text_modal`… likely a skin-level `.on('dblclick')`" | `canvas.vue` has no `dblclick` handling and does not swallow it. Its mousedown capture handler does not `preventDefault` a click on a card body. The `SkinFactory` shares one skin instance per key | A `.on('dblclick')` on the card, in the skin, with no canvas change. The handler closes over the wrapper. Task 3 Step 1 checks it in a browser first; if the event does not arrive, stop and report |
| C4 | "While a drag is in progress the slots show on every candidate node, which needs a container class on the canvas" | The canvas container carries `dragging` (node move) and `box-selecting`. The edge drag state is `edgeDrag.mode`. `.connection-pin` is styled in `canvas.vue` with `!important` rules | Two generic pieces in `canvas.vue`: `edge-dragging` on the container, bound to `edgeDrag.mode === 'active'`, and a pin class `hw-pin-reveal` (`visibility: hidden !important`, visible under `.node-card:hover` or `.graph-canvas.edge-dragging`). The annotation skin only adds the class. Skin-injected CSS (`error_skin`'s `add_head_html`) is the alternative |
| C5 | "A drop on it goes through the pin index's distance hit and `nearestCompatiblePin`" | The index holds every `.connection-pin` (ghosts excepted) with its real rect, and a hidden pin keeps its rect. A direct hit (14 px ÷ zoom) ignores data type. A suggestion (200 canvas units) needs `sameType` | Holds as designed. The commit is the nearest compatible pin, so a drop near a side's grown pin links to that pin (a `VISUAL` inlet takes many links), and a drop near the slot grows a new one. Slots sit at the far end of each side's strip, apart from grown pins |
| C6 | (not stated) | Only `NodeSkin` renders the ghost pins `root_in`/`root_out`, and `BaseSkin` does not. An edge whose pin was removed (Q28) draws to the ghost | `AnnotationSkin` renders both ghosts at the centre of the inlet and outlet sides of the node's layout direction |
| C7 | (not stated) | `pin_kind = "annotation"` is not in `PinIconResolver.ICONS`, so a grown pin draws the `fallback` glyph (a circle) in both directions. Slots keep `ADD`'s declared `add_circle_outline`/`add_circle` | No new icon entries. Grown pins draw the fallback circle, and the arrow head shows direction. A skin may map `annotation_in`/`annotation_out` |
| C8 | (not stated) | Props edits through `render_settings` and direct `setattr` are not undoable | The modal writes `props.text` the same way; text edits are not undoable, like other props |
| C9 | "Each side carries a growing `ADD[ANNOTATION]` inlet and outlet" | `ADD[T]`'s port is `DECLARED` when added without an origin, and `is_user_removable()` is false for it | Slots are never removable; grown pins (`RESOLVED`) are, through the existing pin-menu row |
| C10 | (not stated) | Builtin nodes other than the error node are hidden from menus | `@node(label="Annotation", menu="annotation", search_tags=["note", "comment", "diagram", "arrow", "annotation"])`. Alternatives: (b) `menu="core/annotation"`, (c) the label "Note" |

## Names this plan introduces

| Name | Where | What |
|---|---|---|
| `AnnotationStyle` | `builtin/types/annotation.py` | The annotation wire's style bag: `color`, `width`, `dash`, `arrow_start`, `arrow_end` |
| `AnnotationWire` | same | `VISUAL`, `propagation = ()`, `pin_kind = "annotation"`, `style = AnnotationStyle` |
| `ANNOTATION` | same | `STRING` on `AnnotationWire`, `widget_key=None`, `StoreStrategy.NEVER` |
| `AnnotationNode` | `builtin/nodes/annotation.py` | The annotation node |
| `AnnotationNode.SIDES` | same | `("top", "right", "bottom", "left")` |
| `AnnotationNode.side_of(port_id)` | same | The card side a port id records, or `None` for `exec`/`done` |
| `AnnotationSkin` | `builtin/skins/annotation_skin.py` | The four-sided skin |
| `edge-dragging` | `canvas.vue` | Container class while an edge drag is active |
| `hw-pin-reveal` | `canvas.vue` | A pin hidden until hover or an edge drag |

## File structure

| File | Change |
|---|---|
| `packages/haywire-core/src/haywire/barn/builtin/types/annotation.py` | new: style bag, wire, type |
| `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py` | export `ANNOTATION` |
| `packages/haywire-core/src/haywire/barn/builtin/wires.py` | module docstring names the fourth wire |
| `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py` | new: `AnnotationNode` |
| `packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py` | new: `AnnotationSkin` |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` | `edge-dragging`, `hw-pin-reveal` |
| `packages/haywire-core/src/haywire/barn/builtin/__init__.py` | module docstring |
| tests: `tests/core/test_types/test_annotation_type.py`, `tests/core/test_node/test_annotation_node.py`, `tests/ui/skin/test_annotation_skin.py`, `tests/ui/harness/test_annotation_node.py` | new |
| tests: `tests/ui/harness/routes.py` | `/graph-annotation` route |
| docs: glossary, design doc status, builtin library docs (regenerated), baked docs | Task 5 |

---

### Task 0: Baseline (controller)

- [ ] **Step 1: Confirm the corrections.** Present C1 to C10 to the user, with lettered options where there is a choice. Record the answers in the design doc as a new section, "Decisions of 2026-10-04, 5.5 detail plan (Q81 to Q90)". Fold any changed answer into the tasks below before starting.
- [ ] **Step 2: Clean trees.** In both repos, `git status --short` shows nothing but untracked plan files and `.claude/settings.json`.
- [ ] **Step 3: Baselines.**
  1. Run the pre-commit gate, the browser tier, the visiongraph tests, the mypy set and `uv run ruff check . && uv run ruff format --check .`.
  2. Record the pass counts in `.superpowers/sdd/progress.md` under a new section, "5.5".
  3. Everything must be green. If anything is not, stop and start an error-fix session with the user (CLAUDE.md).
- [ ] **Step 4: Saved-graph snapshot.**
  1. Recreate `tests/core/test_zz_graph_snapshot.py` as in [5.1's Task 0 Step 4](2026-10-03-wire-types-5-1-sweep.md). Never commit it.
  2. Run `HW_GRAPH_SNAPSHOT=/tmp/graph_snapshot_before_5_5.json uv run pytest tests/core/test_zz_graph_snapshot.py -q -p no:randomly`.

  No saved graph may change.

---

### Task 1: `AnnotationWire`, `AnnotationStyle` and `ANNOTATION`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/types/annotation.py`
- Create: `tests/core/test_types/test_annotation_type.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/types/__init__.py`
- Modify: `packages/haywire-core/src/haywire/barn/builtin/wires.py` (docstring only)

- [ ] **Step 1: Write the failing tests**

```python
"""The annotation wire: drawn and saved, never executed, styled per edge."""

import pytest

from haywire.core.edge.style import STYLE_FIELDS
from haywire.core.settings import settings_fields
from haywire.core.types.wire import WireRole, wire_type_of

pytestmark = pytest.mark.unit


def test_the_annotation_wire_is_visual_and_styled():
    from haywire.barn.builtin.types.annotation import AnnotationStyle, AnnotationWire

    assert AnnotationWire.role is WireRole.VISUAL
    assert AnnotationWire.propagation == ()
    assert AnnotationWire.pin_kind == "annotation"
    assert AnnotationWire.style is AnnotationStyle
    assert AnnotationWire.id == "haywire-core:wire:AnnotationWire"


def test_the_style_declares_every_recognised_field():
    from haywire.barn.builtin.types.annotation import AnnotationStyle

    assert tuple(settings_fields(AnnotationStyle)) == STYLE_FIELDS


def test_annotation_travels_on_the_annotation_wire_and_has_no_widget():
    from haywire.barn.builtin.types import ADD, ANNOTATION
    from haywire.barn.builtin.types.annotation import AnnotationWire

    assert wire_type_of(ANNOTATION).id == AnnotationWire.id
    assert wire_type_of(ADD[ANNOTATION]).id == AnnotationWire.id
    assert ANNOTATION.class_identity.widget_key is None
```

(Check the identity attribute name for the widget key with `codegraph explore "DataTypeIdentity widget_key"`, and fix the assertion to match.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/core/test_types/test_annotation_type.py -q -p no:randomly`
Expected: `ModuleNotFoundError: haywire.barn.builtin.types.annotation`.

- [ ] **Step 3: Implement** `builtin/types/annotation.py`

```python
"""ANNOTATION — the drawn-only wire of annotation nodes, its look and its type.

The wire, its style bag and the type live together here, not in ``wires.py``:
the bag's fields need builtin types, which import ``wires.py`` themselves.
"""

from haywire.barn.builtin import widget_keys
from haywire.core.edge.arrow_heads import NO_HEAD
from haywire.core.edge.style import dash_choices
from haywire.core.settings import EdgeSettings, setting
from haywire.core.types import StoreStrategy, WireRole, WireType, type

from .choices import CHOICES
from .color import COLOR
from .specs import FLOAT, STRING


class AnnotationStyle(EdgeSettings):
    """The look of an annotation edge, set per edge in the edge menu and the inspector."""

    color = setting[COLOR]("#8e8e8e", label="Colour")
    width = setting[FLOAT](2.0, label="Width", min=0.5, max=12.0)
    dash = setting[CHOICES]("solid", label="Dash", widget_config={"options": dash_choices})
    arrow_start = setting[STRING](NO_HEAD, label="Start Head", widget={"key": widget_keys.ARROW_HEAD_WIDGET})
    arrow_end = setting[STRING]("arrow", label="End Head", widget={"key": widget_keys.ARROW_HEAD_WIDGET})


class AnnotationWire(WireType):
    """Links between annotation nodes: drawn and saved, never executed."""

    role = WireRole.VISUAL
    propagation = ()
    pin_kind = "annotation"
    style = AnnotationStyle


@type(
    wire_type=AnnotationWire,
    label="Annotation",
    description="A link between annotation nodes; carries no value",
    color="#8e8e8e",
    widget_key=None,
    store_strategy=StoreStrategy.NEVER,
)
class ANNOTATION(STRING):
    """A link between two annotation nodes.

    It is drawn and saved with the graph but never executed, so it carries no
    value. Its colour, dash, width and arrow heads are set per link.
    """
```

Add `from .annotation import ANNOTATION` and `"ANNOTATION"` to `types/__init__.py`. Extend the docstring of `wires.py`: "The fourth builtin wire, `AnnotationWire`, lives in `types/annotation.py` with its style bag."

- [ ] **Step 4: Run the tests and the type tests.** `uv run pytest tests/core/test_types/ -q -p no:randomly`. Expected: pass. If importing `haywire.core.settings` from a builtin type module creates a cycle (`ImportError` at collection), move the style bag's imports inside the module's lowest dependency order and report it. Do not import the bag lazily: `WireType.__init_subclass__` checks `style` at class definition.
- [ ] **Step 5: Ruff and mypy** on the touched files. **Commit:** `feat(builtin): the annotation wire, its style and the ANNOTATION type`.

---

### Task 2: `AnnotationNode`

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/nodes/annotation.py`
- Create: `tests/core/test_node/test_annotation_node.py`

**Interfaces:**
- `AnnotationNode.SIDES = ("top", "right", "bottom", "left")`.
- Port ids:
  - `f"{side}_{'in' if inlet else 'out'}_{index}"`;
  - control: `exec` (inlet) and `done` (outlet).
- `AnnotationNode.side_of(port_id) -> str | None`.
- The `props` subclass:
  - `skin = setting[CHOICES]("haywire-core:skin:AnnotationSkin", …)`;
  - `text = setting[STRING]("", category="annotation", …)`;
  - `show_control_pins = setting[BOOL](False, category="annotation", …)`;
  - `REDRAW_FIELDS = BaseNode.props.REDRAW_FIELDS + ("text", "show_control_pins")`.

- [ ] **Step 1: Write the failing tests.** The fixtures are those of `tests/core/test_types/test_add_type.py` (`graph_with_library_system`, `library_system`), marked `integration`. Tests:
  1. `test_a_new_node_has_eight_slots_and_a_control_pair`: ports `{side}_in_0`/`{side}_out_0` for each side, all `ADD[ANNOTATION]`, plus `exec`/`done` as `EXEC`.
  2. `test_linking_two_notes_grows_a_pin_on_each_side_used`: create A and B, then `create_edge_wrapper(A, "bottom_out_0", B, "top_in_0")`. Then:
     - `A.ports["bottom_out_0"].type_cls is ANNOTATION` and its origin is `RESOLVED`;
     - `A.ports["bottom_out_1"]` is a fresh `ADD[ANNOTATION]`;
     - the same holds on B's top inlet;
     - after `force_immediate_validation()` the edge is valid, `edge.style` is an `AnnotationStyle`, and `edge.propagation is None`;
     - `edge.carries_values` is false.
  3. `test_a_grown_pin_keeps_its_side`: `AnnotationNode.side_of("left_out_3") == "left"`; `side_of("exec") is None`.
  4. `test_indices_are_never_reused`: grow `top_in_0`, remove it with `remove_port`, then link again on `top_in_1`. The next slot is `top_in_2`.
  5. `test_removing_a_grown_pin_leaves_its_edge_on_the_ghost` (Q28): after `remove_port(B.node, "top_in_0")`, the edge is still in `graph.edges` and invalid ("Ports not found"), and the slot `top_in_1` is still there.
  6. `test_slots_are_not_removable_and_grown_pins_are` (C9).
  7. `test_an_unlinked_note_is_valid`: `graph.force_immediate_validation()`; the node's structural validation passes.
  8. `test_control_passes_through_with_its_payload`: build a control chain `TestBeginPlay.exec → note.exec`, `note.done → TestPrint.exec` (keys from `_RECONNECT_SOURCE_KEY`/`_RECONNECT_SINK_KEY` in `tests/ui/harness/routes.py`). Run one execution with the pattern of an existing control-chain test (find one with `codegraph explore "execute control chain test TestPrint"`). TestPrint runs. Separately, call the worker directly with `exec` set to `{"k": 1}`: `done` holds `{"k": 1}` and the worker returns `"done"`.
  9. `test_a_note_round_trips_with_its_pins_text_and_edge_style`:
     - set `props.text = "line 1\nline 2"`, link A to B, and set `edge.style.color = "#ff0000"`;
     - `to_dict()` → new graph → `from_dict()` (use the save/load helper the 5.4 tests use in `tests/core/test_edge/test_edge_style.py`);
     - the grown pins, the text, the edge and its colour are back.
  10. `test_the_skin_is_bound_by_key`: `node.props.skin == "haywire-core:skin:AnnotationSkin"`, and importing `haywire.barn.builtin.nodes.annotation` does not import `nicegui` (check `sys.modules` in a subprocess, as `tests/core` does for the reroute node; find it with `grep -rn "nicegui" tests/core | grep sys.modules`).
- [ ] **Step 2: Run them to verify they fail** (`ImportError`).
- [ ] **Step 3: Implement.** Model it on `add_port_test.py`'s decided-slot branch and `reroute.py`'s props subclass:

```python
@node(
    label="Annotation",
    description="A box of text for diagrams; links to other annotations with styled arrows",
    menu="annotation",
    search_tags=["note", "comment", "diagram", "arrow", "annotation"],
    node_type=NodeType.CONTROL,
)
class AnnotationNode(BaseNode):
    """A note on the canvas, with arrows to other notes.
    ...(displayed docstring: how to link, how pins grow per side, removing a pin
    from the pin menu, double-click to edit, Show Control Pins)...
    """

    SIDES = ("top", "right", "bottom", "left")

    class props(BaseNode.props):  # type: ignore[valid-type,misc]
        REDRAW_FIELDS = BaseNode.props.REDRAW_FIELDS + ("text", "show_control_pins")
        skin = setting[CHOICES]("haywire-core:skin:AnnotationSkin", label="Skin", category="appearance", order=10)
        text = setting[STRING]("", label="Text", category="annotation", order=1,
                               description="What the note says; double-click the card to edit it")
        show_control_pins = setting[BOOL](False, label="Show Control Pins", category="annotation", order=2,
                                          description="Draw the control pins while they are unlinked")

    def init(self) -> None:
        from haywire.barn.builtin.types import ADD, ANNOTATION, EXEC

        self.add(EXEC.as_inlet("exec"))
        self.add(EXEC.as_outlet("done"))
        for side in self.SIDES:
            for inlet in (True, False):
                self._add_slot(side, inlet, 0, ADD[ANNOTATION])

    def worker(self, context: ExecutionContext) -> str:
        self.out("done", self.value("exec"))
        return "done"

    def _grow(self, port, edge_wrapper) -> None:
        """Turn the connected slot into an annotation pin and open a new slot after it."""
        # on_connect fires again on every re-link (load, paste, revalidation).
        if not issubclass(port.type_cls, ADD):
            return
        side, inlet, index = self._parse(port.id)
        with self.rejig(include=[port.id]):
            self._add_slot(side, inlet, index, ANNOTATION, PortOrigin.RESOLVED)
        self._add_slot(side, inlet, self._next_index(side, inlet), ADD[ANNOTATION])
```

Plus `side_of` (classmethod), `_parse`, `_next_index` and `_add_slot` (with `on_connect="_grow"`), as in `add_port_test.py`. Labels are `f"{side.title()} {'In' if inlet else 'Out'} {index}"`. Check that `@node` accepts the props `REDRAW_FIELDS` override; `NodeWrapper._subscribe_props_redraw` reads `type(props).REDRAW_FIELDS`.

- [ ] **Step 4: Run the tests**, then `uv run pytest tests/core/test_node tests/core/test_types tests/core/test_graph -q -n 4`. Also run the registry and docs tests that count builtin nodes (`grep -rln "RerouteNode\|builtin.*nodes" tests | head` and run those): a test listing builtin nodes may need the new node. That is an expected edit; name it in the commit message.
- [ ] **Step 5: Ruff and mypy. Commit:** `feat(builtin): the annotation node, with pins grown per card side`.

---

### Task 3: `AnnotationSkin`, and the canvas's reveal class

**Files:**
- Create: `packages/haywire-core/src/haywire/barn/builtin/skins/annotation_skin.py`
- Create: `tests/ui/skin/test_annotation_skin.py`
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`
- Modify: `tests/ui/harness/routes.py`
- Create: `tests/ui/harness/test_annotation_node.py`

- [ ] **Step 1: Verify first, in a browser (C3, C5).** Write the harness route and the browser tests before the skin's final form.

  **Route `/graph-annotation`:**
  - two annotation nodes, A at (3600, 3700) and B at (3950, 3700);
  - A's `text` is `"hello"`;
  - mounted with `_mount_graph_canvas(..., testid="annotation")`;
  - the route keeps `graph` and the two node ids on `app.storage`, or answers them through a small JSON endpoint, as `/graph-dynamic` does (copy its pattern).

  **Browser tests** (`@pytest.mark.browser`, use `goto_ready`):
  1. `test_pins_sit_on_their_sides`: for each side and direction, the slot's `data-pin-dir-x/y` equals the side's outward vector (`top` (0,-1), `right` (1,0), `bottom` (0,1), `left` (-1,0)). Its rect centre lies on that card border within 2 px.
  2. `test_slots_are_hidden_until_hover`: a slot's computed `visibility` is `hidden`. After `page.hover` on A's card it is `visible` for A's slots and still `hidden` for B's.
  3. `test_slots_show_on_every_note_during_an_edge_drag`: hover A, then mousedown on A's `right_out_0`. The container has `edge-dragging`, and B's slots are `visible`. Press Escape: the class is gone.
  4. `test_a_drop_near_a_side_grows_the_slot_on_that_side`:
     - start a drag on A's `right_out_0`;
     - move the mouse to 6 px outside B's left border, at the height of `left_in_0`;
     - mousedown;
     - expect an edge `…[right_out_0]->…[left_in_0]` and a new `left_in_1` pin on B;
     - repeat from A's `bottom_out_0` to B's top side: expect `top_in_0`.
  5. `test_a_hidden_slot_is_indexed` (C5): start a drag from A without hovering B, then move to B's `left_in_0` position. The pin gets `connection-valid` or `connection-compatible` within 500 ms (wait on the class, not a fixed time).
  6. `test_double_click_opens_the_text_modal`:
     - dblclick A's card body;
     - a textarea holding `hello` appears;
     - fill it with `"a\nb"` and confirm;
     - A's card text reads `a` and `b` on two lines, and the server's `props.text == "a\nb"`.

  Run them against a first skin draft. **If test 6 shows that the dblclick never reaches Python** (`.on('dblclick')` swallowed by the canvas), stop and report: C3's fallback is a canvas event and needs a decision.

- [ ] **Step 2: Canvas** (`canvas.vue`, C4):
  - add `'edge-dragging': edgeDrag.mode === 'active'` to the container's `:class`;
  - next to the `.connection-pin` rules, add:

```css
/* A pin shown only while its card is hovered or an edge drag is in progress. Hidden with
   visibility so it keeps its box: the pin index and edge anchors read its rect. */
.graph-canvas .connection-pin.hw-pin-reveal { visibility: hidden !important; }
.graph-canvas .node-card:hover .connection-pin.hw-pin-reveal,
.graph-canvas.edge-dragging .connection-pin.hw-pin-reveal { visibility: visible !important; }
```

  Check that the hover reveal does not change layout. The rule changes only `visibility`, so no re-index is needed (pin index research: a class toggle does not dirty the index, and the rects do not move).

- [ ] **Step 3: The skin.** `AnnotationSkin(BaseSkin)`, `@skin(description=..., hidden=True)`. Geometry constants on the reroute pattern: `_PIN_GUTTER = 18`, `_PIN_PROTRUSION = 0`, `_CARD_PADDING = 12`. `render(main_card, wrapper)`:
  1. **Card:**
     - `main_card.classes("node-card drag-handle zoom-pan-lod0")`;
     - style `background: var(--hw-node-bg); border: var(--hw-node-border-width) solid var(--hw-node-border-color); border-radius: var(--hw-node-border-radius); color: var(--hw-node-text-color); position: relative; overflow: visible; padding: {_CARD_PADDING}px; min-width: 120px; min-height: 48px;`.
  2. **Text:**
     - `ui.label(text)` with style `white-space: pre-wrap; word-break: break-word;` and classes `text-sm zoom-pan-lod1`;
     - for empty text, a muted placeholder `Double-click to write` (`opacity: 0.5`).
  3. **Strips.** For each side in `AnnotationNode.SIDES`, an absolutely positioned flex strip on that edge:
     - `{side}: {_CARD_PADDING}px`;
     - spanning the cross axis (`top: 0; bottom: 0` for left and right, `left: 0; right: 0` for top and bottom);
     - `justify-content: space-evenly`, aligned to the edge (`align-items: flex-start` for left, `flex-end` for right; along the row for top and bottom);
     - `overflow: visible; pointer-events: none`, while pins keep `pointer-events: all` from the canvas rule.

     Contents, in this order:
     1. the control pin whose layout side this is, if it is drawn;
     2. the grown pins of the side, by index;
     3. the side's two slots, inlet first, each with `hw-pin-reveal`.
  4. **Per-pin layout** (the one-source rule, `.insights/project_layout_direction_pin_contract.md`):

     ```python
     _LAYOUT = {
         ("left", True): LayoutDirection.LEFT_TO_RIGHT,  ("left", False): LayoutDirection.RIGHT_TO_LEFT,
         ("right", True): LayoutDirection.RIGHT_TO_LEFT, ("right", False): LayoutDirection.LEFT_TO_RIGHT,
         ("top", True): LayoutDirection.TOP_TO_BOTTOM,   ("top", False): LayoutDirection.BOTTOM_TO_TOP,
         ("bottom", True): LayoutDirection.BOTTOM_TO_TOP, ("bottom", False): LayoutDirection.TOP_TO_BOTTOM,
     }
     ```

     Call `render_pin(port, node_id, layout=_LAYOUT[(side, port.is_inlet())], pin_gutter=_PIN_GUTTER, card_padding=_CARD_PADDING, pin_protrusion=_PIN_PROTRUSION, pin_icons=self.pin_icons)`, then `add_pin_tooltip`. Add `hw-pin-reveal` to the returned element for slots (`issubclass(port.type_cls, ADD)`).
  5. **Control pins** use the node's own layout (`resolve_layout_direction(wrapper)`): `exec` on its `inlet_side`, `done` on its `outlet_side`. Draw each when `props.show_control_pins`, or when the port has an edge (`port.get_valid_edges()` or the linked-state accessor `NodeSkin` uses for its `hw-detail-pins_all` decision; reuse that call).
  6. **Ghosts (C6):** `render_ghost_pin(node_id, layout=layout, is_inlet=..., offset=_CARD_PADDING + GHOST_PIN_SIZE // 2 + _PIN_PROTRUSION)` for both, placed in the strips of the layout's inlet and outlet sides.
  7. **Double-click (C3):** `main_card.on("dblclick", lambda _e: self._edit_text(wrapper))`, where `_edit_text` opens `text_modal(title="Annotation", value=props.text, placeholder="Write a note…", width="560px", on_confirm=lambda v: setattr(wrapper.node.props, "text", v))`. Hold no per-node state on the skin.

  Unit tests in `tests/ui/skin/test_annotation_skin.py`:
  - the `_LAYOUT` table: each entry's `side_for` equals its side, for inlets and outlets;
  - render one node with the NiceGUI `user` fixture, as `tests/ui/skin/` tests do. Check that every slot carries `hw-pin-reveal` and no grown pin does, and that `exec` is drawn only when linked or `show_control_pins` is set.

- [ ] **Step 4: Run** the skin tests, the new browser tests, `tests/ui/harness/test_reroute_skin.py` and `test_graph_connect.py`. Then run the whole browser tier.
- [ ] **Step 5: Ruff, mypy. Commit:** `feat(canvas): pins revealed on hover and during an edge drag` (the `canvas.vue` hunk alone), then `feat(builtin): the annotation skin, with pins on every side` (skin, route, tests).

---

### Task 4: Edge style on annotation edges, end to end

No new code is expected. This task proves that 5.4's machinery serves the builtin wire.

- [ ] **Step 1: Browser test** in `tests/ui/harness/test_annotation_node.py`, `test_an_annotation_edge_draws_its_style`:
  - link A to B in the route, or through the drag from Task 3;
  - the edge path draws with `stroke` `#8e8e8e`, an end head (the computed style of `marker-end` is not `none`), and no start head;
  - set `edge.style.arrow_start = "circle"` and `edge.style.color = "#ff0000"` server-side, then `mark_style_changed()`;
  - the path's colour and start head update. Wait on the computed value.
- [ ] **Step 2: Edge menu.** Open the edge menu on the annotation edge, as `tests/ui/harness/test_edge_style_menu.py` does. The five style rows are present and the propagation row is not.
- [ ] **Step 3: Commit:** `test(annotation): an annotation edge draws and edits its style`.

---

### Task 5: Glossary, docs and the design's status

- [ ] **Step 1: Glossary** (`docs/reference/glossary.md`):
  - add **Annotation node**: "A builtin `CONTROL` node that draws a box of text and links to other annotation nodes with **Styled edge**s on `AnnotationWire` (a `VISUAL` wire). Each card side grows pins where the user connects; the side is part of the port id. Its control pins pass control through and are drawn only when linked or when *Show Control Pins* is set.";
  - in **Wire type**, name the four builtin wires;
  - in **Ghost pin**, add that the annotation skin renders them too.
- [ ] **Step 2: Skin canon** (`docs/components/skins/skin-canon.md`): a short section, "A pin on any side". A skin passes `render_pin` the one `LayoutDirection` whose inlet or outlet side is the wanted side, as `AnnotationSkin._LAYOUT` does. A pin may carry `hw-pin-reveal` to stay hidden until hover or an edge drag. Never hide a pin with `display: none`.
- [ ] **Step 3: Builtin library docs.** `uv run haywire docs --all`, then check that `packages/haywire-core/src/haywire/barn/builtin/docs/` gained `haywire-core.node.AnnotationNode.md`, `haywire-core.type.ANNOTATION.md` and `haywire-core.skin.AnnotationSkin.md`, and that OVERVIEW and QUICKREF list them. Run `scripts/bake_docs.py` if the baked docs track these files (as in 5.1).
- [ ] **Step 4: The design doc (not committed).** In `2026-10-02-wire-types.md`:
  - status row 5.5 → "**Landed** on branch `wire-types-5-1` <date>, not merged", with this plan's link;
  - the 5.5 section notes C1 (module), C3 (dblclick on the skin) and C4 (generic canvas classes);
  - add the decisions table Q81 onward.
- [ ] **Step 5: `uv run mkdocs build 2>&1 | grep -iE "warning|error" | grep -v insights`** shows nothing new.
- [ ] **Step 6: Commit:** `docs: the annotation node, pins on any side`.

---

### Task 6: Verify the plan

- [ ] **Step 1: Full checks.** The pre-commit gate, the browser tier, the visiongraph tests, the mypy set and ruff (both commands). All green. Compare the counts with Task 0: only new tests are added.
- [ ] **Step 2: Saved graphs unchanged.** Rerun the snapshot to `/tmp/graph_snapshot_after_5_5.json` and `diff` it against the one from Task 0. Expected: no difference.
- [ ] **Step 3: Live studio** (with the `haywire-live-studio` skill):
  1. Add two Annotation nodes from the add-node menu. Type text in the properties panel; it shows on the card with its line breaks.
  2. Hover a card: its eight slots appear. Drag from the right outlet slot to near the other note's left side: a grown pin on each side and a grey arrow.
  3. Link from bottom to top, and from left to right on a third note. Pins spread along each side.
  4. Double-click a card: the modal opens. Edit and confirm: the card updates and the tab is marked unsaved.
  5. Edit the arrow's colour, dash and heads in the edge menu.
  6. Remove a grown pin from the pin menu: its arrow draws to the ghost, invalid.
  7. Toggle *Show Control Pins*: `exec`/`done` appear. Link `exec` from a Begin Play chain and run: execution passes through.
  8. Save, close, reopen: everything is kept.
  9. Run `.scratch/edgecheck.js` in the browser console: no edge is off its pin.
- [ ] **Step 4: Report** to the user: commits, counts, findings. Remind them that F13 to F15 are due now that 5.5 has landed.

---

## Self-review (done while writing)

- **Design coverage:**
  - `AnnotationWire`, `ANNOTATION` and the style bag with the five fields (Q48, Q58): Task 1.
  - `ADD[ANNOTATION]` slots per side, the decided-slot template, the side in the id, indices never reused: Task 2.
  - `render_pin` unchanged, with a per-pin layout: Task 3, Step 3.4.
  - Hover by `visibility`, and the container class during a drag: Task 3, Step 2.
  - The `sameType` suggestion unchanged: C5, Task 3, Step 1.5.
  - Content as `text`, the properties panel, the double-click to `text_modal`, colour from `color_override` (`var(--hw-node-bg)`), and sizing from node sizing: Tasks 2 and 3.
  - A `CONTROL` node with pass-through: Task 2, Step 1.8.
  - Hidden control pins drawn when linked: Task 3, Step 3.5.
  - Q28, removal leaves edges on the ghost: Task 2, Step 1.5, and C6.
  - Verify-first items: the pin index finds a hidden slot (Task 3, Step 1.5); a drop on a hidden slot (Step 1.4); a drag onto a side picks the right slot (Step 1.4).
- **Placeholders:** three spots name the lookup that fixes a detail (the widget-key attribute, the control-chain execution helper, the linked-state accessor). The assertions are fixed.
