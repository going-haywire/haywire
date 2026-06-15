# Floating Selection Toolbar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent, Miro-style floating toolbar that appears above the current selection's on-screen bounding box and offers curated commands (Copy · Delete · ⋯), rendered with NiceGUI panels exactly like the existing right-click context menu.

**Architecture:** A new `ToolbarFocus` scope carries curated toolbar panels (independent of the existing `SelectionFocus` right-click panels). A new `SelectionToolbarProvider` — a sibling of `SessionContextMenuProvider`, sharing the same `BaseContextMenuProvider` panel-render machinery — draws those panels into a persistent, no-backdrop `Popup` positioned at the selection's screen bounds. **Orientation differs deliberately from every other panel host:** the right-click menus render into `Popup.content` (a vertical `ui.column`) as stacked full-width labelled rows; the toolbar renders into a nested `ui.row` as a single line of icon-only buttons (`hui.icon_action`). This horizontal-vs-vertical split is the defining visual difference between the two surfaces. The canvas Vue component computes that bounding box and emits a low-frequency `selectionBounds` event on selection-change and on pan/zoom/drag **end**, plus a `selectionBoundsHide` event on gesture **start** (the Miro "hide during gesture" rule), so there is no frame-rate Python traffic. The toolbar's ⋯ overflow reuses the existing `SelectionFocus` Popup via the existing `ContextMenuSelectedEvent`.

**Tech Stack:** Python 3.10+, NiceGUI / Quasar / Vue 3, the haywire panel system (`@panel`, `Focus`, `PanelRegistry`, `BaseContextMenuProvider`), the haywire graph event system (`@graph_event`, `BaseGraphEvent`), pytest, ruff, mypy.

---

## Background: how the pieces already fit (read before starting)

These are the load-bearing facts this plan relies on. Verify them by reading the cited files if anything below is unclear.

- **Two selection axes** (`docs/reference/glossary.md`): `EditState.selected_nodes` / `selected_edges` (the *Selection axis*, command target) vs `active_node` / `active_edge` (the *Active axis*, inspector subject). The toolbar reads the **Selection axis**.
- **Panel-driven context menus.** `BaseContextMenuProvider._open_menu(action, focus, pos, on_close)` queries `PanelRegistry.get_panels_for_action(action, focus)`, poll-filters via `visible_panels(...)`, and renders each through `render_panel(cls, ctx, layout, actions_host=self)` into a `Popup`. File: `packages/haywire-core/src/haywire/ui/panel/context_menu_base.py`.
- **Focus classes** declare a scope id + `available(ctx)` gate. File: `barn/haybale-graph-editor/haybale_graph_editor/focuses.py`. `SelectionFocus` (id `"selection"`) is available when any node/edge is selected.
- **Selection actions** are a `Protocol` (`SelectionContextActions`) implemented structurally on the provider; panels call `self.actions.copy_selection()` etc. The provider's `_emit(event)` forwards a graph event and closes the popup. Files: `.../handlers/context_menu_actions.py`, `.../handlers/context_menu.py`.
- **Existing selection panels** live in `barn/haybale-graph-editor/haybale_graph_editor/panels/context_menu/selection_actions.py` and are registered in `register_components()`.
- **Canvas ↔ Python is event-only.** `GraphCanvasVue` (`packages/haywire-core/src/haywire/ui/components/graph/canvas.py`) sends Vue→Python via `canvasEvent` (typed `BaseGraphEvent`) and Python→Vue via `emit_sync_event` → `handleSyncEvent`. There is **no slot** to mount NiceGUI buttons inside the canvas — that is why the toolbar is a Python-owned `Popup` positioned from a bounds event, not Vue-rendered content.
- **The canvas already tracks gesture state:** `dragState.isDragging` (node drag, `canvas.vue:1028/1191`) and `zoomState.isDragging` (pan/zoom, fed by the `zoom-pan-state` document event, `canvas.vue:351-359`). Selection lives in `selectionState.selectedNodes` / `selectedEdges`. `_emitSelectionChanged()` (`canvas.vue:1327`) is the single place selection changes are broadcast.
- **`Popup` can be repositioned without rebuild:** `popup.vue` exposes `setPosition(x, y)` (`popup.vue:196`), callable from Python via `popup.run_method("setPosition", x, y)`. Construct with `backdrop_click_close=False` for persistence.
- **Wiring point:** `GraphCanvasManager.__init__` (`.../graph_canvas_manager.py:47-98`) constructs `SessionContextMenuProvider` + `ContextMenuHandlers`, then `build_event_handler_map([...])` collects all `@handles_event`-decorated methods into the dispatch map. The toolbar handler must be added to that list.

### File structure (what each new/changed file owns)

| File | Responsibility |
|------|----------------|
| `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` (modify) | Declare `SelectionBoundsEvent`, `SelectionBoundsHideEvent` (Vue→Python) and `ToolbarActionEvent` (Vue→Python). |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (modify) | Compute the selection bounding box in screen space; emit bounds on selection-change + gesture-end; emit hide on gesture-start. |
| `barn/haybale-graph-editor/haybale_graph_editor/focuses.py` (modify) | Add `ToolbarFocus` (id `"toolbar"`). |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu_actions.py` (modify) | Add `ToolbarActions` Protocol (overflow trigger verb). |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py` (create) | `SelectionToolbarProvider` (persistent Popup over `ToolbarFocus`) + `SelectionToolbarHandlers` (`@handles_event` for the bounds/hide events). |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/toolbar/toolbar_actions.py` (create) | `CopyToolbarPanel`, `DeleteToolbarPanel`, `OverflowToolbarPanel` (the curated face), registered against `ToolbarFocus`. |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py` (modify) | Construct the toolbar provider + handlers; add to the handler-map list. |
| `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` (modify) | Register the new toolbar panels in `register_components()`. |
| `docs/reference/glossary.md` (modify) | Correct the **Floating toolbar** entry to reflect Python-owns-rendering-and-position. |
| `tests/...` (create) | Unit tests per task. |

---

## Task 1: Define the bounds + action graph events

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` (after `SelectionChangedEvent`, ~line 165)
- Test: `tests/ui/components/graph/test_toolbar_events.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/components/graph/test_toolbar_events.py
"""Round-trip tests for the floating-toolbar graph events."""

import haywire.core.graph.editor  # noqa: F401  (import-order guard, see CLAUDE.md)

from haywire.ui.components.graph.event_definitions import (
    GRAPH_EVENT_REGISTRY,
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
    ToolbarActionEvent,
)


def test_selection_bounds_event_registered_and_roundtrips():
    assert "selectionBounds" in GRAPH_EVENT_REGISTRY
    ev = SelectionBoundsEvent(left=10.0, top=20.0, right=110.0, bottom=70.0)
    data = ev.to_dict()
    assert data["event_type"] == "selectionBounds"
    back = SelectionBoundsEvent.from_dict(data)
    assert (back.left, back.top, back.right, back.bottom) == (10.0, 20.0, 110.0, 70.0)


def test_selection_bounds_hide_event_registered():
    assert "selectionBoundsHide" in GRAPH_EVENT_REGISTRY
    ev = SelectionBoundsHideEvent()
    assert ev.to_dict()["event_type"] == "selectionBoundsHide"


def test_toolbar_action_event_registered_and_roundtrips():
    assert "toolbarAction" in GRAPH_EVENT_REGISTRY
    ev = ToolbarActionEvent(actionId="copy")
    back = ToolbarActionEvent.from_dict(ev.to_dict())
    assert back.actionId == "copy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/components/graph/test_toolbar_events.py -v`
Expected: FAIL with `ImportError: cannot import name 'SelectionBoundsEvent'`.

- [ ] **Step 3: Add the event classes**

Insert immediately after `SelectionChangedEvent` (the class ending ~line 164) in `event_definitions.py`:

```python
@graph_event("selectionBounds", category="user", description="Selection screen bounding box (toolbar anchor)")
@dataclass
class SelectionBoundsEvent(BaseGraphEvent):
    # Screen-space rectangle of the current selection's bounding box, in CSS px
    # relative to the viewport. Emitted on selection change and on pan/zoom/drag
    # END (never at frame rate). Python anchors the floating toolbar to this.
    left: float
    top: float
    right: float
    bottom: float


@graph_event("selectionBoundsHide", category="user", description="Hide the floating toolbar (gesture in progress)")
@dataclass
class SelectionBoundsHideEvent(BaseGraphEvent):
    # Emitted on pan/zoom/drag START. Python hides the toolbar until the next
    # selectionBounds arrives at gesture end (Miro hide-during-gesture rule).
    pass


@graph_event("toolbarAction", category="user", description="Floating-toolbar button clicked")
@dataclass
class ToolbarActionEvent(BaseGraphEvent):
    # Currently unused by the curated face (panels call provider verbs directly),
    # reserved for any future Vue-side toolbar affordance. Kept for symmetry and
    # forward-compat; see plan note in Task 6.
    actionId: str
```

> Note: `@dataclass` with no fields needs the `pass` body; keep the `category="user"` so `_validate_handler_coverage` expects a handler (added in Task 5).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/components/graph/test_toolbar_events.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Regenerate the JS event mirror if one is generated**

The repo has `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`. Check whether it is hand-maintained or generated:

Run: `git log --oneline -1 -- packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`
Then: `grep -rn "graph_events.js" scripts/ packages/ 2>/dev/null | grep -i "gen\|write\|generate"`

If a generator script exists (e.g. `scripts/generate_graph_events.py`), run it: `uv run python scripts/<that_script>.py`.
If NOT generated (hand-maintained), add these three entries to `generated/graph_events.js` mirroring the existing `SELECTION_CHANGED` pattern (an event-type constant in the `GraphEvents` object, a `create*` factory, and a `validate*` stub). Match the surrounding style exactly.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py \
        packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js \
        tests/ui/components/graph/test_toolbar_events.py
git commit -m "feat(graph-events): add selectionBounds, selectionBoundsHide, toolbarAction events"
```

---

## Task 2: Compute and emit the selection bounding box from the canvas

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`

This task has no Python unit test (it is Vue logic with no headless harness in this repo). Verify by reading the diff and by the manual smoke test in Task 7. Keep the changes minimal and mirror existing patterns (`_getSelectionRectangle`, `_emitSelectionChanged`).

- [ ] **Step 1: Add a bounding-box helper near `_getSelectionRectangle` (~line 1443)**

Add this method (it computes the *selection's* box, distinct from the rubber-band box `_getSelectionRectangle` returns):

```javascript
        /** Screen-space bounding box (CSS px, viewport-relative) of all
         *  currently selected nodes. Returns null if nothing selected or no
         *  rects resolvable. Edges are not measured directly — a selection that
         *  is edges-only falls back to null (toolbar hides). */
        _computeSelectionScreenBounds() {
            const ids = Array.from(this.selectionState.selectedNodes);
            if (ids.length === 0) return null;

            let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
            for (const nodeId of ids) {
                const el = this.$refs.nodeContainer
                    ? this.$refs.nodeContainer.querySelector(`[data-node-id="${nodeId}"]`)
                    : null;
                if (!el) continue;
                const r = el.getBoundingClientRect();
                if (r.left < left) left = r.left;
                if (r.top < top) top = r.top;
                if (r.right > right) right = r.right;
                if (r.bottom > bottom) bottom = r.bottom;
            }
            if (left === Infinity) return null;
            return { left, top, right, bottom };
        },
```

> Confirm the per-node DOM selector before relying on it: run
> `grep -n "data-node-id\|data-nodeid\|node-id" packages/haywire-core/src/haywire/ui/components/graph/canvas.vue barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/ui_node.py`
> and use whatever attribute the node wrapper actually renders. If nodes carry the id differently (e.g. element id `node-<id>`), adjust the selector to match. This is the only fragile line; get it right.

- [ ] **Step 2: Add an emit helper next to `_emitSelectionChanged` (~line 1337)**

```javascript
        _emitSelectionBounds() {
            const b = this._computeSelectionScreenBounds();
            if (!b) {
                // Nothing measurable → tell Python to hide.
                this.emitCanvasEvent(EventCreators.createSelectionBoundsHide());
                return;
            }
            this.emitCanvasEvent(EventCreators.createSelectionBounds(
                b.left, b.top, b.right, b.bottom
            ));
        },

        _emitSelectionBoundsHide() {
            this.emitCanvasEvent(EventCreators.createSelectionBoundsHide());
        },
```

> If `graph_events.js` is hand-maintained, ensure `createSelectionBounds(left, top, right, bottom)` and `createSelectionBoundsHide()` exist (added in Task 1 Step 5). If a generator produced them, confirm the argument order matches the dataclass field order: `left, top, right, bottom`.

- [ ] **Step 3: Emit bounds on every selection change**

In `_emitSelectionChanged()` (~line 1337), add a bounds emit at the end of the method body, right after the existing `this.emitCanvasEvent(EventCreators.createSelectionChanged(...))` call:

```javascript
            // Anchor (or hide) the floating toolbar to the new selection.
            this._emitSelectionBounds();
```

- [ ] **Step 4: Emit hide on gesture start, bounds on gesture end**

There are three gestures. Wire each:

1. **Node drag start/end.** Find where `this.dragState.isDragging = true` is set (~line 1028) and add right after it:
   ```javascript
           this._emitSelectionBoundsHide();
   ```
   Find where `this.dragState.isDragging = false` is set (~line 1191) and add right after it:
   ```javascript
           this._emitSelectionBounds();
   ```

2. **Pan/zoom.** These are driven by the `zoom-pan-state` document event handled in `handleZoomPanUpdate` (~line 351). The payload carries `isDragging`. Track edges: add a data field `_toolbarHiddenForGesture: false` to the component `data()` return (near `zoomState`), then inside `handleZoomPanUpdate`, after `this.zoomState = { zoom, panX, panY, isDragging };`:
   ```javascript
           if (isDragging && !this._toolbarHiddenForGesture) {
               this._toolbarHiddenForGesture = true;
               this._emitSelectionBoundsHide();
           } else if (!isDragging && this._toolbarHiddenForGesture) {
               this._toolbarHiddenForGesture = false;
               this._emitSelectionBounds();
           }
   ```
   > Wheel-zoom may not toggle `isDragging`. If `grep -n "isDragging" packages/haywire-core/src/haywire/ui/components/zoom/*.vue` shows wheel zoom does NOT set `isDragging`, also call `this._emitSelectionBounds()` (debounced) at the end of the wheel handler in the zoom container, OR accept that wheel-zoom repositions only on the next selection change. Prefer the simplest: re-emit bounds after wheel settles using a 120ms debounce timer. Document whichever you chose in a code comment.

- [ ] **Step 5: Manual sanity read**

Re-read the four edited regions in `canvas.vue` and confirm: (a) `_emitSelectionBounds` is called after `createSelectionChanged`, (b) hide fires on all gesture starts, (c) bounds fires on all gesture ends, (d) the node selector in `_computeSelectionScreenBounds` matches the real DOM attribute.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue
git commit -m "feat(canvas): emit selection screen bounds on change + gesture-end, hide on gesture-start"
```

---

## Task 3: Add the ToolbarFocus scope and ToolbarActions protocol

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/focuses.py` (after `SelectionFocus`, ~line 71)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu_actions.py` (after `SelectionContextActions`, ~line 59)
- Test: `tests/graph_editor/test_toolbar_focus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/graph_editor/test_toolbar_focus.py
import haywire.core.graph.editor  # noqa: F401

from haybale_graph_editor.focuses import ToolbarFocus, SelectionFocus
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import ToolbarActions


def test_toolbar_focus_has_distinct_id():
    assert ToolbarFocus.id == "toolbar"
    assert ToolbarFocus.id != SelectionFocus.id


def test_toolbar_focus_available_mirrors_selection(make_ctx_with_selection):
    # available() is True iff there is a non-empty selection (any node/edge).
    ctx_empty = make_ctx_with_selection(nodes=set(), edges=set())
    ctx_one = make_ctx_with_selection(nodes={"n1"}, edges=set())
    assert ToolbarFocus.available(ctx_empty) is False
    assert ToolbarFocus.available(ctx_one) is True


def test_toolbar_actions_is_runtime_checkable_protocol():
    # ToolbarActions declares the overflow verb.
    assert hasattr(ToolbarActions, "open_overflow_menu")
```

> The `make_ctx_with_selection` fixture: check `tests/graph_editor/conftest.py` for an existing builder that returns a `SessionContext` with an `EditState` whose `selected_nodes`/`selected_edges` are set. If none exists, add this fixture to that conftest:
> ```python
> import pytest
> from haywire.core.session.context import SessionContext
> from haybale_graph_editor.state.edit_state import EditState
>
> @pytest.fixture
> def make_ctx_with_selection():
>     def _make(nodes, edges):
>         ctx = SessionContext()
>         es = ctx.data[EditState]
>         es.selected_nodes = set(nodes)
>         es.selected_edges = set(edges)
>         return ctx
>     return _make
> ```
> Adjust `SessionContext()` construction to match how existing tests build one (grep `tests/graph_editor` for `SessionContext(` to copy the real call).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_toolbar_focus.py -v`
Expected: FAIL with `ImportError: cannot import name 'ToolbarFocus'`.

- [ ] **Step 3: Add `ToolbarFocus` to `focuses.py`**

Insert after the `SelectionFocus` class (~line 71):

```python
class ToolbarFocus(Focus):
    id = "toolbar"
    label = "Toolbar"
    icon = "dashboard"
    order = 91  # just after SelectionFocus (90)

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes) or bool(edit.selected_edges)
```

- [ ] **Step 4: Add `ToolbarActions` to `context_menu_actions.py`**

Insert after `SelectionContextActions` (~line 59):

```python
@runtime_checkable
class ToolbarActions(Protocol):
    """Verbs the floating toolbar's curated face invokes.

    The toolbar reuses SelectionContextActions for Copy/Delete (the provider
    implements both Protocols structurally). This Protocol adds only the
    toolbar-specific verb: opening the ⋯ overflow, which reaches back into the
    SelectionFocus right-click menu.
    """

    def open_overflow_menu(self) -> None: ...
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_toolbar_focus.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/focuses.py \
        barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu_actions.py \
        tests/graph_editor/test_toolbar_focus.py tests/graph_editor/conftest.py
git commit -m "feat(graph-editor): add ToolbarFocus scope and ToolbarActions protocol"
```

---

## Task 4: Build the curated toolbar panels

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/panels/toolbar/__init__.py`
- Create: `barn/haybale-graph-editor/haybale_graph_editor/panels/toolbar/toolbar_actions.py`
- Test: `tests/graph_editor/test_toolbar_panels.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/graph_editor/test_toolbar_panels.py
import haywire.core.graph.editor  # noqa: F401

from haybale_graph_editor.focuses import ToolbarFocus
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
    SelectionContextActions,
    ToolbarActions,
)
from haybale_graph_editor.panels.toolbar.toolbar_actions import (
    CopyToolbarPanel,
    DeleteToolbarPanel,
    OverflowToolbarPanel,
)


def test_panels_target_toolbar_focus():
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, OverflowToolbarPanel):
        assert cls.focus is ToolbarFocus


def test_copy_and_delete_target_selection_actions():
    assert CopyToolbarPanel.actions is SelectionContextActions
    assert DeleteToolbarPanel.actions is SelectionContextActions


def test_overflow_targets_toolbar_actions():
    assert OverflowToolbarPanel.actions is ToolbarActions


def test_poll_true_only_with_selection(make_ctx_with_selection):
    empty = make_ctx_with_selection(nodes=set(), edges=set())
    one = make_ctx_with_selection(nodes={"n1"}, edges=set())
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, OverflowToolbarPanel):
        assert cls.poll(empty) is False
        assert cls.poll(one) is True
```

> Confirm the `@panel` decorator stores `focus` and `actions` as class attributes (the test reads `cls.focus` / `cls.actions`). Verify with `grep -n "focus\|actions" packages/haywire-core/src/haywire/ui/panel/decorator.py`. If the decorator stores them under different attribute names (e.g. `_focus`), update the assertions to match the real names.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_toolbar_panels.py -v`
Expected: FAIL with `ModuleNotFoundError: ...panels.toolbar.toolbar_actions`.

- [ ] **Step 3: Create the package init**

```python
# barn/haybale-graph-editor/haybale_graph_editor/panels/toolbar/__init__.py
"""Floating-toolbar panels (ToolbarFocus)."""
```

- [ ] **Step 4: Create the panels**

```python
# barn/haybale-graph-editor/haybale_graph_editor/panels/toolbar/toolbar_actions.py
"""Curated floating-toolbar panels.

Face: Copy · Delete · ⋯ (overflow). Copy/Delete reuse SelectionContextActions
(the toolbar provider implements that Protocol structurally, like the right-click
provider). The ⋯ overflow uses ToolbarActions.open_overflow_menu, which re-opens
the SelectionFocus right-click menu so the batch ops (redraw/revalidate/reset)
stay in one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ...focuses import ToolbarFocus
from ...state.edit_state import EditState
from ...editors.graph_canvas.handlers.context_menu_actions import (
    SelectionContextActions,
    ToolbarActions,
)

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _has_selection(ctx: "SessionContext") -> bool:
    edit = ctx.data[EditState]
    return bool(edit.selected_nodes) or bool(edit.selected_edges)


@panel(
    actions=SelectionContextActions,
    focus=ToolbarFocus,
    label="Copy",
    icon=hui.icon.copy,
    order=10,
)
class CopyToolbarPanel(BasePanel):
    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_selection(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        # Icon-only, theme-aware, flat round dense — the house primitive for an
        # inline icon action (design-guide §8.8). The toolbar is HORIZONTAL: the
        # provider renders these panels into a `ui.row`, so each panel draws a
        # single icon button, NOT a full-width labelled row like the vertical
        # right-click panels do.
        with layout:
            hui.icon_action(hui.icon.copy, tooltip="Copy", on_click=self.actions.copy_selection)


@panel(
    actions=SelectionContextActions,
    focus=ToolbarFocus,
    label="Delete",
    icon=hui.icon.delete,
    order=20,
)
class DeleteToolbarPanel(BasePanel):
    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_selection(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action(hui.icon.delete, tooltip="Delete", on_click=self.actions.delete_selection)


@panel(
    actions=ToolbarActions,
    focus=ToolbarFocus,
    label="More",
    icon="more_horiz",
    order=900,  # always last (the ⋯ on the right)
)
class OverflowToolbarPanel(BasePanel):
    actions: ToolbarActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_selection(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action("more_horiz", tooltip="More actions", on_click=self.actions.open_overflow_menu)
```

> Two things to verify against the codebase, fixing inline if they differ:
> 1. `hui.icon_action(icon, *, tooltip, on_click, size="xs")` is the house icon-only button (design-guide §8.8, defined in `haywire/ui/elements/elements.py:390`). It is the correct primitive for a horizontal toolbar — do NOT use `hui.button(...).props(...)` (raw) and do NOT use `hui.row`/`hui.column` (the `hui` vocabulary does not export layout containers; the provider owns the `ui.row`). Confirm `icon_action` exists and its signature with `grep -n "def icon_action" packages/haywire-core/src/haywire/ui/elements/elements.py`.
> 2. `hui.icon.copy` / `hui.icon.delete` exist (used in `selection_actions.py`). `more_horiz` is a Material icon name string; if `hui.icon` has a constant for it (`grep -n "more_horiz\|more_horizontal\|overflow" packages/haywire-core/src/haywire/ui/elements/icons.py`), prefer that constant.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_toolbar_panels.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/toolbar/ \
        tests/graph_editor/test_toolbar_panels.py
git commit -m "feat(graph-editor): add curated toolbar panels (Copy/Delete/Overflow)"
```

---

## Task 5: Build the toolbar provider and event handler

**Files:**
- Create: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py`
- Test: `tests/graph_editor/test_selection_toolbar_provider.py`

This is the heart of the feature: a persistent-Popup provider plus the handler that turns bounds/hide events into show/reposition/hide calls.

- [ ] **Step 1: Write the failing test**

```python
# tests/graph_editor/test_selection_toolbar_provider.py
import haywire.core.graph.editor  # noqa: F401

from unittest.mock import MagicMock

from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
)
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
    SelectionToolbarProvider,
    SelectionToolbarHandlers,
)


def _provider(monkeypatch):
    ctx = MagicMock()
    session = MagicMock()
    registry = MagicMock()
    # No panels visible by default → show() should be a no-op.
    registry.get_panels_for_action.return_value = []
    prov = SelectionToolbarProvider(
        context=ctx, session=session, panel_registry=registry,
        on_emit_event=MagicMock(), on_emit_sync_event=MagicMock(),
    )
    return prov, registry


def test_show_no_visible_panels_opens_nothing(monkeypatch):
    prov, registry = _provider(monkeypatch)
    # Force visible_panels → [] regardless of registry contents.
    monkeypatch.setattr(
        "haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar.visible_panels",
        lambda classes, ctx: [],
    )
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._toolbar_popup is None


def test_handler_routes_bounds_to_show(monkeypatch):
    prov, _ = _provider(monkeypatch)
    prov.show_at = MagicMock()
    prov.hide = MagicMock()
    handlers = SelectionToolbarHandlers(provider=prov)

    handlers.process_selection_bounds(
        SelectionBoundsEvent(left=10.0, top=20.0, right=110.0, bottom=70.0)
    )
    prov.show_at.assert_called_once_with((10.0, 20.0, 110.0, 70.0))


def test_handler_routes_hide(monkeypatch):
    prov, _ = _provider(monkeypatch)
    prov.show_at = MagicMock()
    prov.hide = MagicMock()
    handlers = SelectionToolbarHandlers(provider=prov)

    handlers.process_selection_bounds_hide(SelectionBoundsHideEvent())
    prov.hide.assert_called_once()


def test_open_overflow_emits_selection_context(monkeypatch):
    # ⋯ overflow re-opens the SelectionFocus right-click menu via the existing
    # contextMenuSelected event path. We assert it emits ContextMenuSelectedEvent.
    prov, _ = _provider(monkeypatch)
    from haywire.ui.components.graph.event_definitions import ContextMenuSelectedEvent
    prov._open_ctx = None
    prov._last_bounds = (10.0, 20.0, 110.0, 70.0)
    emitted = []
    prov._on_emit_event = lambda ev: emitted.append(ev)
    prov.open_overflow_menu()
    assert any(isinstance(ev, ContextMenuSelectedEvent) for ev in emitted)
```

> The overflow test asserts the provider re-emits `ContextMenuSelectedEvent` so the *existing* `ContextMenuHandlers` → `SessionContextMenuProvider.on_selection_context` path renders the SelectionFocus menu. Confirm `ContextMenuSelectedEvent`'s exact field names with `grep -n "class ContextMenuSelectedEvent" -A8 packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` and match them in Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_selection_toolbar_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: ...handlers.selection_toolbar`.

- [ ] **Step 3: Implement the provider + handler**

```python
# barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py
"""SelectionToolbarProvider and SelectionToolbarHandlers.

The floating toolbar is the persistent, selection-anchored sibling of the
right-click context menu. It reuses BaseContextMenuProvider's panel-render
machinery but draws ToolbarFocus panels into a PERSISTENT Popup (no backdrop
close) that is shown / repositioned / hidden in response to the canvas's
low-frequency selectionBounds / selectionBoundsHide events.

Rendering is NiceGUI panels (same as the context menu). The canvas only tells
us WHERE (screen bounds) and WHEN to hide (gesture in progress).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Tuple

from haywire.core.session.context import SessionContext
from haywire.core.session.session import Session
from haywire.ui.panel.registry import PanelRegistry
from nicegui import ui

from haywire.ui.panel.context_menu_base import BaseContextMenuProvider
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.host_rendering import render_panel, visible_panels
from haywire.ui.components.popup import Popup

from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
    ContextMenuSelectedEvent,
)
from ..event_handlers import handles_event
from ....state.edit_state import EditState

logger = logging.getLogger(__name__)

# Vertical gap (px) between the selection's top edge and the toolbar's bottom.
_TOOLBAR_GAP = 12.0
# Approximate toolbar height (px) used to place it ABOVE the selection.
_TOOLBAR_HEIGHT = 44.0


class SelectionToolbarProvider(BaseContextMenuProvider):
    """Persistent panel-driven floating toolbar over ToolbarFocus.

    Implements SelectionContextActions (copy/delete — reused by Copy/Delete
    panels) and ToolbarActions (open_overflow_menu) structurally.
    """

    def __init__(
        self,
        context: SessionContext,
        session: Session,
        panel_registry: PanelRegistry,
        on_emit_event: Optional[Callable] = None,
        on_emit_sync_event: Optional[Callable] = None,
    ):
        super().__init__(context, session, panel_registry)
        self._on_emit_event = on_emit_event
        self._on_emit_sync_event = on_emit_sync_event
        self._toolbar_popup: Optional[Popup] = None
        self._last_bounds: Optional[Tuple[float, float, float, float]] = None

    # -- lifecycle ----------------------------------------------------------

    def show_at(self, bounds: Tuple[float, float, float, float]) -> None:
        """Show or reposition the toolbar above the given screen bounds rect."""
        from haybale_graph_editor.focuses import ToolbarFocus
        from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
            ToolbarActions,
        )

        self._last_bounds = bounds
        left, top, right, _bottom = bounds
        center_x = (left + right) / 2.0
        pos_x = center_x
        pos_y = max(0.0, top - _TOOLBAR_GAP - _TOOLBAR_HEIGHT)

        # Poll ToolbarFocus panels (actions axis: ToolbarActions covers overflow;
        # SelectionContextActions panels also match because they declare
        # focus=ToolbarFocus). Query both action axes the toolbar panels use.
        panel_classes = self._collect_toolbar_panels()
        visible = visible_panels(panel_classes, self._context)
        if not visible:
            self.hide()
            return

        if self._toolbar_popup is None:
            self._toolbar_popup = Popup(
                position_x=pos_x,
                position_y=pos_y,
                backdrop_click_close=False,
                escape_close=False,
                backdrop_color="transparent",
                draggable=False,
            )
            self._toolbar_popup.open()
        else:
            self._toolbar_popup.run_method("setPosition", pos_x, pos_y)

        # Redraw content HORIZONTALLY. Every other panel host (right-click
        # menus) renders into Popup.content, which is a `ui.column` (vertical) —
        # the toolbar is the ONE host that lays its panels out in a row. Do NOT
        # try to flip the column to flex-row via .classes() (it keeps the
        # column's flex-col + w-full and renders wrong); instead render the
        # panels into a child `ui.row` nested in the column.
        content = self._toolbar_popup.content
        content.clear()
        with content:
            row = ui.row().classes("items-center gap-1 flex-nowrap")
        layout = PanelLayout(row)
        for cls in visible:
            render_panel(cls, self._context, layout, actions_host=self)

    def hide(self) -> None:
        if self._toolbar_popup is not None:
            self._toolbar_popup.close()
            self._toolbar_popup.delete()
            self._toolbar_popup = None

    def _collect_toolbar_panels(self) -> list:
        """All panels whose focus is ToolbarFocus, across the action axes the
        toolbar uses (SelectionContextActions for Copy/Delete, ToolbarActions
        for overflow). De-dup while preserving order."""
        from haybale_graph_editor.focuses import ToolbarFocus
        from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
            SelectionContextActions,
            ToolbarActions,
        )

        seen: set = set()
        out: list = []
        for action in (SelectionContextActions, ToolbarActions):
            for cls in self._panel_registry.get_panels_for_action(action, ToolbarFocus):
                if cls not in seen:
                    seen.add(cls)
                    out.append(cls)
        # Stable order by the panel's declared order attribute.
        out.sort(key=lambda c: getattr(c, "order", 0))
        return out

    # -- SelectionContextActions (reused by Copy/Delete panels) -------------

    def _emit(self, event) -> None:
        if self._on_emit_event:
            self._on_emit_event(event)

    def copy_selection(self) -> None:
        from haywire.ui.components.graph.event_definitions import UserCopySelectedEvent

        edit = self._context.data[EditState]
        self._emit(
            UserCopySelectedEvent(
                selectedNodes=list(edit.selected_nodes),
                selectedEdges=list(edit.selected_edges),
            )
        )

    def delete_selection(self) -> None:
        from haywire.ui.components.graph.event_definitions import UserRemoveEvent

        edit = self._context.data[EditState]
        self._emit(
            UserRemoveEvent(
                nodes=list(edit.selected_nodes),
                edges=list(edit.selected_edges),
            )
        )

    # -- ToolbarActions -----------------------------------------------------

    def open_overflow_menu(self) -> None:
        """Re-open the SelectionFocus right-click menu near the ⋯ button.

        Emits ContextMenuSelectedEvent so the existing ContextMenuHandlers →
        SessionContextMenuProvider.on_selection_context path renders the full
        SelectionFocus menu (Copy/Delete + Redraw/Revalidate/Reset). This keeps
        the batch ops in exactly one place.
        """
        edit = self._context.data[EditState]
        if self._last_bounds is None:
            return
        left, top, right, _bottom = self._last_bounds
        screen_x = right  # anchor near the ⋯ (right edge of the toolbar)
        screen_y = max(0.0, top - _TOOLBAR_GAP)
        self._emit(
            ContextMenuSelectedEvent(
                screenX=screen_x,
                screenY=screen_y,
                selectedNodes=list(edit.selected_nodes),
                selectedEdges=list(edit.selected_edges),
            )
        )


class SelectionToolbarHandlers:
    """Route selectionBounds / selectionBoundsHide events to the provider."""

    def __init__(self, provider: SelectionToolbarProvider):
        self.provider = provider

    @handles_event(SelectionBoundsEvent)
    def process_selection_bounds(self, event: SelectionBoundsEvent) -> None:
        self.provider.show_at((event.left, event.top, event.right, event.bottom))

    @handles_event(SelectionBoundsHideEvent)
    def process_selection_bounds_hide(self, event: SelectionBoundsHideEvent) -> None:
        self.provider.hide()
```

> Verify three things against the codebase before running, fixing inline:
> 1. `ContextMenuSelectedEvent` field names (`screenX/screenY/selectedNodes/selectedEdges`) — confirm with the grep in Step 1. The right-click menu emits this event from Vue; here Python synthesizes it. Confirm `ContextMenuHandlers.process_context_menu` accepts a Python-emitted instance (it dispatches by type, so it will — but the event must be routed through `on_emit_event` → `_handle_canvas_event`, which Task 6 wires).
> 2. `Popup.content` is a `ui.column`; `.clear()` and `.classes(...)` work on it (they do — it's a NiceGUI element).
> 3. `PanelLayout(content)` — confirm `PanelLayout` takes the content element positionally (it does in `BaseContextMenuProvider._open_menu`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_selection_toolbar_provider.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py \
        tests/graph_editor/test_selection_toolbar_provider.py
git commit -m "feat(graph-editor): SelectionToolbarProvider + bounds/hide handlers"
```

---

## Task 6: Wire the toolbar into GraphCanvasManager and register the panels

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py` (~lines 24, 77-98)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` (`register_components()`)
- Test: `tests/graph_editor/test_toolbar_wiring.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/graph_editor/test_toolbar_wiring.py
import haywire.core.graph.editor  # noqa: F401

from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
)


def test_toolbar_events_have_handlers(make_graph_canvas_manager):
    """The manager's dispatch map must cover the new toolbar events."""
    mgr = make_graph_canvas_manager()
    handler_map = mgr._event_handlers
    assert "selectionBounds" in handler_map
    assert "selectionBoundsHide" in handler_map


def test_toolbar_panels_registered(loaded_graph_editor_library):
    """register_components() must register the three toolbar panels."""
    registry = loaded_graph_editor_library.panel_registry
    from haybale_graph_editor.focuses import ToolbarFocus
    from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
        SelectionContextActions, ToolbarActions,
    )
    sel = registry.get_panels_for_action(SelectionContextActions, ToolbarFocus)
    tb = registry.get_panels_for_action(ToolbarActions, ToolbarFocus)
    names = {c.__name__ for c in sel} | {c.__name__ for c in tb}
    assert {"CopyToolbarPanel", "DeleteToolbarPanel", "OverflowToolbarPanel"} <= names
```

> These two fixtures (`make_graph_canvas_manager`, `loaded_graph_editor_library`) almost certainly need to mirror existing integration fixtures. Before writing them from scratch, run:
> `grep -rln "GraphCanvasManager(\|register_components\|PanelRegistry()" tests/`
> and reuse the established setup. If `make_graph_canvas_manager` is heavy (needs a real Editor/Session), mark this test `@pytest.mark.integration` and assert only the handler-map coverage; the panel-registration assertion can run against a lightweight `PanelRegistry` that you populate by calling the library's `register_components()` directly. Adapt to whatever harness exists — do NOT invent a new app bootstrap.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/graph_editor/test_toolbar_wiring.py -v`
Expected: FAIL — `selectionBounds` not in handler map; toolbar panels not registered.

- [ ] **Step 3: Wire the provider + handlers in the manager**

In `graph_canvas_manager.py`, add the import near line 25:

```python
from .handlers.selection_toolbar import SelectionToolbarProvider, SelectionToolbarHandlers
```

After the `context_menu_handlers` block (~line 88), add:

```python
        toolbar_provider = SelectionToolbarProvider(
            context=self._session.context,
            session=self._session,
            panel_registry=self._panel_registry,
            on_emit_event=self._handle_canvas_event,
            on_emit_sync_event=self.canvas_vue.emit_sync_event,
        )
        self.toolbar_handlers = SelectionToolbarHandlers(provider=toolbar_provider)
        self._toolbar_provider = toolbar_provider  # keep a ref for cleanup
```

Add `self.toolbar_handlers` to the `build_event_handler_map([...])` list (~line 91-98):

```python
        self._event_handlers: Dict[str, Callable] = build_event_handler_map(
            [
                self.visual_layer,
                self.selection,
                self.interactions,
                self.context_menu_handlers,
                self.toolbar_handlers,
            ]
        )
```

In the manager's `cleanup()` method (find it — ~line 209), add a toolbar teardown so the persistent Popup is removed on tab close / hot-reload:

```python
        if getattr(self, "_toolbar_provider", None) is not None:
            self._toolbar_provider.hide()
```

> `_handle_canvas_event` is used as `on_emit_event`: when the provider emits `ContextMenuSelectedEvent` for the overflow, it is routed back through the same dispatch map and hits `ContextMenuHandlers.process_context_menu`. Confirm this self-dispatch is acceptable (it is — `SelectionHandlers` already calls `_handle_canvas_event`-equivalents). No extra wiring needed.

- [ ] **Step 4: Register the panels in `register_components()`**

Open `barn/haybale-graph-editor/haybale_graph_editor/__init__.py` and find where `selection_actions` panels are registered (grep `selection_actions` or `CopySelectionPanel`). Register the toolbar module the **same way**. If panels are auto-discovered by scanning the `panels/` folder, confirm `panels/toolbar/` is included in the scan root; if it's an explicit import list, add:

```python
from .panels.toolbar import toolbar_actions  # noqa: F401  (registers via @panel)
```

> Match the EXACT registration mechanism already used for `panels/context_menu/selection_actions.py`. Read that registration before editing. Do not introduce a new discovery path (CLAUDE.md: do not assume registration paths).

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/graph_editor/test_toolbar_wiring.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the focused suite + the existing context-menu/selection tests for regressions**

Run: `uv run pytest tests/graph_editor -k "toolbar or selection or context" -v`
Expected: all PASS (new toolbar tests + untouched selection/context-menu tests).

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py \
        barn/haybale-graph-editor/haybale_graph_editor/__init__.py \
        tests/graph_editor/test_toolbar_wiring.py
git commit -m "feat(graph-editor): wire floating toolbar provider, handlers, and panel registration"
```

---

## Task 7: Manual smoke test in the running app

**Files:** none (verification only).

- [ ] **Step 1: Launch the app**

Run: `uv run haywire`

- [ ] **Step 2: Verify appearance**

Open a graph with several nodes. Single-click one node → a small floating toolbar with Copy · Delete · ⋯ appears above it. Box-select multiple nodes → the toolbar re-anchors above the combined bounding box. Click empty canvas → toolbar disappears.

- [ ] **Step 3: Verify hide-during-gesture**

With a selection active: start panning the canvas → toolbar disappears; release → it reappears at the new screen position. Zoom with the wheel → toolbar hides during/just after zoom, then re-anchors. Drag the selected nodes → toolbar hides during drag, reappears at the dropped position.

- [ ] **Step 4: Verify actions**

Click Copy → nodes copied (paste via right-click works). Click Delete → selection removed (one undoable step). Click ⋯ → the existing SelectionFocus right-click menu opens with Redraw/Revalidate/Reset.

- [ ] **Step 5: Verify coexistence**

Right-click the selection → the right-click menu opens; confirm the floating toolbar and the right-click menu don't visually fight. (If they overlap awkwardly, note it — a follow-up can suppress the toolbar while the right-click Popup is open by having `on_selection_context`'s open/close also call `toolbar_provider.hide()`/`show_at(last_bounds)`. This is a polish item, not a blocker.)

- [ ] **Step 6: Commit (if any tweaks were needed)**

```bash
git add -A
git commit -m "fix(graph-editor): floating toolbar smoke-test adjustments"
```

---

## Task 8: Update the glossary to match the implemented model

**Files:**
- Modify: `docs/reference/glossary.md` (the **Floating toolbar** + **ToolbarFocus** rows)

The inquisition wrote a **Floating toolbar** entry that implied Vue owns position cheaply. The implemented model is Python-owns-rendering-and-position via a persistent Popup; the canvas only emits low-frequency bounds. Correct it.

- [ ] **Step 1: Replace the Floating toolbar row**

Find the `| **Floating toolbar** |` row and replace its definition cell with:

```
A persistent, Miro-style command surface anchored above the **Selection axis**'s on-screen bounding box whenever the selection is non-empty. A *second* command surface alongside the right-click menu, not a replacement. Rendered with **NiceGUI panels** (`ToolbarFocus`) into a persistent, no-backdrop `Popup` by `SelectionToolbarProvider` — the panel-render sibling of `SessionContextMenuProvider`. **Python owns both content and the positioned container.** The canvas (Vue) computes the selection's screen bounding box and emits a low-frequency `selectionBounds` event on selection-change and on pan/zoom/drag **end**, plus `selectionBoundsHide` on gesture **start** (Miro hide-during-gesture rule — no frame-rate traffic); the provider shows / `setPosition`s / hides the Popup in response. Its curated face is **Copy · Delete · ⋯**, rendered **horizontally** as icon-only buttons (`hui.icon_action`) into a `ui.row` — deliberately unlike the right-click menu, which is a **vertical** column of labelled rows. The ⋯ overflow re-opens the **SelectionFocus** right-click menu (via `ContextMenuSelectedEvent`) so the batch ops live in one place.
```

- [ ] **Step 2: Replace the ToolbarFocus row**

Find `| **ToolbarFocus** |` and update its definition cell to:

```
The Scope (`id="toolbar"`) authors register **floating-toolbar** panels against — the curated face (Copy · Delete · ⋯). Distinct from **SelectionFocus** (the right-click surface). Copy/Delete panels declare `focus=ToolbarFocus` but `actions=SelectionContextActions` (reused); the ⋯ panel uses `actions=ToolbarActions` whose `open_overflow_menu` re-opens the SelectionFocus menu. Polled by `SelectionToolbarProvider`, not by the right-click provider.
```

- [ ] **Step 3: Verify the doc builds**

Run: `uv run mkdocs build 2>&1 | tail -5`
Expected: build succeeds (no broken-link/syntax errors introduced).

- [ ] **Step 4: Commit**

```bash
git add docs/reference/glossary.md
git commit -m "docs(glossary): correct Floating toolbar + ToolbarFocus to implemented model"
```

---

## Task 9: Full quality gate

**Files:** none (verification only).

- [ ] **Step 1: Lint**

Run: `uv run ruff check barn/haybale-graph-editor packages/haywire-core/src/haywire/ui/components/graph`
Expected: no new errors. Fix anything attributable to this change.

- [ ] **Step 2: Format check**

Run: `uv run ruff format --check .`
Expected: clean. If it reports drift, run `uv run ruff format .` and re-commit.

- [ ] **Step 3: Type check**

Run: `uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/`
Expected: no new errors. (Match the CLAUDE.md mypy invocation if checking the full set.)

- [ ] **Step 4: Full test suite**

Run: `uv run pytest -m "not integration"`
Then: `uv run pytest -m integration`
Expected: all PASS.

- [ ] **Step 5: Final commit (if formatting/lint fixes were applied)**

```bash
git add -A
git commit -m "chore(graph-editor): lint/format/type fixes for floating toolbar"
```

---

## Self-review notes (decisions locked, watch-outs for the implementer)

- **Orientation (horizontal toolbar vs vertical menus) — load-bearing:** every existing panel host renders into `Popup.content`, a `ui.column`, producing a vertical stack of full-width labelled rows. The toolbar is the *one* host that is horizontal. Two rules make this work and must both hold: (1) the provider renders panels into a nested `ui.row(...).classes("items-center gap-1 flex-nowrap")` (Task 5 Step 3) — never by adding `flex-row` to the column, which leaves `flex-col`/`w-full` in place and renders wrong; (2) the toolbar panels draw a single `hui.icon_action(...)` each (icon-only), NOT the full-width `hui.button(label, ...)` the vertical selection panels use (Task 4). If a future toolbar panel needs a label, use a tooltip, not inline text — labels would break the row.
- **Edges-only selections:** `_computeSelectionScreenBounds` measures node DOM rects only; an edges-only selection returns `null` → toolbar hides. This is acceptable for v1 (the Miro inspiration is node/sticky-centric). If edges-only toolbars are wanted later, measure edge path bounding boxes too — out of scope here.
- **`ToolbarActionEvent`** (Task 1) is defined but not consumed by the curated face (panels call provider verbs directly via `actions_host`). It is kept as a forward-compat hook and to satisfy the symmetric event set; `_validate_handler_coverage` will warn it has no handler. **Either** add a no-op handler **or** (cleaner) set its `category="system"` instead of `"user"` so the coverage check ignores it. Decide in Task 1 Step 3 and adjust — prefer `category="system"` to avoid a dead handler. *(If you change it, update the Task 1 test's `category` expectation accordingly — the test only checks registration, so it stays green.)*
- **Right-click ⋯ coexistence:** Task 7 Step 5 notes the optional polish of hiding the toolbar while the SelectionFocus Popup is open. The inquisition decided the toolbar suppresses itself during the right-click menu; if you want that guaranteed (not just visually tolerable), have `SessionContextMenuProvider.on_selection_context` call into the toolbar provider's `hide()` on open and `show_at(self._last_bounds)` on close. That requires passing the toolbar provider a reference (or routing through the manager). Left as a follow-up to keep this plan's two providers decoupled; flag to the user if they want it in-scope.
- **Wheel-zoom bounds refresh** (Task 2 Step 4): the exact hook depends on whether the zoom container sets `isDragging` for wheel events. The plan gives a debounce fallback; confirm against `components/zoom/` and pick the simplest correct path.
```
