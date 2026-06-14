# Selected vs. Active (node/edge) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the graph canvas distinguish the single *active* element (the primary/focused node or edge) from the broader *selection*, both in model state and in the visual highlight.

**Architecture:** The selection is a `Set` (command target); the *active* element is a single scalar pointer **into** that set — a node **or** an edge, never both, or `None`. The active pointer is set by explicit single-element focus gestures (plain-click; the "active-promotion" shift-click) and cleared to `None` by bulk/programmatic changes (drag-box, paste). The browser (canvas.vue) owns the live highlight and applies an `node-active` / `connection-active` CSS class **optimistically on gesture** — exactly mirroring how `node-selected` works today — and ships the active id to Python on `SelectionChangedEvent` for a passive record that drives the inspector panels. A new `--hw-node-active` / `--hw-edge-active` theme token gives the active element a crisp accent ring/stroke layered on top of the selected glow.

**Tech Stack:** Python 3, NiceGUI, reactive `signal_field` descriptors (haywire DI), a Vue 3 single-file component (`canvas.vue`), an auto-generated JS event bridge (`generators.py` → `generated/graph_events.js`), and a CSS-variable theme system (`themes/workbench.py` + concrete theme subclasses). Tests: `pytest` (marker `unit`).

**Design source:** This plan implements the design captured in `docs/reference/glossary.md` (terms **Active axis**, **Active-promotion**, **Selection axis**) and `docs/reference/design-guide.md` (tokens `--hw-node-active`, `--hw-edge-active`). Read those two entries before starting.

**Gesture law (the "Active-promotion" rule), for reference in every task:**

| Gesture on element X | Result |
|---|---|
| Plain click on X | selection = {X}; **active = X** |
| Plain click on empty canvas | clear selection; active = None |
| Shift-click, X **not selected** | X added; **active = X** |
| Shift-click, X **selected but not active** | selection unchanged; **active = X** (promote) |
| Shift-click, X **is active** | X **deselected**; active = None |
| Drag-box selects many | active = None |
| Paste (auto-selects new subgraph) | active = None |

Active is a **single** element across both kinds: setting an active node clears any active edge and vice-versa.

---

## File Structure

Touched files, by responsibility:

- **`barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py`** — owns `EditState`. No new fields needed (the existing `active_node` / `active_edge` are the carriers); this plan only changes *how* they are populated. No edit expected unless a helper is added (none is).
- **`packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py`** — the single source of truth for canvas events. Add an `activeNodeId` + `activeEdgeId` field to `SelectionChangedEvent`, and an `active` descriptor to `SyncSelectionsEvent`.
- **`packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`** — auto-generated JS bridge. Regenerated from the Python definitions; never hand-edited except via the generator.
- **`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py`** — `SelectionHandlers.process_selection_change` derives the active element. Replace the `next(iter(...))` derivation with the event-carried active id; clear the other kind. Also: the paste path sets active = None.
- **`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py`** — `sync_selections` emits `SyncSelectionsEvent`; add the active arg.
- **`packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`** — owns the live selection + highlight. Add `activeElement` to `selectionState`, apply/clear `node-active` / `connection-active`, implement the active-promotion shift-click law, emit the active id, and reconcile active in `_syncSelections`. Plus the two CSS rules for the active highlight.
- **`packages/haywire-core/src/haywire/ui/themes/workbench.py`** — add `node_active` / `edge_active` to `_CSS_TOKEN_MAP`.
- **`barn/haybale-studio/haybale_studio/themes/workbench.py`** — concrete shipped dark + light themes: give `node_active` / `edge_active` values.
- **`barn/haybale-testing/haybale_testing/themes/workbench.py`** — test themes: give `node_active` / `edge_active` values (keeps `to_css_vars` coverage tests honest).
- **`tests/ui/test_canvas_handlers/test_selection_handlers.py`** — extend with active-derivation tests.
- **Docs already updated** during design: `docs/reference/glossary.md`, `docs/reference/design-guide.md`. No doc tasks remain except a final consistency check (Task 9).

---

## Pre-flight baseline

- [ ] **Step 0: Establish a clean baseline before touching anything**

Run:
```sh
uv run ruff check packages/haywire-core/src/haywire/ui/components/graph/ barn/haybale-graph-editor/ packages/haywire-core/src/haywire/ui/themes/ barn/haybale-studio/haybale_studio/themes/
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/
uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -q
```
Expected: all clean / all pass. If anything fails here, STOP and raise it with the user — per CLAUDE.md the codebase has no pre-existing errors, so a failure means the environment is wrong. Any new failure after your edits is yours.

---

### Task 1: Add active-id fields to `SelectionChangedEvent` (Python side, wire-tested)

The Vue layer must tell Python which element is active. We add two optional fields (one per kind) rather than one polymorphic field, because the existing dataclass/generator pipeline has no kind tag and downstream code already branches on node-vs-edge. Exactly one is non-empty at a time (or both empty = no active element).

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py:155-159`
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/ui/test_canvas_handlers/test_selection_handlers.py`, after `test_paste_event_carries_clipboard_text` (around line 228):

```python
def test_selection_changed_event_carries_active_ids():
    from haywire.ui.components.graph.event_definitions import SelectionChangedEvent

    e = SelectionChangedEvent(
        selectedNodes=["n1", "n2"],
        selectedEdges=[],
        activeNodeId="n2",
        activeEdgeId="",
    )
    assert e.activeNodeId == "n2"
    assert e.activeEdgeId == ""
    # survives Python wire serialization, nested under "data"
    d = e.to_dict()["data"]
    assert d["activeNodeId"] == "n2"
    assert d["activeEdgeId"] == ""

    # defaults stay empty for backward compat (existing call sites omit them)
    e2 = SelectionChangedEvent(selectedNodes=[], selectedEdges=[])
    assert e2.activeNodeId == ""
    assert e2.activeEdgeId == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py::test_selection_changed_event_carries_active_ids -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'activeNodeId'`.

- [ ] **Step 3: Add the fields**

In `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py`, change the `SelectionChangedEvent` dataclass (currently lines 155-159) to:

```python
@graph_event("selectionChanged", category="user", description="Selection state changed")
@dataclass
class SelectionChangedEvent(BaseGraphEvent):
    selectedNodes: List[str]
    selectedEdges: List[str]
    # The single active (primary) element, by kind. At most one is non-empty;
    # both empty means the selection has no primary (bulk/programmatic change).
    # Defaults keep existing positional call sites working.
    activeNodeId: str = ""
    activeEdgeId: str = ""
```

> Note: the new fields MUST be appended **after** the existing ones and carry defaults — the JS generator emits creator params positionally in field order, and existing callers pass only the first two.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py::test_selection_changed_event_carries_active_ids -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py tests/ui/test_canvas_handlers/test_selection_handlers.py
git commit -m "feat(canvas): carry active element id on SelectionChangedEvent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Add `active` field to `SyncSelectionsEvent` (Python→Vue path)

When Python drives selection programmatically (paste), the sync event must also carry the active element so the canvas can reconcile the `node-active` class. We use one field shaped `{"kind": "node"|"edge"|"", "id": str}` because the sync handler reconciles a single element regardless of kind.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py:332-336`
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`

- [ ] **Step 1: Write the failing test**

Add to the same test file, after the test from Task 1:

```python
def test_sync_selections_event_carries_active():
    from haywire.ui.components.graph.event_definitions import SyncSelectionsEvent

    e = SyncSelectionsEvent(nodes=["n1"], edges=[], active={"kind": "node", "id": "n1"})
    assert e.active == {"kind": "node", "id": "n1"}
    assert e.to_dict()["data"]["active"] == {"kind": "node", "id": "n1"}

    # default is the "no active" sentinel; existing emit sites omit it
    e2 = SyncSelectionsEvent(nodes=[], edges=[])
    assert e2.active == {"kind": "", "id": ""}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py::test_sync_selections_event_carries_active -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'active'`.

- [ ] **Step 3: Add the field**

In `event_definitions.py`, change `SyncSelectionsEvent` (currently lines 332-336) to:

```python
@graph_event("syncSelections", category="sync", description="Sync selection state to UI")
@dataclass
class SyncSelectionsEvent(BaseGraphEvent):
    nodes: List[str]
    edges: List[str]
    # Single active element to reconcile in the canvas: {"kind": "node"|"edge"|"", "id": str}.
    # {"kind": "", "id": ""} means "no primary" (clears any active highlight).
    active: Dict[str, str] = field(default_factory=lambda: {"kind": "", "id": ""})
```

`Dict` and `field` are already imported at the top of the file (lines 14-15) — confirm; if `Dict` is missing add it to the `typing` import.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py::test_sync_selections_event_carries_active -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py tests/ui/test_canvas_handlers/test_selection_handlers.py
git commit -m "feat(canvas): carry active element on SyncSelectionsEvent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Regenerate the JS event bridge

The JS event creators are generated from the Python definitions. After Tasks 1-2 the generated file is stale (missing the new fields).

**Files:**
- Modify (regenerate): `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`

> **Why not `scripts/generate_vue_events.py`?** That script writes to a stale path (`graph_canvas/generated/`) that no longer exists. The live generator entry point is `generators.main()`, which writes next to itself at `components/graph/generated/graph_events.js` — the path `canvas.py:18` actually loads.

- [ ] **Step 1: Regenerate**

Run:
```sh
uv run python -c "from haywire.ui.components.graph import generators; generators.main()"
```
Expected stdout: `Vue event constants generated successfully!` and a `File: .../components/graph/generated/graph_events.js` line.

- [ ] **Step 2: Verify the generated creator signatures changed**

Run:
```sh
grep -n "createSelectionChanged\|SYNC_SELECTIONS\|active" packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js | head
```
Expected: `createSelectionChanged(selectedNodes, selectedEdges, activeNodeId, activeEdgeId, sessionId = 'default')` appears, and the `data: { ... }` for both selection events now lists the new fields.

- [ ] **Step 3: Sanity-check nothing else regenerated unexpectedly**

Run: `git diff --stat packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`
Expected: only `graph_events.js` changed. Inspect `git diff` to confirm the only semantic changes are the two selection events (plus possibly whitespace) — the generator is deterministic so unrelated events should be byte-identical.

- [ ] **Step 4: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js
git commit -m "chore(canvas): regenerate JS event bridge for active fields

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Derive `active_node` / `active_edge` from the event, not `next(iter(...))`

Replace the non-deterministic arbitrary-set-element derivation in `SelectionHandlers.process_selection_change` with the event-carried active id, enforcing single-active-across-kinds.

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py:60-84`
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/ui/test_canvas_handlers/test_selection_handlers.py`, in the "SelectionChanged" section (after `test_selection_changed_notifies_session`, ~line 166):

```python
def test_active_node_follows_event_active_id(handler, session, edit_state_cls):
    """active_node is the event's activeNodeId, not an arbitrary set member."""
    handler.process_selection_change(
        SelectionChangedEvent(
            selectedNodes=["n1", "n2", "n3"],
            selectedEdges=[],
            activeNodeId="n2",
            activeEdgeId="",
        )
    )
    edit = session.context.data[edit_state_cls]
    # handler.graph.get_node_wrapper is a MagicMock; assert it was asked for n2.
    handler.graph.get_node_wrapper.assert_called_with("n2")
    assert edit.active_edge is None


def test_active_edge_clears_active_node_single_active(handler, session, edit_state_cls):
    """An active edge means no active node (single active element across kinds)."""
    handler.process_selection_change(
        SelectionChangedEvent(
            selectedNodes=["n1"],
            selectedEdges=["e1"],
            activeNodeId="",
            activeEdgeId="e1",
        )
    )
    edit = session.context.data[edit_state_cls]
    assert edit.active_node is None
    handler.graph.get_edge_wrapper.assert_called_with("e1")


def test_no_active_id_means_none(handler, session, edit_state_cls):
    """Bulk selection (drag-box) carries no active id -> active_node/edge are None."""
    handler.process_selection_change(
        SelectionChangedEvent(
            selectedNodes=["n1", "n2"],
            selectedEdges=[],
            activeNodeId="",
            activeEdgeId="",
        )
    )
    edit = session.context.data[edit_state_cls]
    assert edit.active_node is None
    assert edit.active_edge is None
```

> The existing `test_selection_changed_notifies_session` constructs the event with only `selectedNodes`/`selectedEdges` — the defaults `activeNodeId=""`/`activeEdgeId=""` keep it valid, and with the new logic both active values become `None`. That test only asserts on `selected_*` and the published signal, so it stays green. Confirm in Step 4.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -k "active" -v`
Expected: the three new tests FAIL — `test_no_active_id_means_none` fails because the current code sets `active_node` from `next(iter(selected_nodes))` (non-None), and the others fail because `get_node_wrapper`/`get_edge_wrapper` are called with an arbitrary id, not the event's active id.

- [ ] **Step 3: Rewrite the derivation**

In `selection.py`, replace the body of `process_selection_change` (lines 60-84) with:

```python
    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Update local selection state and write through to SessionContext.

        The active (primary) element is whatever the canvas marked active on
        the event — a node OR an edge, never both. An empty active id means the
        selection has no primary (bulk/programmatic change), so both active
        pointers are cleared. See the Active axis / Active-promotion glossary
        entries.
        """
        logger.debug(
            f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedEdges}, "
            f"activeNode={event.activeNodeId!r}, activeEdge={event.activeEdgeId!r}"
        )
        self.selected_nodes = set(event.selectedNodes)
        self.selected_edges = set(event.selectedEdges)

        if self._session is None:
            return

        ctx = self._session.context
        active_node = (
            self.graph.get_node_wrapper(event.activeNodeId) if event.activeNodeId else None
        )
        active_edge = (
            self.graph.get_edge_wrapper(event.activeEdgeId) if event.activeEdgeId else None
        )
        edit_state = ctx.data[EditState]
        edit_state.selected_nodes = self.selected_nodes
        edit_state.selected_edges = self.selected_edges
        edit_state.active_node = active_node
        edit_state.active_edge = active_edge
        ctx.active_component = active_node.registry_key if active_node is not None else None

        self._session.publish(SelectionMoved())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -v`
Expected: all tests in the file PASS — including the new three and the pre-existing `test_selection_changed_*` (which only assert on `selected_*` / the published signal).

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py tests/ui/test_canvas_handlers/test_selection_handlers.py
git commit -m "feat(graph-editor): derive active element from event, drop next(iter) guess

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Paste sets active = None, and sync_selections carries it

After a paste the new subgraph is auto-selected with **no primary** (per the gesture law). `process_paste_clipboard` must clear active in `EditState`, and `VisualLayerHandlers.sync_selections` must emit the "no active" sentinel so the canvas clears any stale active ring.

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py:152-162`
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:329-335`
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`

- [ ] **Step 1: Write the failing test**

Add to the test file, in the paste section (after `test_paste_auto_selects_pasted_elements`, ~line 337):

```python
def test_paste_clears_active(graph, session, edit_state_cls):
    """A pasted subgraph is selected but has no active primary."""
    from haywire.core.undo.actions.graph_actions import ClipboardData

    editor = MagicMock()
    editor.paste_clipboard.return_value = (["new_n1", "new_n2"], [])
    visual_layer = MagicMock()
    h = SelectionHandlers(
        graph=graph, editor=editor, session_id="sess",
        session=session, visual_layer=visual_layer,
    )
    # seed a stale active so we can prove it gets cleared
    edit = session.context.data[edit_state_cls]
    edit.active_node = MagicMock()

    payload = {
        "haywire_clipboard": True,
        "format_version": 1,
        "source": {"session_id": "x", "timestamp": 99.0},
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "nodes": {}, "edges": {},
    }
    h.process_paste_clipboard(
        UserPasteClipboardEvent(canvasX=5.0, canvasY=6.0, clipboardText=json.dumps(payload))
    )
    assert edit.active_node is None
    assert edit.active_edge is None
    # sync_selections is called with the new selection; the no-active sentinel
    # is passed as the `active` kwarg.
    _, kwargs = visual_layer.sync_selections.call_args
    assert kwargs.get("active") == {"kind": "", "id": ""}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py::test_paste_clears_active -v`
Expected: FAIL — `edit.active_node` is still the seeded MagicMock (paste doesn't clear it today), and `sync_selections` is called positionally without an `active` kwarg.

- [ ] **Step 3a: Clear active in the paste handler**

In `selection.py`, in `process_paste_clipboard`, replace the auto-select block (lines 154-162) with:

```python
        # Auto-select the freshly pasted subgraph so the user can drag it
        # immediately, but with NO primary (a programmatic bulk change clears
        # the active element — see the Active axis glossary entry). Update both
        # the local record and the session EditState, then push to the canvas.
        self.selected_nodes = set(new_node_ids)
        self.selected_edges = set(new_edge_ids)
        if self._session is not None:
            edit_state = self._session.context.data[EditState]
            edit_state.selected_nodes = self.selected_nodes
            edit_state.selected_edges = self.selected_edges
            edit_state.active_node = None
            edit_state.active_edge = None
        if self._visual_layer is not None:
            self._visual_layer.sync_selections(
                new_node_ids, new_edge_ids, active={"kind": "", "id": ""}
            )
```

- [ ] **Step 3b: Extend `sync_selections` to carry active**

In `visual_layer.py`, replace `sync_selections` (lines 329-335) with:

```python
    def sync_selections(self, selected_nodes, selected_edges, active=None):
        """Emit consolidated selection sync event to Vue.

        ``active`` is the single primary element to reconcile on the canvas:
        ``{"kind": "node"|"edge"|"", "id": str}``. ``None`` (the default) means
        "no primary" and is sent as the ``{"kind": "", "id": ""}`` sentinel,
        clearing any active highlight.
        """
        if active is None:
            active = {"kind": "", "id": ""}
        sync_event = SyncSelectionsEvent(
            nodes=list(selected_nodes),
            edges=list(selected_edges),
            active=active,
        )
        self.canvas_vue.emit_sync_event(sync_event)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -v`
Expected: all PASS. Note `test_paste_auto_selects_pasted_elements` asserts `visual_layer.sync_selections.assert_called_once_with(["new_n1", "new_n2"], ["new_e1"])` — this will now FAIL because we added the `active` kwarg. Update that assertion in the same step to:

```python
    visual_layer.sync_selections.assert_called_once_with(
        ["new_n1", "new_n2"], ["new_e1"], active={"kind": "", "id": ""}
    )
```

Re-run; expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py tests/ui/test_canvas_handlers/test_selection_handlers.py
git commit -m "feat(graph-editor): paste selects with no active primary

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Add `node_active` / `edge_active` theme tokens

Wire the two new CSS variables through the theme system: map entries in the base `WorkbenchTheme`, and concrete values in the shipped + test themes. `to_css_vars()` only emits a token if both the map entry AND a class attribute exist, so all three files are required.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/themes/workbench.py:104-108`
- Modify: `barn/haybale-studio/haybale_studio/themes/workbench.py:56-61` (dark) and `:146-151` (light)
- Modify: `barn/haybale-testing/haybale_testing/themes/workbench.py` (TestDarkTheme ~line 41-44, TestLightTheme ~line 100-103)
- Test: `tests/studio/` (new tiny test, see Step 1)

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_theme_active_tokens.py`:

```python
"""The active-element highlight tokens must be emitted by shipped themes."""

import pytest

pytestmark = pytest.mark.unit


def test_shipped_themes_emit_active_tokens():
    from haybale_studio.themes.workbench import HaywireDarkTheme, HaywireLightTheme

    for theme_cls in (HaywireDarkTheme, HaywireLightTheme):
        css = theme_cls().to_css_vars()
        assert "--hw-node-active" in css, f"{theme_cls.__name__} missing --hw-node-active"
        assert "--hw-edge-active" in css, f"{theme_cls.__name__} missing --hw-edge-active"
        # active must differ from selected so the two tiers are distinguishable
        assert css["--hw-node-active"] != css["--hw-node-selected"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/studio/test_theme_active_tokens.py -v`
Expected: FAIL — `--hw-node-active` not in css (no map entry yet).

- [ ] **Step 3a: Add map entries to the base theme**

In `packages/haywire-core/src/haywire/ui/themes/workbench.py`, in `_CSS_TOKEN_MAP`, change the node-chrome and edges blocks (lines 104, 108) to insert the two new mappings:

```python
        "node_selected": "--hw-node-selected",
        "node_active": "--hw-node-active",
        "node_shadow": "--hw-node-shadow",
```
and
```python
        "edge_default": "--hw-edge-default",
        "edge_selected": "--hw-edge-selected",
        "edge_active": "--hw-edge-active",
```

- [ ] **Step 3b: Add concrete values to the shipped themes**

In `barn/haybale-studio/haybale_studio/themes/workbench.py`:

`HaywireDarkTheme` — after `node_selected = "#4f8ef7"` (line 56) add:
```python
    node_active = "#8fb8ff"
```
and after `edge_selected = "#4f8ef7"` (line 61) add:
```python
    edge_active = "#8fb8ff"
```

`HaywireLightTheme` — after `node_selected = "#4f8ef7"` (line 146) add:
```python
    node_active = "#1f5fd0"
```
and after `edge_selected = "#4f8ef7"` (line 151) add:
```python
    edge_active = "#1f5fd0"
```

> Rationale: in both themes `node_selected == accent == #4f8ef7`, which is *why* selected and active look identical today. `node_active` is a brighter (dark theme) / deeper (light theme) accent so the active ring reads distinct even before the shape difference. The hard ring vs. soft glow (Task 7) carries the rest.

- [ ] **Step 3c: Add values to the test themes**

In `barn/haybale-testing/haybale_testing/themes/workbench.py`:

`TestDarkTheme` — after `node_selected = "#aabbcc"` (~line 41) add `node_active = "#ddeeff"`; after `edge_selected = "#aabbcc"` (~line 44) add `edge_active = "#ddeeff"`.

`TestLightTheme` — after `node_selected = "#0055cc"` (~line 100) add `node_active = "#0033aa"`; and the matching `edge_active = "#0033aa"` after its `edge_selected`.

> Read the file first to confirm the exact surrounding lines before editing — the test theme has both classes; add to **both**.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/studio/test_theme_active_tokens.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/themes/workbench.py barn/haybale-studio/haybale_studio/themes/workbench.py barn/haybale-testing/haybale_testing/themes/workbench.py tests/studio/test_theme_active_tokens.py
git commit -m "feat(themes): add node/edge active highlight tokens

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Canvas — track active, apply the highlight class, and emit the active id

This is the browser-side core. `canvas.vue` gains an `activeElement` in `selectionState`, applies `node-active` / `connection-active` optimistically on gesture (mirroring `node-selected`), implements the active-promotion shift-click law, emits the active id on `SelectionChangedEvent`, and reconciles active in `_syncSelections`. Plus two CSS rules.

> **No automated test:** `canvas.vue` is browser JS with no unit harness in this repo (selection logic is verified via the Python handler tests already written). This task is verified by reading + a manual smoke check (Task 8). Keep changes surgical and mirror existing patterns exactly.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` — `selectionState` (~line 80), `_selectElement`/`_deSelectElement`/`_clearSelection` (~1225-1283), `_handleElementSelection` (~1205-1223), `_emitSelectionChanged` (~1285), `_syncSelections` (~547-601), `_updateNodeVisualSelection`/`_updateEdgeVisualSelection` (~2027-2058), and the `<style>` block (~2480).

- [ ] **Step 1: Add `activeElement` to selection state**

In the `selectionState` object (~line 80-82), add a field:

```javascript
            selectionState: {
                selectedNodes: new Set(),
                selectedEdges: new Set(),
                activeElement: null,  // { kind: 'node'|'edge', id: string } | null — the single primary
                lastClickTime: 0,
            },
```
(Preserve any other existing keys like `lastClickTime` — read the real object first and only add `activeElement`.)

- [ ] **Step 2: Add active-class helpers**

Add two methods next to `_updateNodeVisualSelection` (~line 2027). They mirror the selection-class helpers but toggle the *active* class and use the same retry-for-late-DOM pattern:

```javascript
        _updateNodeVisualActive(nodeId, active, _retries = 6) {
            const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
            if (nodeElement) {
                if (active) {
                    nodeElement.classList.add('node-active');
                } else {
                    nodeElement.classList.remove('node-active');
                }
            } else if (active && _retries > 0) {
                setTimeout(() => this._updateNodeVisualActive(nodeId, active, _retries - 1), 50);
            }
        },

        _updateEdgeVisualActive(edge_id, active, _retries = 6) {
            const edgeInfo = this.edgePaths.get(edge_id);
            if (edgeInfo && edgeInfo.path) {
                if (active) {
                    edgeInfo.path.classList.add('connection-active');
                } else {
                    edgeInfo.path.classList.remove('connection-active');
                }
            } else if (active && _retries > 0) {
                setTimeout(() => this._updateEdgeVisualActive(edge_id, active, _retries - 1), 50);
            }
        },
```

- [ ] **Step 3: Add a `_setActive` helper that enforces single-active-across-kinds**

Add near the other selection methods (~line 1225). It clears the previous active element's class (whatever kind) before setting the new one:

```javascript
        _setActive(kind, id) {
            // Clear the previous active element's highlight (could be either kind).
            const prev = this.selectionState.activeElement;
            if (prev) {
                if (prev.kind === 'node') this._updateNodeVisualActive(prev.id, false);
                else if (prev.kind === 'edge') this._updateEdgeVisualActive(prev.id, false);
            }
            if (kind && id) {
                this.selectionState.activeElement = { kind, id };
                if (kind === 'node') this._updateNodeVisualActive(id, true);
                else if (kind === 'edge') this._updateEdgeVisualActive(id, true);
            } else {
                this.selectionState.activeElement = null;
            }
        },
```

- [ ] **Step 4: Implement the active-promotion shift-click law**

Replace `_handleElementSelection` (~lines 1205-1223) with the gesture law:

```javascript
        _handleElementSelection(isShiftClick, elementType, elementId) {
            console.log(`Element clicked: ${elementType}:${elementId}, shift: ${isShiftClick}`);

            const active = this.selectionState.activeElement;
            const isActive = active && active.kind === elementType && active.id === elementId;
            const isSelected = this._isElementSelected(elementType, elementId);

            if (isShiftClick) {
                if (isActive) {
                    // Shift-click the active element -> deselect it; active -> none.
                    this._deSelectElement(elementType, elementId);
                    this._setActive('', '');
                } else if (isSelected) {
                    // Selected but not active -> promote (selection unchanged).
                    this._setActive(elementType, elementId);
                } else {
                    // Not selected -> add and make active.
                    this._selectElement(elementType, elementId, true);
                    this._setActive(elementType, elementId);
                }
            } else {
                // Plain click: replace selection with this one element; it is active.
                this._clearSelection();
                this._selectElement(elementType, elementId, false);
                this._setActive(elementType, elementId);
            }

            this._emitSelectionChanged();
        },
```

- [ ] **Step 5: Clear active in `_clearSelection`**

In `_clearSelection` (~line 1264-1283), after clearing the selected sets, also clear active. Add before the final `console.log`:

```javascript
            // Clear the active primary too.
            if (this.selectionState.activeElement) {
                const a = this.selectionState.activeElement;
                if (a.kind === 'node') this._updateNodeVisualActive(a.id, false);
                else if (a.kind === 'edge') this._updateEdgeVisualActive(a.id, false);
                this.selectionState.activeElement = null;
            }
```

- [ ] **Step 6: Drag-box select clears active**

Find the rubber-band / box-select path that bulk-populates the selection (search for where `selectionState.selectedNodes` is assigned a freshly-built `Set` after a box drag — around lines 553-598 region for the sync path, and the box-select handler). At the point where a box selection finalizes its set, call `this._setActive('', '')` so a bulk select has no primary, then `this._emitSelectionChanged()`. If the box-select reuses `_selectElement` in a loop, add the single `this._setActive('', '')` call **after** the loop, before emit. Read the surrounding handler first and place the clear at the one finalization point.

- [ ] **Step 7: Emit the active id**

Replace `_emitSelectionChanged` (~line 1285) to include the active id, split by kind:

```javascript
        _emitSelectionChanged() {
            const a = this.selectionState.activeElement;
            const activeNodeId = a && a.kind === 'node' ? a.id : '';
            const activeEdgeId = a && a.kind === 'edge' ? a.id : '';
            this.emitCanvasEvent(EventCreators.createSelectionChanged(
                Array.from(this.selectionState.selectedNodes),
                Array.from(this.selectionState.selectedEdges),
                activeNodeId,
                activeEdgeId
            ));
        },
```

(The generated `createSelectionChanged` now takes these four positional args — confirm against the regenerated `graph_events.js` from Task 3.)

- [ ] **Step 8: Reconcile active in `_syncSelections`**

In `_syncSelections` (~lines 547-601), the handler receives `data` from `SyncSelectionsEvent`, which now includes `active`. After the existing node/edge set reconciliation (just before the closing `console.log` at line 600), add:

```javascript
            // Reconcile the active primary (programmatic paths e.g. paste send
            // {kind:'', id:''} to clear it).
            const active = data.active || { kind: '', id: '' };
            this._setActive(active.kind, active.id);
```

- [ ] **Step 9: Add the CSS rules**

In the scoped node `<style>` block (after the `[data-node-id].node-selected` rules, ~line 2486), add the active ring layered on top of the selected glow. Use the token, never a hardcoded color:

```css
[data-node-id].node-active {
    outline: 2px solid var(--hw-node-active) !important;
    outline-offset: 1px;
}
```

In the global connection `<style>` block (where `.connection-selected` lives — search for it), add:

```css
.connection-active {
    stroke: var(--hw-edge-active) !important;
    stroke-width: 4 !important;
}
```

> The `.connection-selected` rule currently lives in a non-scoped `<style>` and the selected stroke-width is set inline in `_updateEdgeVisualSelection`. The `!important` here wins over the inline `strokeWidth='3'` set on select; that's intended — active is heavier than selected.

- [ ] **Step 10: (Same pass) migrate the hardcoded selected color to the token**

Per the design (and the design-guide "no hardcoded colors" rule), replace the hardcoded blue in `[data-node-id].node-selected` (~lines 2480-2493). Change the three `rgba(74, 144, 226, ...)` occurrences to use the token. The glow is the only sanctioned `box-shadow` (it's a node, not chrome — `--hw-node-shadow`/`--hw-node-selected` are explicitly allowed). New rule:

```css
[data-node-id].node-selected {
    z-index: 1000 !important;
    outline: none !important;
    box-shadow: 0 8px 25px var(--hw-node-shadow),
        0 0 0 2px var(--hw-node-selected) !important;
}

[data-node-id].node-selected:hover {
    outline: none !important;
    box-shadow: 0 12px 35px var(--hw-node-shadow),
        0 0 0 2px var(--hw-node-selected) !important;
}
```

(If `--hw-node-selected` as a flat color in the spread reads too hard vs. the old translucent glow, that's acceptable — the token is the source of truth and themers tune it. Do **not** reintroduce a hardcoded rgba.)

- [ ] **Step 11: Lint the touched Python/JS-adjacent files**

Run:
```sh
uv run ruff check packages/haywire-core/src/haywire/ui/components/graph/ barn/haybale-graph-editor/
uv run ruff format --check packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py
```
Expected: clean. (`.vue` is not ruff-checked; it has no repo linter.)

- [ ] **Step 12: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue
git commit -m "feat(canvas): two-tier selected/active highlight + active-promotion shift-click

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Full quality gate + manual smoke verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full type-check across the declared package set**

Run (the exact set from CLAUDE.md):
```sh
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```
Expected: no errors. Fix any new ones (e.g. the `Dict` default-factory typing on `SyncSelectionsEvent`).

- [ ] **Step 2: Run lint + format check (both — CI runs both)**

Run:
```sh
uv run ruff check .
uv run ruff format --check .
```
Expected: both clean. If format drifts, run `uv run ruff format .` and re-commit.

- [ ] **Step 3: Run the unit suite**

Run: `uv run pytest -m unit -q`
Expected: all pass.

- [ ] **Step 4: Run the full suite (not integration)**

Run: `uv run pytest -m "not integration" -q`
Expected: all pass.

- [ ] **Step 5: Manual smoke check in the running app**

Run: `uv run haywire`
Then in a graph with ≥3 nodes, verify each row of the gesture-law table:
- Plain-click a node → it shows BOTH the selected glow AND the active ring; the Node/Ports/Settings panels appear for it.
- Shift-click a second node → the ring moves to the second; both have the glow.
- Shift-click a third (selected-but-not-active via prior promotion) → ring moves, nothing deselects.
- Shift-click the active node → it deselects; no node has the ring; single-node panels hide; SelectionFocus (Copy/Delete) still shows for the remaining two.
- Drag-box several nodes → all glow, none rings; single-node panels hidden.
- Shift-click a member of the box selection → it gains the ring (promotion recovery).
- Click an edge → edge shows active stroke; any node ring clears (single active across kinds); Edge panel appears.
- Copy then paste → pasted nodes are selected (glow) with no ring; single-node panels hidden.
- Plain-click empty canvas → everything clears.

Record the result in the PR description. If any row misbehaves, the fix is in Task 7 (canvas.vue) — do not patch the Python handlers, which are unit-covered.

- [ ] **Step 6: Commit (only if Step 2 reformatted anything)**

```bash
git add -A
git commit -m "style: ruff format after selected/active highlight work

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Docs consistency check

The glossary (`Active axis`, `Active-promotion`) and design-guide tokens were updated during design. Confirm they match the shipped behavior and that no other doc still describes the old `next(iter(...))` derivation.

**Files:** `docs/reference/glossary.md`, `docs/reference/design-guide.md` (verify only; edit only if stale).

- [ ] **Step 1: Grep for stale derivation references**

Run:
```sh
grep -rn "next(iter" docs/
grep -rn "active_node\|active_edge\|node-active\|edge-active" docs/reference/
```
Expected: no `next(iter` in `docs/` describing selection (the glossary entry already replaced it; if any doc still presents it as current behavior, fix it). The token references should resolve to the entries added during design.

- [ ] **Step 2: Confirm the two glossary terms read true against the final code**

Read `docs/reference/glossary.md` entries **Active axis** and **Active-promotion**. Confirm: (a) "at most one of which is non-None at a time" matches Task 4's clearing; (b) the shift-click table matches Task 7's `_handleElementSelection`; (c) "cleared to None by bulk/programmatic" matches Tasks 5-6. If wording drifted, correct it.

- [ ] **Step 3: Preview the docs build (optional but recommended)**

Run: `uv run mkdocs build --strict`
Expected: builds with no broken-link / warning failures.

- [ ] **Step 4: Commit (only if docs were edited)**

```bash
git add docs/
git commit -m "docs: reconcile selected/active terms with implementation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review Notes (for the implementer)

- **Spec coverage:** model distinction (Tasks 1,2,4), last-touched primary (Task 7 gesture law + Task 4 derivation), single-active-across-kinds (Tasks 4,7 `_setActive`), bulk/paste → None (Tasks 5,6,7 steps 5-6), active-promotion shift-click incl. promote-when-selected and deselect-active (Task 7 step 4), two-tier highlight (Tasks 6,7), token migration of the hardcoded selected blue (Task 7 step 10), docs (Task 9). All covered.
- **Type consistency:** Python field names `activeNodeId` / `activeEdgeId` (SelectionChangedEvent) and `active: {"kind","id"}` (SyncSelectionsEvent) are used identically in handler, generator output, and canvas.vue. JS helper names `_updateNodeVisualActive` / `_updateEdgeVisualActive` / `_setActive` are used consistently. `sync_selections(..., active=...)` signature matches every call site (paste in Task 5; canvas reconcile reads `data.active`).
- **Generator caveat:** new event fields are appended last with defaults (Task 1/2) so the positional JS creators stay backward-compatible for any caller that doesn't pass them; canvas.vue's `createSelectionChanged` call is updated to pass all four (Task 7 step 7).
- **Known sharp edge:** Task 7 step 6 (drag-box clears active) requires locating the box-select finalization in `canvas.vue` — read that handler before editing; it's the one place that isn't a copy of an existing pattern.
