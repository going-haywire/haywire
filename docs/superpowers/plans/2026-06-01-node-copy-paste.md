# Node Copy/Paste Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the graph canvas's existing (non-functional) copy/paste menu actions work — copy a selection of nodes+edges, paste them as fresh instances with new IDs and remapped edges, portable across sessions and across separate Studio processes on the same machine via the OS clipboard.

**Architecture:** Copy serializes a *slice* of the graph (selected nodes' `NodeWrapper.serialize()` dicts + selected edges' `Edge.to_dict()` dicts, both-endpoints rule) into a versioned JSON payload, stores it in the per-session in-process mirror (`EditState.clipboard`) AND writes it to the OS clipboard as text. Paste reads the OS clipboard **in the Vue layer** (to dodge a NiceGUI async trap) and ships the text back on the paste event; the synchronous Python handler parses it, picks the newer of payload/mirror by timestamp, then runs an undoable `PasteClipboardAction` that mints new node IDs, remaps edge endpoints, and offsets positions to the paste point. **Paste is "load a slice of a graph":** unknown `registry_key`s are tolerated exactly as `load_from_dict` tolerates them — the node factory falls back to a placeholder error node carrying the serialized `node_data`, and the canvas surfaces the `HaywireException` warning state. No pre-validation, no all-or-nothing abort.

**Tech Stack:** Python 3, NiceGUI/Quasar/Vue 3, the haywire reactive-props + undo (`CompositeAction`/`HistoryManager`) systems, `uv` for tooling, `pytest` for tests.

---

## Background: ground-truth facts (read before starting)

These were verified against the codebase during design. Trust them over your assumptions.

- **Serialization shapes already exist and are reused as-is:**
  - `NodeWrapper.serialize(include_data=True)` → `{"node_id", "registry_key", "position", "node_data"}` — [node_wrapper.py:679](../../../packages/haywire-core/src/haywire/core/node/node_wrapper.py#L679).
  - `Edge.to_dict()` → `{"source_node_id", "outlet_port_id", "sink_node_id", "inlet_port_id", "edge_type", "chain_adapter_keys", "is_lazy"}` — [edge.py:42](../../../packages/haywire-core/src/haywire/core/edge/edge.py#L42).
  - These are the *same* shapes `Graph.to_dict()` emits and `Graph.load_from_dict()` consumes — [base.py:875](../../../packages/haywire-core/src/haywire/core/graph/base.py#L875).
- **The clipboard mirror already exists:** `EditState.clipboard: Optional[ClipboardData]` — [edit_state.py:30](../../../barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py). It is per-session.
- **`ClipboardData` currently stores IDs only** and explicitly documents it "may be revised to hold serialized state" — [graph_actions.py:399](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py#L399). We revise it to hold the serialized payload dict.
- **Handlers already exist in `SelectionHandlers`** (NOT a new class — design override of inquisition Q4): `process_copy_selection` is implemented (stores IDs), `process_paste_clipboard` is a stub, `_calculate_selection_bounds` exists — [selection.py](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py).
- **`AddNodeAction` only takes `registry_key`** and builds a blank node — [graph_actions.py:17](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py#L17). We extend it with an optional `node_data` kwarg.
- **`PasteClipboardAction` and `DuplicateNodeAction` are `NotImplementedError` scaffolds** — [graph_actions.py:427](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py#L427). We implement `PasteClipboardAction`; `DuplicateNodeAction` stays out of scope.
- **Unknown registry_keys degrade gracefully (no validation needed):** `NodeFactory.get_node(unknown_key)` returns `(error_node_class, NodeNotFoundError)` — it falls back to a registered **error node** placeholder, never `None` — [factory.py:99-113](../../../packages/haywire-core/src/haywire/core/node/factory.py#L99). `NodeWrapper.build(node_data)` then instantiates that placeholder, retains the `node_data`, and records the `HaywireException` as node state ([node_wrapper.py:267](../../../packages/haywire-core/src/haywire/core/node/node_wrapper.py#L267)). This is the *same* path `load_from_dict` uses for a `.haywire` file whose library is missing. **Paste therefore does NOT pre-validate registry_keys** — it relies on this placeholder behavior, identical to file load.
- **Edge id generator:** `generate_edge_uuid(outlet_node_id, outlet_pin_id, inlet_node_id, inlet_pin_id)` — [utils.py:29](../../../packages/haywire-core/src/haywire/ui/utils.py#L29). Edge IDs derive purely from endpoints, so remapping endpoints regenerates the id naturally.
- **Edge restoration nuance:** `create_edge_wrapper` rebuilds the adapter chain fresh and defaults `is_lazy` off — [base.py:484](../../../packages/haywire-core/src/haywire/core/graph/base.py#L484). To preserve a copied edge's `is_lazy` and adapter chain, the paste edge path must mirror `load_from_dict` (construct `EdgeWrapper(...)` with `lazy=`, `build()`, then `_check_chain_for_changes(chain)`) — [base.py:959-981](../../../packages/haywire-core/src/haywire/core/graph/base.py#L959-L981).
- **Node id generator:** `graph.generate_unique_node_id(prefix="node")` — [base.py:242](../../../packages/haywire-core/src/haywire/core/graph/base.py#L242).
- **Editor public idiom:** build an action, call `self.history_manager.add_action(action)` — e.g. `create_wrapper` at [editor.py:51](../../../packages/haywire-core/src/haywire/core/graph/editor.py#L51). Paste must use this path — NOT the private `_notify_change`.
- **Vue/async constraint:** the canvas event dispatch chain (`canvas.py:_handle_canvas_event` → manager `_handle_canvas_event` → `handler(event)`) is **synchronous** and does not await coroutines — [canvas.py:51](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.py#L51), [graph_canvas_manager.py:145](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py#L145). Per [.insights/feedback_nicegui_async.md](../../../.insights/feedback_nicegui_async.md), you must NOT `asyncio.ensure_future()` an async clipboard read (empty slot stack crashes `ui.notify`). **Therefore the OS-clipboard read happens in Vue**, not Python — Vue reads `navigator.clipboard.readText()` and ships the text on the paste event.
- **Vue event creators are generated:** `EventCreators.createUserPasteClipboard(canvasX, canvasY, sessionId)` lives in [generated/graph_events.js:227](../../../packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js#L227), generated by [generators.py](../../../packages/haywire-core/src/haywire/ui/components/graph/generators.py) from the `@graph_event`-decorated dataclasses in [event_definitions.py](../../../packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py). Adding a field to `UserPasteClipboardEvent` requires regenerating the JS.

## Format contract (the clipboard payload)

A single JSON object written to the OS clipboard and mirrored in `ClipboardData`:

```json
{
  "haywire_clipboard": true,
  "format_version": 1,
  "source": { "session_id": "ab12cd34", "timestamp": 1717200000.0 },
  "bounding_box": { "min_x": 100.0, "min_y": 200.0, "max_x": 300.0, "max_y": 250.0 },
  "nodes": {
    "node_abc": { "node_id": "node_abc", "registry_key": "core.math.add", "position": [100.0, 200.0], "node_data": {} }
  },
  "edges": {
    "edge::out@node_abc>>in@node_def": { "source_node_id": "node_abc", "outlet_port_id": "out", "sink_node_id": "node_def", "inlet_port_id": "in", "edge_type": "data", "chain_adapter_keys": [], "is_lazy": false }
  }
}
```

- `haywire_clipboard` + `format_version` are the discriminator: paste ignores OS-clipboard text lacking these.
- **Both-endpoints rule:** an edge is included iff its `source_node_id` AND `sink_node_id` are both in the copied node set.
- `node_data` rides on existing `.haywire`-load tolerance for schema drift AND for missing node classes (unknown `registry_key` → placeholder error node carrying the data). Out of scope to *migrate* drifted data; in scope to tolerate it.

## File map

| File | Responsibility | Change |
|------|----------------|--------|
| `packages/haywire-core/src/haywire/core/graph/clipboard.py` | **New.** Pure functions: `build_clipboard_payload(graph, node_ids, edge_ids, session_id) -> dict`, `is_haywire_payload(obj) -> bool`, `CLIPBOARD_FORMAT_VERSION`. No NiceGUI, no I/O. | Create |
| `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py` | Extend `AddNodeAction` with optional `node_data`; implement `PasteClipboardAction`; revise `ClipboardData` to hold the payload dict. | Modify |
| `packages/haywire-core/src/haywire/core/graph/base.py` | `create_node_wrapper` gains optional `node_data` passed to `wrapper.build(...)`. | Modify |
| `packages/haywire-core/src/haywire/core/graph/editor.py` | New public `paste_clipboard(payload, paste_x, paste_y) -> bool` (mirrors `create_wrapper`). | Modify |
| `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` | Add `clipboardText: str = ""` field to `UserPasteClipboardEvent`. | Modify |
| `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js` | Regenerated from the above (run the generator). | Regenerate |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` | On paste trigger, `await navigator.clipboard.readText()` and pass as `clipboardText`. | Modify |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py` | Upgrade `process_copy_selection` (build slice + write OS clipboard) and implement `process_paste_clipboard` (parse text / pick newer / validate / call `editor.paste_clipboard`). | Modify |
| `tests/core/test_graph/test_clipboard_payload.py` | **New.** Unit tests for `clipboard.py`. | Create |
| `tests/core/test_undo/test_paste_action.py` | **New.** Unit tests for extended `AddNodeAction` + `PasteClipboardAction`. | Create |
| `tests/ui/test_canvas_handlers/test_selection_handlers.py` | Extend with copy-slice + paste handler tests. | Modify |

---

### Task 1: Pure clipboard-payload builder

**Files:**
- Create: `packages/haywire-core/src/haywire/core/graph/clipboard.py`
- Test: `tests/core/test_graph/test_clipboard_payload.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_graph/test_clipboard_payload.py
"""Unit tests for the pure clipboard-payload builder."""
import haywire.core.graph.editor  # noqa: F401 — import first (circular-import guard, see CLAUDE.md)

import pytest
from unittest.mock import MagicMock

from haywire.core.graph.clipboard import (
    build_clipboard_payload,
    is_haywire_payload,
    CLIPBOARD_FORMAT_VERSION,
)

pytestmark = pytest.mark.unit


def _fake_graph():
    """A graph with two nodes (n1, n2) and one edge n1->n2, plus a dangling edge n2->n3."""
    g = MagicMock()

    def node_wrapper(node_id):
        w = MagicMock()
        w.serialize.return_value = {
            "node_id": node_id,
            "registry_key": f"key.{node_id}",
            "position": [100.0 if node_id == "n1" else 300.0, 200.0],
            "node_data": {},
        }
        return w

    g.get_node_wrapper.side_effect = node_wrapper

    edge_in = MagicMock()
    edge_in.edge.to_dict.return_value = {
        "source_node_id": "n1", "outlet_port_id": "o", "sink_node_id": "n2",
        "inlet_port_id": "i", "edge_type": "data", "chain_adapter_keys": [], "is_lazy": False,
    }
    edge_out = MagicMock()
    edge_out.edge.to_dict.return_value = {
        "source_node_id": "n2", "outlet_port_id": "o", "sink_node_id": "n3",
        "inlet_port_id": "i", "edge_type": "data", "chain_adapter_keys": [], "is_lazy": False,
    }
    g.get_edge_wrapper.side_effect = lambda eid: {"e_in": edge_in, "e_out": edge_out}.get(eid)
    return g


def test_payload_has_discriminator_and_version():
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], ["e_in"], "sess123")
    assert payload["haywire_clipboard"] is True
    assert payload["format_version"] == CLIPBOARD_FORMAT_VERSION
    assert payload["source"]["session_id"] == "sess123"
    assert "timestamp" in payload["source"]


def test_payload_serializes_selected_nodes():
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], [], "s")
    assert set(payload["nodes"].keys()) == {"n1", "n2"}
    assert payload["nodes"]["n1"]["registry_key"] == "key.n1"


def test_both_endpoints_rule_drops_boundary_crossing_edges():
    # e_out (n2->n3) must be dropped because n3 is not in the selection.
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], ["e_in", "e_out"], "s")
    assert list(payload["edges"].keys()) == ["e_in"]


def test_bounding_box_spans_selected_node_positions():
    payload = build_clipboard_payload(_fake_graph(), ["n1", "n2"], [], "s")
    bb = payload["bounding_box"]
    assert bb == {"min_x": 100.0, "min_y": 200.0, "max_x": 300.0, "max_y": 200.0}


def test_is_haywire_payload_accepts_valid_rejects_other():
    payload = build_clipboard_payload(_fake_graph(), ["n1"], [], "s")
    assert is_haywire_payload(payload) is True
    assert is_haywire_payload({"foo": "bar"}) is False
    assert is_haywire_payload("plain text") is False
    assert is_haywire_payload({"haywire_clipboard": True, "format_version": 9999}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_graph/test_clipboard_payload.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.core.graph.clipboard'`.

- [ ] **Step 3: Write minimal implementation**

```python
# packages/haywire-core/src/haywire/core/graph/clipboard.py
"""
Pure clipboard-payload builder for graph copy/paste.

This module is intentionally free of NiceGUI and I/O: it turns a selection of
nodes/edges into a serializable dict (the *clipboard payload*) and validates
that an arbitrary object is a haywire payload. Transport (OS clipboard) and
mutation (PasteClipboardAction) live elsewhere.

Payload shape — see docs/superpowers/plans/2026-06-01-node-copy-paste.md.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseGraph

CLIPBOARD_FORMAT_VERSION = 1


def build_clipboard_payload(
    graph: "BaseGraph",
    node_ids: List[str],
    edge_ids: List[str],
    session_id: str,
) -> Dict[str, Any]:
    """Serialize a slice of ``graph`` (selected nodes + edges) into a payload.

    Only edges whose *both* endpoints are in ``node_ids`` are included
    (the both-endpoints rule); boundary-crossing edges are dropped so a
    paste is always self-consistent.
    """
    selected = set(node_ids)

    nodes: Dict[str, Any] = {}
    positions: list[tuple[float, float]] = []
    for node_id in node_ids:
        wrapper = graph.get_node_wrapper(node_id)
        if wrapper is None:
            continue
        serialized = wrapper.serialize(include_data=True)
        nodes[node_id] = serialized
        pos = serialized.get("position") or [0.0, 0.0]
        positions.append((float(pos[0]), float(pos[1])))

    edges: Dict[str, Any] = {}
    for edge_id in edge_ids:
        wrapper = graph.get_edge_wrapper(edge_id)
        if wrapper is None:
            continue
        edge_dict = wrapper.edge.to_dict()
        if edge_dict["source_node_id"] in selected and edge_dict["sink_node_id"] in selected:
            edges[edge_id] = edge_dict

    if positions:
        bounding_box = {
            "min_x": min(p[0] for p in positions),
            "min_y": min(p[1] for p in positions),
            "max_x": max(p[0] for p in positions),
            "max_y": max(p[1] for p in positions),
        }
    else:
        bounding_box = {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0}

    return {
        "haywire_clipboard": True,
        "format_version": CLIPBOARD_FORMAT_VERSION,
        "source": {"session_id": session_id, "timestamp": time.time()},
        "bounding_box": bounding_box,
        "nodes": nodes,
        "edges": edges,
    }


def is_haywire_payload(obj: Any) -> bool:
    """True iff ``obj`` is a clipboard payload this version can paste."""
    return (
        isinstance(obj, dict)
        and obj.get("haywire_clipboard") is True
        and obj.get("format_version") == CLIPBOARD_FORMAT_VERSION
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_graph/test_clipboard_payload.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/clipboard.py tests/core/test_graph/test_clipboard_payload.py
git commit -m "feat(graph): pure clipboard-payload builder with both-endpoints rule

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `create_node_wrapper` accepts `node_data`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/base.py:256` (`create_node_wrapper`)
- Test: `tests/core/test_undo/test_paste_action.py` (created here; grows in Tasks 3–4)

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_undo/test_paste_action.py
"""Unit tests for node_data-carrying creation and the paste action."""
import haywire.core.graph.editor  # noqa: F401 — import first (circular-import guard)

import pytest

from haywire.core.graph.base import BaseGraph

pytestmark = pytest.mark.unit


def test_create_node_wrapper_passes_node_data_to_build(monkeypatch):
    captured = {}
    g = BaseGraph()

    class _FakeWrapper:
        def __init__(self, *a, **k):
            self._node_id = k.get("node_id", "node_x")
        def build(self, node_info=None):
            captured["node_info"] = node_info

    # Patch the wrapper class used inside create_node_wrapper and the add step.
    import haywire.core.graph.base as base_mod
    monkeypatch.setattr(base_mod, "NodeWrapper", _FakeWrapper, raising=False)
    monkeypatch.setattr(g, "add_node_wrapper", lambda w: w)

    g.create_node_wrapper("some.key", position=(0, 0), node_data={"hello": "world"})
    assert captured["node_info"] == {"hello": "world"}
```

> NOTE: If `create_node_wrapper` imports `NodeWrapper` locally inside the method (it does — `from ..node.node_wrapper import NodeWrapper`), patch the source symbol instead:
> `monkeypatch.setattr("haywire.core.node.node_wrapper.NodeWrapper", _FakeWrapper)`.
> Check the actual import site in [base.py:256-300](../../../packages/haywire-core/src/haywire/core/graph/base.py#L256) and patch whichever name the method resolves at call time.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -v`
Expected: FAIL — `TypeError: create_node_wrapper() got an unexpected keyword argument 'node_data'`.

- [ ] **Step 3: Write minimal implementation**

Open [base.py:256](../../../packages/haywire-core/src/haywire/core/graph/base.py#L256). Change the signature and thread `node_data` into the existing `wrapper.build(...)` call (the method already calls `build`; pass `node_data` through). Mirror the `load_from_dict` call `wrapper.build(wrapper_data.get("node_data", {}))`.

```python
def create_node_wrapper(
    self,
    registry_key: str,
    position: Tuple[float, float] = (3750, 3750),
    node_data: Optional[Dict[str, Any]] = None,
) -> Optional["NodeWrapper"]:
    # ... existing body ...
    # at the build call (currently wrapper.build() / wrapper.build({})):
    wrapper.build(node_data or {})
    # ... existing add_node_wrapper + return ...
```

Read the current body first and make the minimal edit — only the signature plus the single `build(...)` argument. Do not restructure.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/base.py tests/core/test_undo/test_paste_action.py
git commit -m "feat(graph): create_node_wrapper accepts optional node_data

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Extend `AddNodeAction` with `node_data`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:17` (`AddNodeAction`)
- Test: `tests/core/test_undo/test_paste_action.py`

- [ ] **Step 1: Write the failing test (append to the file)**

```python
def test_add_node_action_forwards_node_data(monkeypatch):
    from haywire.core.undo.actions.graph_actions import AddNodeAction

    seen = {}

    class _G:
        def create_node_wrapper(self, registry_key, position, node_data=None):
            seen["node_data"] = node_data
            return object()

    action = AddNodeAction(graph=_G(), registry_key="k", position=(0, 0), node_data={"a": 1})
    action._execute_impl()
    assert seen["node_data"] == {"a": 1}


def test_add_node_action_default_node_data_is_none(monkeypatch):
    from haywire.core.undo.actions.graph_actions import AddNodeAction

    seen = {}

    class _G:
        def create_node_wrapper(self, registry_key, position, node_data=None):
            seen["node_data"] = node_data
            return object()

    action = AddNodeAction(graph=_G(), registry_key="k", position=(0, 0))
    action._execute_impl()
    assert seen["node_data"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -k add_node_action -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'node_data'`.

- [ ] **Step 3: Write minimal implementation**

In [graph_actions.py:17](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py#L17), add the kwarg and store it; pass it on first execution only (redo re-adds the existing wrapper, which already carries its data):

```python
def __init__(
    self,
    graph: BaseGraph,
    registry_key: str,
    position: Tuple[float, float] = (3750, 3750),
    description: Optional[str] = None,
    node_data: Optional[Dict[str, Any]] = None,
):
    super().__init__(description or f"Add node '{registry_key}'")
    self.graph = graph
    self.registry_key = registry_key
    self.position = position
    self.node_data = node_data
    self.wrapper: "NodeWrapper | None" = None
    self.undo_wrapper: "NodeWrapper | None" = None

def _execute_impl(self) -> None:
    if self.wrapper is None:
        self.wrapper = self.graph.create_node_wrapper(
            registry_key=self.registry_key,
            position=self.position,
            node_data=self.node_data,
        )
    else:
        self.wrapper = self.graph.add_node_wrapper(self.wrapper)
    self.undo_wrapper = None
    if not self.wrapper:
        raise RuntimeError(f"Failed to create node wrapper '{self.registry_key}'")
```

`Dict`/`Any` are already imported at the top of the file (`from typing import Optional, Dict, List, Tuple`). If not, add them.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -k add_node_action -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py tests/core/test_undo/test_paste_action.py
git commit -m "feat(undo): AddNodeAction carries optional node_data for paste

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Implement `PasteClipboardAction` + revise `ClipboardData`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py:399` (`ClipboardData`) and `:427` (`PasteClipboardAction`)
- Test: `tests/core/test_undo/test_paste_action.py`

The action mints new node IDs, remaps edges, offsets positions, and composes child actions. It is a `CompositeAction`, so undo/redo of all children is handled by the base class. **It does NOT validate registry_keys** — unknown types degrade to placeholder error nodes via `create_node_wrapper`/`build`, exactly like `load_from_dict` (see Background).

- [ ] **Step 1: Write the failing test (append)**

```python
def _payload(nodes, edges):
    return {
        "haywire_clipboard": True,
        "format_version": 1,
        "source": {"session_id": "s", "timestamp": 1.0},
        "bounding_box": {"min_x": 0.0, "min_y": 0.0, "max_x": 0.0, "max_y": 0.0},
        "nodes": nodes,
        "edges": edges,
    }


def test_paste_builds_child_actions_with_new_ids_and_remapped_edges(monkeypatch):
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction, AddNodeAction, AddEdgeAction

    payload = _payload(
        nodes={
            "n1": {"node_id": "n1", "registry_key": "k", "position": [100.0, 100.0], "node_data": {"v": 1}},
            "n2": {"node_id": "n2", "registry_key": "k", "position": [200.0, 100.0], "node_data": {"v": 2}},
        },
        edges={
            "e": {"source_node_id": "n1", "outlet_port_id": "o", "sink_node_id": "n2",
                  "inlet_port_id": "i", "edge_type": "data", "chain_adapter_keys": [], "is_lazy": False},
        },
    )

    ids = iter(["new_a", "new_b"])

    class _G:
        # No node_factory needed — paste does not pre-validate registry_keys.
        def generate_unique_node_id(self, prefix="node"):
            return next(ids)

    action = PasteClipboardAction(graph=_G(), payload=payload, paste_x=0.0, paste_y=0.0)

    node_actions = [a for a in action.actions if isinstance(a, AddNodeAction)]
    edge_actions = [a for a in action.actions if isinstance(a, AddEdgeAction)]
    assert {a.registry_key for a in node_actions} == {"k"}
    assert {tuple(a.node_data.items()) for a in node_actions} == {(("v", 1),), (("v", 2),)}
    # edge endpoints remapped to the freshly minted ids
    assert len(edge_actions) == 1
    ea = edge_actions[0]
    assert ea.source_node_id == "new_a"
    assert ea.sink_node_id == "new_b"
    # new node positions exist and were offset by (paste - bbox.min) == (0,0) here
    assert {a.position for a in node_actions} == {(100.0, 100.0), (200.0, 100.0)}


def test_paste_builds_actions_for_unknown_registry_keys_too():
    """Unknown types are NOT rejected — they paste as placeholders (like load_from_dict)."""
    from haywire.core.undo.actions.graph_actions import PasteClipboardAction, AddNodeAction

    payload = _payload(
        nodes={"n1": {"node_id": "n1", "registry_key": "totally.unknown", "position": [0, 0], "node_data": {}}},
        edges={},
    )

    class _G:
        def generate_unique_node_id(self, prefix="node"):
            return "new_x"

    action = PasteClipboardAction(graph=_G(), payload=payload, paste_x=0.0, paste_y=0.0)
    node_actions = [a for a in action.actions if isinstance(a, AddNodeAction)]
    assert [a.registry_key for a in node_actions] == ["totally.unknown"]
```

> NOTE on `CompositeAction.actions`: verify the attribute name holding child actions in [base_action.py](../../../packages/haywire-core/src/haywire/core/undo/base_action.py) (`self.actions` vs `self._actions`). Use whatever the base class exposes; adjust the test accessor to match. Read it before writing Step 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -k paste -v`
Expected: FAIL — `NotImplementedError` (the current scaffold).

- [ ] **Step 3: Write minimal implementation**

First read [base_action.py](../../../packages/haywire-core/src/haywire/core/undo/base_action.py) to learn how `CompositeAction` stores/adds children (e.g. `add_action`, `self.actions`). Then replace the `ClipboardData` body and the `PasteClipboardAction.__init__` NotImplementedError in [graph_actions.py](../../../packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py):

```python
@dataclass
class ClipboardData:
    """Session clipboard mirror: the serialized payload + a copy timestamp.

    Holds the same dict written to the OS clipboard (see
    haywire.core.graph.clipboard.build_clipboard_payload), enabling a
    synchronous, permission-independent copy->paste within one session.
    """
    payload: Dict[str, Any]
    timestamp: float


class PasteClipboardAction(CompositeAction):
    """Undoable composite that pastes a clipboard payload into a graph.

    Mints fresh node IDs, remaps edge endpoints through the old->new map,
    offsets node positions so the selection's top-left lands at
    (paste_x, paste_y), and composes AddNodeAction (carrying node_data) +
    AddEdgeAction children. Undo/redo of all children is inherited from
    CompositeAction.

    Does NOT validate registry_keys: unknown node types degrade to placeholder
    error nodes (carrying their node_data) via create_node_wrapper/build —
    exactly as Graph.load_from_dict handles a file whose library is missing.
    """

    def __init__(
        self,
        graph: BaseGraph,
        payload: Dict[str, Any],
        paste_x: float,
        paste_y: float,
        description: Optional[str] = None,
    ):
        super().__init__(description or "Paste clipboard")
        self.graph = graph

        nodes = payload.get("nodes", {})
        edges = payload.get("edges", {})

        # 1. Compute paste offset from the stored bounding box.
        bbox = payload.get("bounding_box", {"min_x": 0.0, "min_y": 0.0})
        off_x = paste_x - bbox["min_x"]
        off_y = paste_y - bbox["min_y"]

        # 2. Mint new ids + build child AddNodeActions (no registry_key
        #    validation — unknown types become placeholders, like file load).
        id_map: Dict[str, str] = {}
        for old_id, node in nodes.items():
            new_id = graph.generate_unique_node_id()
            id_map[old_id] = new_id
            pos = node.get("position") or [0.0, 0.0]
            self.add_action(
                AddNodeAction(
                    graph=graph,
                    registry_key=node["registry_key"],
                    position=(float(pos[0]) + off_x, float(pos[1]) + off_y),
                    node_data=node.get("node_data") or {},
                )
            )

        # 3. Remap edges through id_map (both endpoints guaranteed present by
        #    the both-endpoints copy rule; skip defensively if not).
        for edge in edges.values():
            src = id_map.get(edge["source_node_id"])
            sink = id_map.get(edge["sink_node_id"])
            if src is None or sink is None:
                continue
            self.add_action(
                AddEdgeAction(
                    graph=graph,
                    source_node_id=src,
                    outlet_pin_id=edge["outlet_port_id"],
                    sink_node_id=sink,
                    inlet_pin_id=edge["inlet_port_id"],
                )
            )
```

> If `CompositeAction` uses a different child-add method name than `add_action`, use the real one (read base_action.py in Step 3 prep). Ensure `Any`/`Dict`/`List` are imported at top of file.
>
> **MIGRATE ALL `ClipboardData` CONSUMERS (the shape changes from `nodes/edges/original_to_new_ids/bounding_box/timestamp/source_session_id` to `payload/timestamp`).** Verified live sites that read the OLD shape and will break:
> - `barn/.../graph_canvas/graph_canvas_manager.py:199-201` `_has_clipboard_content` reads `clipboard.nodes` → change to `len(clipboard.payload.get("nodes", {})) > 0`.
> - `barn/.../handlers/selection.py:113-121` (the stub) reads `clipboard.nodes`/`.edges` → fully replaced in Task 8.
> - `barn/.../panels/context_menu/selection_actions.py:69`, `create_node_panel.py:88`, `barn/haybale-testing/.../test_selection_panels.py:61` only check `clipboard is not None` → **no change needed** (presence check survives).
> - Tests that build/read the old shape: `tests/ui/test_canvas_handlers/test_haybale_context_menu_panels.py:322` (and `:71`), `tests/libraries/test_clipboard_reactive.py:76`, and `tests/ui/test_canvas_handlers/test_selection_handlers.py:149-162` (asserts `.nodes`/`.edges`/`.source_session_id`). Update these to the `payload`/`timestamp` shape (the `test_selection_handlers.py` copy assertions are rewritten in Task 8 Step 1; fix the other two test files here).
>
> After editing, re-run the grep to confirm zero stale readers remain:
> `grep -rn "clipboard\.nodes\|clipboard\.edges\|\.source_session_id\|original_to_new_ids" packages/ barn/ tests/`
>
> **Edge `is_lazy`/adapter-chain note:** `AddEdgeAction` → `create_edge_wrapper` rebuilds the chain fresh and ignores `is_lazy` (see Background). For v1 this is acceptable — pasted edges relink and re-derive adapters; lazy flag resets to default. If preserving `is_lazy`/chain is required, that is a *follow-up* (extend `AddEdgeAction` like we did `AddNodeAction`), explicitly NOT in this plan's scope.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -k paste -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py tests/core/test_undo/test_paste_action.py
git commit -m "feat(undo): implement PasteClipboardAction with id-remap (placeholder-tolerant)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `Editor.paste_clipboard` public method

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/editor.py` (add method near `create_wrapper`)
- Test: `tests/core/test_undo/test_paste_action.py`

- [ ] **Step 1: Write the failing test (append)**

```python
def test_editor_paste_clipboard_adds_action_and_returns_true(monkeypatch):
    from haywire.core.graph.editor import Editor
    from haywire.core.undo.actions import graph_actions

    added = {}

    class _HM:
        def add_action(self, action):
            added["action"] = action

    payload = _payload(
        nodes={"n1": {"node_id": "n1", "registry_key": "k", "position": [0, 0], "node_data": {}}},
        edges={},
    )

    ed = Editor.__new__(Editor)  # bypass __init__ wiring
    ed.graph = type("G", (), {
        "generate_unique_node_id": lambda self, prefix="node": "new_x",
    })()
    ed.history_manager = _HM()

    assert ed.paste_clipboard(payload, 10.0, 20.0) is True
    assert isinstance(added["action"], graph_actions.PasteClipboardAction)


def test_editor_paste_clipboard_pastes_unknown_types_too():
    """Unknown registry_keys do NOT block paste — they degrade to placeholders."""
    from haywire.core.graph.editor import Editor

    payload = _payload(
        nodes={"n1": {"node_id": "n1", "registry_key": "unknown", "position": [0, 0], "node_data": {}}},
        edges={},
    )
    added = {}
    ed = Editor.__new__(Editor)
    ed.graph = type("G", (), {"generate_unique_node_id": lambda self, prefix="node": "new_x"})()
    ed.history_manager = type("HM", (), {"add_action": lambda self, a: added.setdefault("a", a)})()

    assert ed.paste_clipboard(payload, 0.0, 0.0) is True
    assert "a" in added
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -k editor_paste -v`
Expected: FAIL — `AttributeError: 'Editor' object has no attribute 'paste_clipboard'`.

- [ ] **Step 3: Write minimal implementation**

Add to [editor.py](../../../packages/haywire-core/src/haywire/core/graph/editor.py), mirroring `create_wrapper` ([editor.py:51](../../../packages/haywire-core/src/haywire/core/graph/editor.py#L51)). Import `PasteClipboardAction` at top with the other action imports.

```python
def paste_clipboard(self, payload: Dict[str, Any], paste_x: float, paste_y: float) -> bool:
    """Paste a clipboard payload at (paste_x, paste_y) as one undoable action.

    Unknown node types in the payload are NOT rejected — they paste as
    placeholder error nodes (like loading a .haywire file whose library is
    missing). Returns False only on an unexpected error.
    """
    try:
        action = PasteClipboardAction(
            graph=self.graph, payload=payload, paste_x=paste_x, paste_y=paste_y
        )
        self.history_manager.add_action(action)
        logger.info(f"Pasted {len(payload.get('nodes', {}))} nodes at ({paste_x}, {paste_y})")
        return True
    except Exception as e:
        logger.error(f"Error pasting clipboard: {e}")
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_undo/test_paste_action.py -k editor_paste -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/editor.py tests/core/test_undo/test_paste_action.py
git commit -m "feat(graph): Editor.paste_clipboard public entrypoint

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Add `clipboardText` to the paste event + regenerate JS

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py:256` (`UserPasteClipboardEvent`)
- Regenerate: `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/ui/test_canvas_handlers/test_selection_handlers.py imports + a new test
def test_paste_event_carries_clipboard_text():
    from haywire.ui.components.graph.event_definitions import UserPasteClipboardEvent
    e = UserPasteClipboardEvent(canvasX=1.0, canvasY=2.0, clipboardText='{"x":1}')
    assert e.clipboardText == '{"x":1}'

    # default stays empty for backward compat
    e2 = UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0)
    assert e2.clipboardText == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -k clipboard_text -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'clipboardText'`.

- [ ] **Step 3: Write minimal implementation**

In [event_definitions.py:258](../../../packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py#L258):

```python
@graph_event("userPasteClipboard", category="user", description="Paste clipboard contents")
@dataclass
class UserPasteClipboardEvent(BaseGraphEvent):
    canvasX: float
    canvasY: float
    # OS-clipboard text read in the Vue layer (avoids a NiceGUI async trap on
    # the synchronous Python dispatcher). Empty when the in-process mirror
    # should be used instead. See docs/superpowers/plans/2026-06-01-node-copy-paste.md.
    clipboardText: str = ""
```

Then regenerate the JS. Find the generator entrypoint:

Run: `uv run python -m haywire.ui.components.graph.generators` (or the documented codegen command — check [generators.py:171](../../../packages/haywire-core/src/haywire/ui/components/graph/generators.py#L171) `main()` and the project's codegen convention; there may be a `scripts/` wrapper).
Expected: `graph_events.js` now contains `clipboardText` in `createUserPasteClipboard(...)` and its validator.

Verify: `git diff packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js` shows `clipboardText` added to the creator signature and event body.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -k clipboard_text -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js tests/ui/test_canvas_handlers/test_selection_handlers.py
git commit -m "feat(graph-events): UserPasteClipboardEvent carries clipboardText

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Menu→Vue→Python clipboard round-trip

**DESIGN (revised during execution — supersedes the original Task 7).** Paste stays **menu-only** (no keyboard shortcut). The OS clipboard can only be read async in the browser, and the Python paste menu button can't await it (`hui.button` wires clicks as `lambda: fn()`, never awaiting the coroutine — changing that is a shared-widget change we won't make). So the read is a **round-trip through the existing sync-event machinery**:

1. **Paste menu click** (Python, `paste_at_click` in `context_menu.py`) emits a NEW Python→Vue sync event `SyncRequestClipboardPasteEvent(canvasX, canvasY)` via `emit_sync_event` (instead of emitting `UserPasteClipboardEvent` directly). It already has the canvas position in `self._open_ctx.canvas_pos`.
2. **canvas.vue** `handleSyncEvent` gets a new `case` that does `await navigator.clipboard.readText()` (async is native in JS — no trap) then emits `UserPasteClipboardEvent(canvasX, canvasY, clipboardText)` back to Python via `emitCanvasEvent`.
3. **Python `process_paste_clipboard`** (Task 8, sync, main thread) receives the event with `clipboardText` populated, parses it, calls `editor.paste_clipboard(...)`. Paste execution + UI repaint happen on the main thread via the validation callback — no async anywhere on the Python side.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py` — add a new sync event `SyncRequestClipboardPasteEvent` (category="sync").
- Regenerate: `packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js`.
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` — new `handleSyncEvent` case + async clipboard read.
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py` — `paste_at_click` emits the sync request instead of `UserPasteClipboardEvent`.

- [ ] **Step 1: Add the sync event**

In [event_definitions.py](../../../packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py), in the SYNC EVENTS section (after the other `Sync*Event` classes, ~line 268+), add:

```python
@graph_event("syncRequestClipboardPaste", category="sync", description="Ask Vue to read the OS clipboard and emit a paste")
@dataclass
class SyncRequestClipboardPasteEvent(BaseGraphEvent):
    canvasX: float
    canvasY: float
```

Then regenerate the JS (verified working command from Task 6 — the `scripts/generate_vue_events.py` wrapper is BROKEN, points at a stale `graph_canvas/` path):

Run: `uv run python -c "from haywire.ui.components.graph.generators import main; main()"`
Verify `git diff` shows `SyncCommands.SYNC_REQUEST_CLIPBOARD_PASTE` (or equivalent constant) added to `graph_events.js`. (Sync events become entries in the `SyncCommands` constant block — confirm the generator emits the constant for category="sync" events.)

- [ ] **Step 2: canvas.vue — handle the sync request, read clipboard, re-emit**

In [canvas.vue](../../../packages/haywire-core/src/haywire/ui/components/graph/canvas.vue), add a `case` to the `handleSyncEvent(syncEvent)` switch (it dispatches on `GraphEvents.SyncCommands.*`):

```javascript
case GraphEvents.SyncCommands.SYNC_REQUEST_CLIPBOARD_PASTE:
    this._handleClipboardPasteRequest(data);
    break;
```

And add the method (near other emit methods). Note `handleSyncEvent` is sync, but it can fire-and-forget an async helper — the helper only reads the clipboard and emits an event (no Vue DOM writes that need the call stack), which is safe in the browser:

```javascript
async _handleClipboardPasteRequest(data) {
    let text = "";
    try {
        text = await navigator.clipboard.readText();
    } catch (err) {
        // Permission denied / unavailable — emit empty text; Python falls
        // back to the in-process mirror.
        console.warn("clipboard.readText() failed; using in-process mirror", err);
    }
    this.emitCanvasEvent(EventCreators.createUserPasteClipboard(data.canvasX, data.canvasY, text));
},
```

> Confirm `createUserPasteClipboard` arg order in the regenerated `graph_events.js` (Task 6 made it `(canvasX, canvasY, clipboardText, sessionId='default')`). Match it.

- [ ] **Step 3: context_menu.py — paste_at_click emits the sync request**

In [context_menu.py](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py), `paste_at_click` currently does `self._emit(UserPasteClipboardEvent(canvasX=x, canvasY=y))`. Change it to emit the sync request via the sync-event channel. The provider has `self._on_emit_sync_event` (used elsewhere, e.g. `SyncEdgeConnectResumeEvent`). Use it; also close the popup (the old `_emit` closed it). Read the current `paste_at_click` and the `_emit`/`_on_emit_sync_event` usage first, then:

```python
def paste_at_click(self) -> None:
    """Ask Vue to read the OS clipboard and emit a paste at the click position."""
    from haywire.ui.components.graph.event_definitions import SyncRequestClipboardPasteEvent

    if self._open_ctx is None or self._open_ctx.canvas_pos is None:
        return
    x, y = self._open_ctx.canvas_pos
    if self._on_emit_sync_event:
        self._on_emit_sync_event(SyncRequestClipboardPasteEvent(canvasX=x, canvasY=y))
    if self._open_popup is not None:
        self._open_popup.close()
```

> Verify `self._on_emit_sync_event` and `self._open_popup` are the right attribute names on the provider (read the class). Match the existing pattern used by `reconnect_active_edge` / the resume-event path.

- [ ] **Step 4: Lint/type-check + targeted tests**

Run:
```sh
uv run ruff check packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py
uv run mypy packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py
```
Then run any context-menu provider tests: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py tests/ui/graph_canvas/test_context_menu_actions.py -v` — these may assert `paste_at_click` behavior; update expectations to the new sync-emit (a context-menu-actions test may have asserted `UserPasteClipboardEvent` was emitted — it should now assert `SyncRequestClipboardPasteEvent` via the sync channel). Read failing tests and fix them to match the new contract.

- [ ] **Step 5: Manual verification**

Run: `uv run haywire`
- Same-session: copy a node, right-click → Paste. Expected: node pastes at the cursor (clipboard text round-trips; if browser denies clipboard, the empty-text fallback uses the mirror and still pastes).
- Cross-process: copy here, open a SECOND `uv run haywire`, right-click → Paste in the second. Expected: node appears (OS clipboard read via the round-trip). NOTE: the Paste menu item is gated by `poll()` on the mirror (`EditState.clipboard is not None`) — in a fresh second process the mirror is empty so the item may be hidden. If so, that gate must be relaxed (Task 8 territory) — flag it; for THIS task, confirm the round-trip mechanism works when the item is reachable.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/event_definitions.py packages/haywire-core/src/haywire/ui/components/graph/generated/graph_events.js packages/haywire-core/src/haywire/ui/components/graph/canvas.vue barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py
git commit -m "feat(canvas): menu->Vue->Python clipboard round-trip for paste

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Copy builds slice + writes OS clipboard; paste handler wired

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py`
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`

- [ ] **Step 1: Write the failing tests (append)**

```python
import json
from unittest.mock import patch
from haywire.ui.components.graph.event_definitions import UserPasteClipboardEvent


def test_copy_stores_serialized_payload_in_mirror(graph, session, edit_state_cls):
    from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
    # graph.get_node_wrapper(...).serialize must return a dict
    graph.get_node_wrapper.return_value.serialize.return_value = {
        "node_id": "n1", "registry_key": "k", "position": [10.0, 20.0], "node_data": {}
    }
    h = SelectionHandlers(graph=graph, editor=MagicMock(), session_id="sess", session=session)

    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.run_javascript") as rj:
        h.process_copy_selection(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))

    clip = session.context.data[edit_state_cls].clipboard
    assert clip is not None
    assert clip.payload["haywire_clipboard"] is True
    assert "n1" in clip.payload["nodes"]
    # OS clipboard write attempted
    assert rj.called
    assert "navigator.clipboard.writeText" in rj.call_args[0][0]


def test_paste_uses_event_text_when_valid(graph, session, edit_state_cls):
    from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
    editor = MagicMock()
    editor.paste_clipboard.return_value = True
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)

    payload = {"haywire_clipboard": True, "format_version": 1,
               "source": {"session_id": "x", "timestamp": 99.0},
               "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
               "nodes": {}, "edges": {}}
    h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=5.0, canvasY=6.0, clipboardText=json.dumps(payload)))

    editor.paste_clipboard.assert_called_once()
    args = editor.paste_clipboard.call_args[0]
    assert args[0]["source"]["timestamp"] == 99.0
    assert (args[1], args[2]) == (5.0, 6.0)


def test_paste_falls_back_to_mirror_when_text_empty(graph, session, edit_state_cls):
    from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
    from haywire.core.undo.actions.graph_actions import ClipboardData
    editor = MagicMock()
    editor.paste_clipboard.return_value = True
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)

    mirror_payload = {"haywire_clipboard": True, "format_version": 1,
                      "source": {"session_id": "x", "timestamp": 1.0},
                      "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
                      "nodes": {}, "edges": {}}
    session.context.data[edit_state_cls].clipboard = ClipboardData(payload=mirror_payload, timestamp=1.0)

    h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=""))
    editor.paste_clipboard.assert_called_once_with(mirror_payload, 0.0, 0.0)


def test_paste_notifies_when_nothing_to_paste(graph, session, edit_state_cls):
    from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
    editor = MagicMock()
    h = SelectionHandlers(graph=graph, editor=editor, session_id="sess", session=session)

    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify") as notify:
        h.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=""))
    editor.paste_clipboard.assert_not_called()
    notify.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -k "copy_stores or paste_uses or paste_falls or nothing_to_paste" -v`
Expected: FAIL — copy still stores ID-based `ClipboardData(nodes=..., edges=...)`; paste is a stub.

- [ ] **Step 3: Write minimal implementation**

Rewrite the two handlers in [selection.py](../../../barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py). Replace imports of `ClipboardData` usage and add the new ones. `_calculate_selection_bounds` is no longer needed by copy (the payload builder computes the bbox); leave it or remove if unused.

```python
import json
# ... existing imports ...
from haywire.core.graph.clipboard import build_clipboard_payload, is_haywire_payload
from haywire.core.undo.actions.graph_actions import ClipboardData

# ... inside SelectionHandlers ...

@handles_event(UserCopySelectedEvent)
def process_copy_selection(self, event: UserCopySelectedEvent):
    """Serialize the selection to a payload; mirror it and write the OS clipboard."""
    logger.info(f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedEdges)} connections")
    if self._session is None:
        logger.warning("Copy ignored: no session bound to handler")
        return
    if not event.selectedNodes:
        return
    try:
        payload = build_clipboard_payload(
            self.graph, event.selectedNodes, event.selectedEdges, self.session_id
        )
        self._session.context.data[EditState].clipboard = ClipboardData(
            payload=payload, timestamp=payload["source"]["timestamp"]
        )
        # Write to the OS clipboard as JSON text (cross-process export).
        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(json.dumps(payload))})")
    except Exception as e:
        logger.error(f"❌ Error during copy operation: {e}")
        ui.notify(f"Copy failed: {e}", type="negative")
        traceback.print_exc()

@handles_event(UserPasteClipboardEvent)
def process_paste_clipboard(self, event: UserPasteClipboardEvent):
    """Paste: pick the newer of OS-clipboard text vs in-process mirror, then paste."""
    if self._session is None:
        logger.warning("Paste ignored: no session bound to handler")
        return

    os_payload = None
    if event.clipboardText:
        try:
            parsed = json.loads(event.clipboardText)
            if is_haywire_payload(parsed):
                os_payload = parsed
        except (ValueError, TypeError):
            os_payload = None

    mirror = self._session.context.data[EditState].clipboard
    mirror_payload = mirror.payload if mirror is not None else None

    # Arbitrate by timestamp: OS clipboard wins if newer (or mirror absent).
    chosen = None
    if os_payload is not None and mirror_payload is not None:
        os_ts = os_payload["source"]["timestamp"]
        chosen = os_payload if os_ts >= mirror.timestamp else mirror_payload
    else:
        chosen = os_payload or mirror_payload

    if chosen is None:
        ui.notify("Nothing to paste", type="warning")
        return

    ok = self.editor.paste_clipboard(chosen, event.canvasX, event.canvasY)
    if ok:
        n = len(chosen.get("nodes", {}))
        ui.notify(f"Pasted {n} node{'s' if n != 1 else ''}", type="positive")
    else:
        # Unknown node types do NOT cause failure (they paste as placeholders);
        # False here means an unexpected error.
        ui.notify("Paste failed", type="negative")
```

> `json.dumps(json.dumps(payload))` double-encodes: the inner dumps makes the JSON string; the outer makes it a safe JS string literal for `writeText(...)`. This matches the existing idiom at [elements.py:969](../../../packages/haywire-core/src/haywire/ui/elements/elements.py#L969).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_canvas_handlers/test_selection_handlers.py -v`
Expected: PASS (existing tests + 4 new).

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py tests/ui/test_canvas_handlers/test_selection_handlers.py
git commit -m "feat(canvas): copy serializes slice to OS clipboard; paste wired to editor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Full-suite green + manual end-to-end + glossary cross-check

**Files:** none (verification task)

- [ ] **Step 1: Lint + type-check touched areas**

Run:
```sh
uv run ruff check packages/haywire-core/src/haywire/core/graph/clipboard.py packages/haywire-core/src/haywire/core/undo/actions/graph_actions.py packages/haywire-core/src/haywire/core/graph/editor.py packages/haywire-core/src/haywire/core/graph/base.py barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/
```
Expected: no NEW errors (baseline is clean per CLAUDE.md; anything new is yours to fix).

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -m "not integration"`
Expected: all pass. Then `uv run pytest -m integration` if the touched areas have integration coverage.

- [ ] **Step 3: Manual end-to-end in the running app**

Run: `uv run haywire`
- Select 2 nodes connected by an edge + a dangling edge to a third (unselected) node. Copy. Paste at a new spot.
  - Expected: 2 new nodes with fresh IDs at the cursor offset, the internal edge recreated, the dangling edge NOT recreated (both-endpoints rule).
- Undo once. Expected: the entire paste reverts in one step (CompositeAction).
- Redo. Expected: paste reappears.
- Copy, then open a second `uv run haywire` process, paste (via whatever paste affordance Task 7 wired). Expected: nodes appear (cross-process via OS clipboard).
- Paste with an empty/foreign OS clipboard and an empty mirror. Expected: "Nothing to paste" notify, no crash.
- Copy a node from a library, disable/uninstall that library, then paste. Expected: the node pastes as a **placeholder error node** with a warning (NOT a failed/blocked paste) — identical to opening a `.haywire` file whose library is missing.

- [ ] **Step 4: Glossary cross-check**

Confirm [docs/reference/glossary.md](../../reference/glossary.md) "Clipboard & Copy/Paste" section terms still match the code: `Clipboard payload`, `Clipboard slice`, `Both-endpoints rule`, `Clipboard mirror`, `ID remapping`, `PasteClipboardAction`. The glossary says the mirror is `ClipboardData`; verify the revised `ClipboardData` (now `payload` + `timestamp`) is still accurately described, and update the glossary line if the field description drifted.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "test: full-suite green for node copy/paste; glossary cross-check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review notes (for the implementer)

- **Spec coverage:** transport=OS clipboard JSON (Tasks 6–8); payload=slice+bbox+version+source w/ both-endpoints (Task 1); extend AddNodeAction (Task 3); PasteClipboardAction w/ id-remap, undoable, **placeholder-tolerant — no registry_key validation** (Task 4); Editor.paste_clipboard public, no `_notify_change` (Task 5); handlers in SelectionHandlers w/ mirror + timestamp-arbitrated OS fallback (Task 8). All covered.
- **Design correction (overrides inquisition):** the original design called for all-or-nothing registry_key validation. **Removed.** `NodeFactory.get_node` falls back to a placeholder error node for unknown keys (factory.py:99), so paste tolerates missing node classes exactly like `load_from_dict` — paste *is* "load a slice of a graph." No `PasteValidationError`, no pre-check.
- **Out of scope (do NOT implement):** graph variables in payload; best-effort partial paste of *valid* nodes (N/A — all nodes paste, unknown ones as placeholders); cross-machine version migration; `DuplicateNodeAction`; keyboard shortcuts; process-level shared mirror; preserving edge `is_lazy`/adapter-chain through paste (fresh-relink v1 decision — noted as follow-up in Task 4).
- **Type consistency check:** `ClipboardData` is `{payload: dict, timestamp: float}` everywhere after Task 4 (old `nodes/edges/original_to_new_ids/bounding_box/source_session_id` shape is fully replaced — grep for stale constructions in `barn/` and tests). `PasteClipboardAction(graph, payload, paste_x, paste_y)` signature is identical in Tasks 4/5/8. `build_clipboard_payload(graph, node_ids, edge_ids, session_id)` identical in Tasks 1/8. `create_node_wrapper(..., node_data=)` identical in Tasks 2/3. `paste_clipboard(payload, paste_x, paste_y)` identical in Tasks 5/8.
- **Grep-for-callers reminder (CLAUDE.md):** before Task 4, `grep -rn "ClipboardData(\|clipboard\.nodes\|clipboard\.edges\|\.source_session_id\|original_to_new_ids" packages/ barn/ tests/`. Verified live sites (migrated in Task 4's "MIGRATE ALL CONSUMERS" note + Task 8): `graph_canvas_manager.py:199-201` (`_has_clipboard_content` — reads `.nodes`, MUST change), `selection.py` (rewritten Task 8), `tests/ui/test_canvas_handlers/test_haybale_context_menu_panels.py`, `tests/libraries/test_clipboard_reactive.py`, `tests/ui/test_canvas_handlers/test_selection_handlers.py`. Presence-only checks (`selection_actions.py:69`, `create_node_panel.py:88`, `test_selection_panels.py:61`) need NO change. After Task 4 the grep for `.nodes`/`.edges`/`.source_session_id`/`original_to_new_ids` on clipboard must return nothing.
