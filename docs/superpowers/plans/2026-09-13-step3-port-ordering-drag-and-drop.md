# Port Ordering Drag And Drop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the graph user reorder a node's ports by dragging them in the Properties → Ports panel, with the new order persisted.

**Architecture:** Ordering already exists end to end — `DataPort.order` is the sort key for `_iter_ports()`, `to_dict()` persists any non-default field, and the load path bypasses `add()` precisely so a stored order survives. What is missing is a way for the user to change it. This plan adds SortableJS drag (shipped with NiceGUI as `make_sortable`) to the Ports panel, one sortable per direction section and one per fold, so an illegal cross-lane drop is inexpressible rather than validated away.

**Tech Stack:** Python 3.12, NiceGUI 3.13 (`make_sortable`, `SortableEventArguments`), pytest.

## Global Constraints

- **Depends on:** Steps 1 and 2 (`2026-09-13-step1-fold-depth-indentation.md`, `2026-09-13-step2-fold-replaces-group-and-section.md`) must land first. The panel mirrors the fold hierarchy, and `get_visible_ports()` loses its `include_sections` argument there.
- NiceGUI floor is already `>=3.12.1` (`make_sortable` arrived in 3.11.0); 3.13.0 is installed. No dependency change.
- Line length 109 (`ruff`). CI runs BOTH `ruff check .` and `ruff format --check .`.
- **Reordering is NOT undoable.** A bad drop is repaired by dragging back.
- **Do not publish `GraphDataMutated` yourself** — one arrives anyway, and every session is reached.

  **Why other sessions update.** `HaystackState` is an `AppState`: "one instance … shared across every browser session" (`packages/haywire-core/src/haywire/core/state/base.py:59-66`), keyed "one entry per file path" (`haystack_state.py:27`). So two sessions on one file share a single `GraphEntry` and a single `BaseGraph`. `mark_node_dirty` therefore reaches the one graph every session's canvas subscribes to (`graph_canvas_manager.py:126`), and `refresh_node_visual` repaints the card in all of them — the same path a pin deletion already uses today. (`graph_id` differing per tab, `glossary.md:384`, is about opening a file as two separate *entries*, not about two sessions viewing one.)
 `HaystackState._on_entry_validation` (`barn/haybale-haystack/haybale_haystack/state/haystack_state.py:178-192`) marks the entry unsaved and broadcasts `GraphDataMutated` for any validation result that is **not** entirely visual-only. `NODE_LAYOUT_CHANGED` is deliberately not visual-only — that is what makes the reorder persist — so the broadcast fires, and the panel (`redraw_on=(…, GraphDataMutated, …)`, `node_ports.py:41`) rebuilds shortly after the drop. **Verify the interaction in Task 6 Step 1 before assuming it is benign**; the drop has already committed to the model by then, so the rebuild should render the new order rather than fight the gesture. If it visibly flickers or reverts, the fix is a suppression flag on the panel for the drop it originated, NOT making the reason visual-only (that would silently stop the reorder being saved).
- Cross-lane drag is prevented **by construction** (per-section sortable `group=` names), never by rejecting a drop.
- `make_sortable` does not support a custom HTML id on the container — setting one breaks its slot synchronisation.

### ⚠️ How to build a test node with real ports

**There is no fixture that builds an inline test node.** `test_node_factory`
does not exist; `node_factory` is a DI `NodeFactory` keyed by *registry key*,
and a `@node` class declared inside a test file is never registered (registration
is a library folder scan, not the decorator). So a `@node` probe class written in
a test module cannot be built and has no ports.

The pattern every existing port-level test uses (see
`tests/core/test_types/test_add_type.py:227-233`):

1. Add the probe node as a real module under
   `barn/haybale-testing/haybale_testing/nodes/testbed/`, decorated with
   `@node(..., menu="testing/testbed")` — copy `dynamic_port_test.py` for shape.
2. In the test, take the `graph_with_library_system` fixture and build it:

```python
def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.reorder_probe import ReorderProbeNode

    wrapper = graph.create_node_wrapper(
        ReorderProbeNode.class_identity.registry_key, position=position
    )
    assert wrapper is not None, "node creation failed"
    return wrapper.node
```

Consequences that change what the tests in this plan look like:

- These are **integration** tests. Mark them `pytestmark = pytest.mark.integration`,
  NOT `pytest.mark.unit`. Run with `uv run pytest -m integration`.
- `reorder_ports` calls `self.wrapper.mark_layout_changed()`, so a probe built
  through `create_node_wrapper` is required anyway — a bare instance has no
  wrapper and no graph.
- The rejig probe needs its reconfiguring method callable from the test, so give
  it a public method (as `dynamic_port_test.py` does) rather than relying on
  `post_init` alone.
- ⚠️ **`tests/studio/test_docs/test_generate.py:31` runs
  `git checkout -- barn/haybale-testing` in its teardown**, deleting untracked
  files there. **Commit each new probe node before running any suite that
  includes that test.**

Tests that only inspect a class, signature, or source text stay unit tests and
need none of this.

## Pre-Flight Baseline

```sh
uv run ruff check barn/haybale-graph-editor/haybale_graph_editor/panels/properties/
uv run mypy packages/haywire-core/src/ barn/haybale-graph-editor/haybale_graph_editor/
uv run pytest tests/ui/panel/ tests/core/test_node/ -q
```

All clean before starting.

## File Structure

| File | Responsibility |
|---|---|
| `packages/haywire-core/src/haywire/core/graph/types.py` | `ChangeReason`. Gains `NODE_LAYOUT_CHANGED`. |
| `packages/haywire-core/src/haywire/core/node/data.py` | Gains `reorder_ports()` — the one place `order` is rewritten. |
| `packages/haywire-core/src/haywire/core/types/port.py` | `adopt_state_from` gains `order`. |
| `packages/haywire-core/src/haywire/core/settings/settings.py` | `Promotion` gains `order`, so a promoted port's order survives regeneration. |
| `packages/haywire-core/src/haywire/core/node/promotion.py` | Threads `order` through `promote_setting` / `regenerate_promoted_ports`. |
| `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py` | Renders fold nesting and wires the sortables. |
| `tests/core/test_node/test_port_reorder.py` | New. The reorder verb, rejig survival, promoted-port persistence. |
| `tests/ui/panel/test_ports_panel_reorder.py` | New. Sortable wiring and drop handling. |

---

### Task 1: `NODE_LAYOUT_CHANGED`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/graph/types.py:9-44` (enum), `:78-102` (`requires_redraw`, `is_visual_only`)
- Test: `tests/core/test_graph/test_change_reason_layout.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ChangeReason.NODE_LAYOUT_CHANGED` — `requires_redraw()` True, `is_visual_only()` False. Task 4 marks nodes dirty with it.

The existing refresh API deliberately excludes this case: `request_node_redraw`
maps to `NODE_REDRAW_REQUESTED`, which `is_visual_only()` returns True for, and
the section is headed "REFRESH REQUESTS (bypass undo history — non-mutating
operations)". A reorder repaints *and* persists, so it needs a reason of its own.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_graph/test_change_reason_layout.py`:

```python
"""NODE_LAYOUT_CHANGED repaints AND persists.

The category `is_visual_only` documents via NODE_MOVED: a move repaints, but
position is persisted as props.posX/posY, so an app layer must still mark the
file unsaved. A port reorder is the same shape — it changes only what the card
draws, and it is saved.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.types import ChangeReason

pytestmark = pytest.mark.unit


def test_layout_changed_exists() -> None:
    assert ChangeReason.NODE_LAYOUT_CHANGED.value == "node_layout_changed"


def test_layout_changed_requires_a_redraw() -> None:
    """Pins move between positions, so the card is rebuilt."""
    assert ChangeReason.NODE_LAYOUT_CHANGED.requires_redraw() is True


def test_layout_changed_is_not_visual_only() -> None:
    """is_visual_only() True would tell the app not to mark the file unsaved."""
    assert ChangeReason.NODE_LAYOUT_CHANGED.is_visual_only() is False


def test_layout_changed_needs_no_reassembly() -> None:
    """The ports are identical; only their order changed."""
    assert ChangeReason.NODE_LAYOUT_CHANGED.requires_graph_reassembly() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_graph/test_change_reason_layout.py -v`
Expected: FAIL with `AttributeError: NODE_LAYOUT_CHANGED`

- [ ] **Step 3: Add the enum member**

In `packages/haywire-core/src/haywire/core/graph/types.py`, after `NODE_MOVED`:

```python
    # Node reason that persists an arrangement without changing structure
    NODE_LAYOUT_CHANGED = "node_layout_changed"
    """A node's persisted arrangement changed — today, its port order.

    Distinct from a ``layout_direction`` change, which reaches the card through
    ``NodeProperties.REDRAW_FIELDS`` as ``NODE_REDRAW_REQUESTED``.
    """
```

Add it to the `redraw_reasons` set in `requires_redraw()` (`types.py:78-88`),
immediately after `ChangeReason.NODE_MOVED,` (line 81):

```python
            ChangeReason.NODE_LAYOUT_CHANGED,
```

Leave `visual_reasons` in `is_visual_only()` untouched — the omission is the
decision.

Extend that method's docstring. **Keep the summary line** (`types.py:92`) —
replace ONLY the second paragraph at `types.py:95-96`, which currently reads
"``NODE_MOVED`` is not visual-only: a move repaints, but position is persisted
as ``props.posX``/``posY``.", with:

```
        mutation for one. ``NODE_MOVED`` and ``NODE_LAYOUT_CHANGED`` are not
        visual-only: both repaint, and both persist — position as
        ``props.posX``/``posY``, port order as ``DataPort.order``.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_graph/test_change_reason_layout.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Verify the canvas handles it**

`visual_layer.py` branches `NODE_ADDED` / `NODE_REMOVED` / `NODE_MOVED`, then
falls through to `elif reason.requires_redraw():` at
`barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/visual_layer.py:151-155`,
which calls `refresh_node_visual(ui_node, reason)`. Verified: an unknown reason
whose `requires_redraw()` is True lands there. Read it once to confirm nothing
has changed, then continue.

Note `get_priority()` (`types.py:122-147`) gives `NODE_LAYOUT_CHANGED` the redraw
priority (60) via `requires_redraw()`, so a `NODE_VALIDATION_REQUESTED` (70)
landing in the same debounce window supersedes it. That is correct — a
revalidation redraws too.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/core/graph/types.py tests/core/test_graph/test_change_reason_layout.py
git commit -m "feat(graph): add NODE_LAYOUT_CHANGED — repaints and persists

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `reorder_ports()` — the one place order is rewritten

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/node/data.py`
- Test: `tests/core/test_node/test_port_reorder.py`

**Interfaces:**
- Consumes: `ChangeReason.NODE_LAYOUT_CHANGED` from Task 1.
- Produces: `NodeData.reorder_ports(self, ordered_ids: list[str]) -> None`. Task 6 calls it from the drop handler.

Siblings are the ports sharing one direction lane and one fold. The caller
supplies the full sibling list in its new order; this method assigns each a new
`order` and marks the node dirty.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_node/test_port_reorder.py`:

```python
"""reorder_ports rewrites DataPort.order for one sibling group."""

from __future__ import annotations

import pytest

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import BaseNode, NodeType, node

# Integration: building a node with real ports needs the library system, and
# reorder_ports() reaches self.wrapper — a bare instance has neither.
pytestmark = pytest.mark.integration


def _make_probe(graph, position=(100.0, 100.0)):
    from haybale_testing.nodes.testbed.reorder_probe import ReorderProbeNode

    wrapper = graph.create_node_wrapper(
        ReorderProbeNode.class_identity.registry_key, position=position
    )
    assert wrapper is not None, "node creation failed"
    return wrapper.node


def test_reorder_assigns_new_order_values(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    probe.reorder_ports(["c", "a", "b"])
    assert [p.id for p in probe.get_visible_ports() if p.is_inlet()] == ["c", "a", "b"]


def test_reorder_leaves_other_lanes_alone(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    before = probe.ports["out"].order
    probe.reorder_ports(["c", "b", "a"])
    assert probe.ports["out"].order == before


def test_reorder_ignores_unknown_ids(graph_with_library_system) -> None:
    """A stale id from a redrawn panel must not raise mid-gesture."""
    probe = _make_probe(graph_with_library_system)
    probe.reorder_ports(["c", "nope", "a", "b"])
    assert [p.id for p in probe.get_visible_ports() if p.is_inlet()] == ["c", "a", "b"]


def test_reorder_is_a_noop_for_an_empty_list(graph_with_library_system) -> None:
    probe = _make_probe(graph_with_library_system)
    before = {p.id: p.order for p in probe.ports.values()}
    probe.reorder_ports([])
    assert {p.id: p.order for p in probe.ports.values()} == before
```

**First create the probe node** at
`barn/haybale-testing/haybale_testing/nodes/testbed/reorder_probe.py`, with a
public `rebuild()` so the rejig test can re-run it:

```python
"""Reorder probe — static and dynamic ports for port-ordering tests."""

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label="Reorder Probe",
    description="Tests user-driven port ordering",
    search_tags=["testing", "reorder", "order"],
    menu="testing/testbed",
    node_type=NodeType.DATA,
)
class ReorderProbeNode(BaseNode):
    """Test-only."""

    def init(self):
        from haywire.barn.builtin.types import FLOAT, STRING

        self.add(FLOAT.as_inlet("a"))
        self.add(FLOAT.as_inlet("b"))
        self.add(FLOAT.as_inlet("c"))
        self.add(STRING.as_outlet("out"))
        self.rebuild()

    def rebuild(self):
        """Re-add the dynamic inlets, as post_init would on every load."""
        from haywire.barn.builtin.types import FLOAT

        with self.rejig(include=r"^dyn_"):
            for name in ("dyn_a", "dyn_b", "dyn_c"):
                self.add(FLOAT.as_inlet(name))

    def worker(self, context: ExecutionContext) -> str | None:
        return None
```

Commit it before running any suite containing `tests/studio/test_docs/`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_port_reorder.py -v`
Expected: FAIL with `AttributeError: 'BaseNode' object has no attribute 'reorder_ports'`

- [ ] **Step 3: Implement `reorder_ports`**

In `packages/haywire-core/src/haywire/core/node/data.py`, beside the other
port-hierarchy methods:

```python
    def reorder_ports(self, ordered_ids: list[str]) -> None:
        """Set the display order of one sibling group from ``ordered_ids``.

        Siblings are the ports sharing a direction lane and a fold — the group
        the user can actually rearrange. Ports outside the list keep the order
        they had, so reordering one lane leaves every other lane alone.

        Ids naming no port are skipped: a stale id from a panel redrawn mid-drag
        must not raise. An empty list changes nothing.

        Args:
            ordered_ids: Every sibling in the group, in the order they should
                display.
        """
        known = [pid for pid in ordered_ids if pid in self.ports]
        if not known:
            return

        # Reuse the slots the group already occupies, so only these ports move.
        slots = sorted(self.ports[pid].order for pid in known)
        for slot, pid in zip(slots, known):
            self.ports[pid].order = slot

        # `if self.wrapper:` matches data.py:183; the attribute is declared
        # non-optional (data.py:41,46) but neighbouring code still guards it.
        if self.wrapper:
            self.wrapper.mark_layout_changed()
```

In `packages/haywire-core/src/haywire/core/node/node_wrapper.py`, beside
`redraw()`:

```python
    def mark_layout_changed(self) -> None:
        """Mark the node's persisted arrangement dirty — its card rebuilds and the graph saves.

        Distinct from ``redraw()``, whose ``NODE_REDRAW_REQUESTED`` is
        visual-only and tells the app layer NOT to mark the file unsaved.
        """
        with self._lock:
            if self._graph:
                self._graph._validation.mark_node_dirty(
                    self._node_id, ChangeReason.NODE_LAYOUT_CHANGED
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_node/test_port_reorder.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/node/data.py packages/haywire-core/src/haywire/core/node/node_wrapper.py tests/core/test_node/test_port_reorder.py
git commit -m "feat(node): add reorder_ports()

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Order survives `rejig()` and promotion regeneration

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/types/port.py:496-508` (`adopt_state_from`)
- Modify: `packages/haywire-core/src/haywire/core/settings/settings.py:56-66` (`Promotion`), `:181-198` (`_set_promoted`), `:561-571` (`_to_dict`), `:600-...` (`_from_dict`)
- Modify: `packages/haywire-core/src/haywire/core/node/promotion.py:131-159`, `:161-230`
- Test: `tests/core/test_node/test_port_reorder.py`

**Interfaces:**
- Consumes: `reorder_ports` from Task 2.
- Produces:
  - `Promotion(direction, show_widget=None, order=None)` — a NamedTuple, `order` third.
  - `Settings._set_promoted(self, name, direction, show_widget=None, order=None)`
  - `promote_setting(node, accessor, field, direction=PortType.INLET, show_widget=None, order=None)`

Two paths destroy a user's order today. `add()` stamps a fresh counter on every
re-add, and `adopt_state_from` transplants edges and field data but not `order` —
so a `rejig()` (which `post_init` runs on *every load* for a dynamic node) resets
it. And a promoted port is never serialized (ADR 0019); it is regenerated through
`add()`, so its order has nowhere to live.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_node/test_port_reorder.py`:

> ⚠️ **Every function-local `@node` class below is a placeholder for a REGISTERED
> probe.** A `@node` declared inside a test function is never registered, so
> `create_node_wrapper` cannot build it. Before writing these tests, add each
> shape as its own module under
> `barn/haybale-testing/haybale_testing/nodes/testbed/` and build it with
> `_make_probe`-style helpers, exactly as the Global Constraints section shows.
> The class bodies below give the port declarations to copy; the test then calls
> the registered node, not a local class.


```python
def test_order_survives_a_rejig(graph_with_library_system) -> None:
    """post_init runs rejig on every load; a re-added port must keep the user's order."""

    @node(
        label="Rejig Probe",
        description="fixture",
        menu="testing/reorder",
        node_type=NodeType.DATA,
    )
    class _RejigProbe(BaseNode):
        """Test-only."""

        def init(self):
            from haywire.barn.builtin.types import FLOAT, STRING

            self.add(STRING.as_outlet("out"))
            self.rebuild()

        def rebuild(self):
            from haywire.barn.builtin.types import FLOAT

            with self.rejig(include=r"^dyn_"):
                for name in ("dyn_a", "dyn_b", "dyn_c"):
                    self.add(FLOAT.as_inlet(name))

        def worker(self, context: ExecutionContext) -> str | None:
            return None

    probe = _make_probe(graph_with_library_system)
    probe.reorder_ports(["dyn_c", "dyn_a", "dyn_b"])
    probe.rebuild()
    assert [p.id for p in probe.get_visible_ports() if p.is_inlet()] == ["dyn_c", "dyn_a", "dyn_b"]


def test_promotion_record_carries_order() -> None:
    from haywire.core.settings.settings import Promotion
    from haywire.core.types.enums import PortType

    record = Promotion(PortType.INLET)
    assert record.order is None
    assert record._replace(order=7).order == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_node/test_port_reorder.py::test_order_survives_a_rejig -v`
Expected: FAIL — the order resets to declaration order.

- [ ] **Step 3: Carry `order` through `adopt_state_from`**

In `packages/haywire-core/src/haywire/core/types/port.py:496-508`, extend
`adopt_state_from`. **The current docstring reads** "Transplant edge state (and
value, when types match) from a port being replaced during reconfiguration.
Called by ``BaseNode.add`` when a port id is re-added in a push/rejig context." —
replace it and add the one new line:

```python
    def adopt_state_from(self, existing: "DataPort") -> None:
        """Transplant edge state, value (when types match) and display order from a
        port being replaced during reconfiguration. Called by ``BaseNode.add`` when a
        port id is re-added in a push/rejig context.

        Order is user-owned: a graph user's arrangement outlives a node
        reconfiguring itself, so a node re-adding a port does not move it. A port
        the node adds for the first time takes a fresh order, and so appends.
        """
        self._linked_edges = existing._linked_edges.copy()
        self._all_edges = existing._all_edges.copy()
        self.order = existing.order

        # Preserve the field instance only when the type is unchanged, so the
        # stored value (and its observers) survive the port swap.
        if existing._data is not None and self._data is not None:
            if existing.type_cls is self.type_cls:
                self._data = existing._data
```

- [ ] **Step 4: Add `order` to the promotion record**

In `packages/haywire-core/src/haywire/core/settings/settings.py`, extend the
`Promotion` NamedTuple:

```python
    direction: PortType
    show_widget: ShowWidgetStrategy | None = None
    order: int | None = None
```

and its docstring:

```
    ``order`` is the port's display position, ``None`` until the user drags it.
    A promoted port is regenerated rather than serialized (ADR 0019), so its
    order lives here for the same reason ``show_widget`` does.
```

Extend `_set_promoted` with `order: int | None = None` and store it:

```python
        self._promoted_keys[fields[name].storage_key] = Promotion(direction, show_widget, order)
```

In `_to_dict`, after the `show_widget` block:

```python
            if record.order is not None:
                entry["order"] = record.order
```

Note `entry` is annotated `dict[str, str]`; widen it to `dict[str, str | int]`.

In `_from_dict` (`settings.py:604-616`), restore it as the third positional.
There is no enum to construct — `order` is a bare `int` — so the existing
`Promotion(...)` call becomes:

```python
            self._promoted_keys[key] = Promotion(
                direction,
                ShowWidgetStrategy(raw_strategy) if raw_strategy is not None else None,
                record.get("order"),
            )
```

Also update `_to_dict`'s docstring at `settings.py:547-551`, which enumerates the
record's keys and would otherwise omit `order`.

Add a setter. ⚠️ **It does NOT mirror `_set_promoted_show_widget`'s
signature**: that one takes a field *name* (`settings.py:200`) and translates it
through `_settings_descriptors()`. This one takes the **storage_key** directly,
because its caller has a port id, and a promoted port's id *is* its storage_key
(`promotion.py:198`):

```python
    def _set_promoted_order(self, storage_key: str, order: int | None) -> None:
        """Record a promoted port's display order, keeping its direction and widget choice."""
        existing = self._promoted_keys.get(storage_key)
        if existing is None:
            return
        self._promoted_keys[storage_key] = existing._replace(order=order)
```

- [ ] **Step 5: Thread `order` through promotion**

In `packages/haywire-core/src/haywire/core/node/promotion.py`:

`promote_setting` (`promotion.py:161-167`, returns `None`) gains
`order: int | None = None`, documented as "The port's display position;
``None`` uses declaration order." Its body already reads
`with node.rejig(include=[pid]): port = node.add(spec)` (`promotion.py:225-226`).
`add()` stamps a fresh counter, so the override must come after it:

```python
    if order is not None:
        port.order = order
```

and pass it to the record: `bag._set_promoted(field, direction, show_widget, order)`.

`regenerate_promoted_ports` passes it through:

```python
            promote_setting(node, accessor, field, record.direction, record.show_widget, record.order)
```

- [ ] **Step 6: Persist the order on a promoted port's reorder**

In `reorder_ports` (Task 2), after assigning the slots, record the new order for
any promoted port so regeneration replays it:

Route it through the existing promotion seam rather than reaching into settings
bags from `data.py`. `promotion.py` already owns "write the port AND its record"
(`set_promoted_show_widget`, `promotion.py:276-298`) and resolves a port id to its
bag with `_resolve_promoted` (`promotion.py:34-44`).

Add to `promotion.py`:

```python
def set_promoted_order(node: "NodeData", port_id: str, order: int) -> None:
    """Record a promoted port's display position on its settings bag.

    A promoted port is regenerated rather than serialized (ADR 0019), so its
    order lives in the promotion record. No-op if ``port_id`` names no promoted
    port.
    """
    try:
        bag, _desc = _resolve_promoted(node, port_id)
    except (KeyError, ValueError):
        return
    bag._set_promoted_order(port_id, order)
```

and call it from `reorder_ports`:

```python
        from haywire.core.node.promotion import set_promoted_order

        for pid in known:
            port = self.ports[pid]
            if port.promoted:
                set_promoted_order(self, pid, port.order)
```

Check `_resolve_promoted`'s real raise behaviour before writing the `except` —
match whatever it actually raises for an unknown port.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_node/test_port_reorder.py -v`
Expected: PASS (6 tests)

- [ ] **Step 8: Run the settings and promotion suites**

```sh
uv run pytest tests/core/test_settings/ tests/core/test_node/ -q
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add packages/haywire-core/src/haywire/core/ tests/core/test_node/test_port_reorder.py
git commit -m "feat(node): a user's port order survives rejig and promotion regeneration

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: The Ports panel renders fold nesting

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py:98-173`
- Test: `tests/ui/panel/test_ports_panel_reorder.py`

**Interfaces:**
- Consumes: the fold hierarchy from the fold plan.
- Produces: `NodePortsPanel._render_lane(self, node, ports, lane, node_id, widget_factory, parent_group=None, depth=0)` — Task 5 wires sortables into it. Note `node` and `lane` are **parameters**, for the reasons below.

The panel is flat today: it partitions `get_visible_ports()` into three lists and
renders each as a bare sequence, so a fold's children appear as ordinary siblings
with no indentation. That already misrepresents the card, and it makes a correct
drag impossible.

⚠️ **Three things the obvious implementation gets wrong.**

1. **Read `get_all_ports()`, not `get_visible_ports()`.**
   `iter_visible_ports` skips any port under a collapsed ancestor
   (`data.py:426`), so a *closed* fold's children are absent from the list
   entirely and could never be reordered — while the panel's own section still
   shows as open. `get_all_ports()` (`data.py:434`) is "every port in display
   order, ignoring group collapse", which is what a panel wants. The node card
   keeps using `get_visible_ports()`; the two surfaces legitimately differ.

2. **The lane comes from the caller, never from `siblings[0]`.**
   A fold is minted via `BOOL.as_config`, so `fold.is_config()` is True
   (`port.py:83-85`). Sniffing the lane from the first sibling would label an
   inlet group `"config"` whenever a fold heads it, colliding its sortable group
   name with the real Config section's — and a cross-lane drop becomes
   expressible, which is exactly what the group scoping exists to prevent. Each
   `expansion_section` passes its own lane down.

3. **Pass the node as a parameter, not on `self`.**
   `node_ports.py:46-52` states the panel is rebuilt fresh on every redraw and
   "cannot own widget cleanup via instance state". Stashing `self._node_for_lane`
   in `draw()` works only by accident of same-pass ordering; thread it instead.

- [ ] **Step 1: Write the failing test**

Create `tests/ui/panel/test_ports_panel_reorder.py`:

```python
"""The Ports panel mirrors the fold hierarchy and drags within one sibling group."""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


def test_panel_renders_lanes_recursively() -> None:
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    assert hasattr(NodePortsPanel, "_render_lane")
    params = inspect.signature(NodePortsPanel._render_lane).parameters
    assert "parent_group" in params
    assert "depth" in params


def test_panel_is_fold_aware() -> None:
    """A flat panel cannot express a legal drop; it must read parent_group."""
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    source = inspect.getsource(NodePortsPanel)
    assert "parent_group" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/panel/test_ports_panel_reorder.py -v`
Expected: FAIL — `assert hasattr(NodePortsPanel, "_render_lane")`

- [ ] **Step 3: Add the recursive lane renderer**

In `node_ports.py`, add to `NodePortsPanel`:

```python
    def _render_lane(
        self,
        node,
        ports: list,
        lane: str,
        node_id: str,
        widget_factory,
        parent_group: str | None = None,
        depth: int = 0,
    ) -> None:
        """Render the ports whose fold is ``parent_group``, recursing into folds.

        One sibling group per call — the ports a user may rearrange among
        themselves. A fold renders its header, then its own children one level
        deeper.

        Args:
            node: The ``BaseNode``, threaded rather than held on ``self``: the
                panel is rebuilt on every redraw and owns no instance state.
            lane: ``"config"``, ``"inlet"`` or ``"outlet"``, supplied by the
                section that owns this list. Never sniffed from a port — a fold
                is itself a CONFIG port and would misreport its lane.
        """
        from nicegui import ui

        siblings = [p for p in ports if p.parent_group == parent_group]
        for port in siblings:
            with ui.column().classes("w-full gap-0").style(f"padding-left: {depth * 12}px;"):
                if getattr(port, "is_group", False):
                    ui.label(port.label).classes("text-xs hw-text-dim px-2 pt-1")
                    self._render_lane(
                        node, ports, lane, node_id, widget_factory, port.id, depth + 1
                    )
                else:
                    self._render_port(port, node_id, widget_factory)
```

Change the port source in `draw()`. It currently reads (`node_ports.py:122-127`):

```python
                if hasattr(hw_node, "get_visible_ports"):
                    visible_ports = hw_node.get_visible_ports()
                else:
                    visible_ports = list(getattr(hw_node, "ports", {}).values())
```

Replace with — a closed fold's children must still be listed here, or they can
never be reordered:

```python
                # get_all_ports, not get_visible_ports: the latter drops every
                # port under a collapsed fold (data.py:426), which would make a
                # closed fold's children unreorderable. The card and the panel
                # legitimately show different sets.
                if hasattr(hw_node, "get_all_ports"):
                    visible_ports = hw_node.get_all_ports()
                else:
                    visible_ports = list(getattr(hw_node, "ports", {}).values())
```

Then replace the three flat loops in `draw()`. Each currently reads:

```python
                if configs:
                    with hui.expansion_section(
                        label=f"Config ({len(configs)})",
                        default_open=True,
                        state=state_bag,
                        panel_key="node:ports:config",
                    ):
                        for port in configs:
                            self._render_port(port, node_id, widget_factory)
```

Change the body of each to pass its own lane:

```python
                        self._render_lane(hw_node, configs, "config", node_id, widget_factory)
```

keeping each `expansion_section` header and `panel_key` exactly as it is. Do the
same for `inlets` (`"inlet"`) and `outlets` (`"outlet"`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_ports_panel_reorder.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the panel suite**

Run: `uv run pytest tests/ui/panel/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py tests/ui/panel/test_ports_panel_reorder.py
git commit -m "feat(panel): the Ports panel mirrors the fold hierarchy

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Wire the sortables

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py`
- Test: `tests/ui/panel/test_ports_panel_reorder.py`

**Interfaces:**
- Consumes: `_render_lane` from Task 4, `reorder_ports` from Task 2.
- Produces: `NodePortsPanel._on_reorder(self, node, sibling_ids, event)` — the drop handler.

Each sibling group gets its own sortable with its own `group=` name, so
SortableJS cannot express a drop into another lane or another fold.

- [ ] **Step 1: Write the failing test**

Append to `tests/ui/panel/test_ports_panel_reorder.py`:

```python
def test_sortable_group_name_is_scoped_per_sibling_group() -> None:
    """Two sibling groups must never share a sortable group name.

    A shared name is what would let SortableJS move an inlet into the outlet
    lane — a drop the model cannot represent.
    """
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    a = NodePortsPanel._sortable_group("n1", "inlet", None)
    b = NodePortsPanel._sortable_group("n1", "outlet", None)
    c = NodePortsPanel._sortable_group("n1", "inlet", "solver")
    d = NodePortsPanel._sortable_group("n2", "inlet", None)
    assert len({a, b, c, d}) == 4


def test_panel_makes_lanes_sortable() -> None:
    import inspect

    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    source = inspect.getsource(NodePortsPanel)
    assert "make_sortable" in source
    assert "_on_reorder" in source


def test_reorder_handler_reads_indices() -> None:
    import inspect

    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    source = inspect.getsource(NodePortsPanel._on_reorder)
    assert "old_index" in source
    assert "new_index" in source
    # The panel subscribes to GraphDataMutated; publishing one redraws the list
    # out from under the gesture.
    assert "GraphDataMutated" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/panel/test_ports_panel_reorder.py::test_sortable_group_name_is_scoped_per_sibling_group -v`
Expected: FAIL — `AttributeError: _sortable_group`

- [ ] **Step 3: Implement the group name and the handler**

Add to `NodePortsPanel`:

```python
    @staticmethod
    def _sortable_group(node_id: str, lane: str, parent_group: str | None) -> str:
        """Return the SortableJS group name for one sibling group.

        Unique per (node, lane, fold), which is what makes a cross-lane or
        cross-fold drop inexpressible rather than something to validate.
        """
        return f"hw-ports:{node_id}:{lane}:{parent_group or 'root'}"

    def _on_reorder(self, node, sibling_ids: list[str], event) -> None:
        """Apply a completed drop: move one id and hand the new order to the node.

        NiceGUI's own ``on_end`` has already re-parented the element
        (``nicegui/elements/sortable/sortable.py:38``) before this runs, so the
        DOM is correct and this only writes the model to match.
        No signal is published — the panel subscribes to ``GraphDataMutated``
        and would rebuild its own list mid-gesture. The node marks itself dirty
        as ``NODE_LAYOUT_CHANGED``, which repaints the card and records the
        change for the save.
        """
        old_index = event.old_index
        new_index = event.new_index
        if old_index == new_index:
            return
        if not (0 <= old_index < len(sibling_ids)) or not (0 <= new_index < len(sibling_ids)):
            return
        reordered = list(sibling_ids)
        reordered.insert(new_index, reordered.pop(old_index))
        node.reorder_ports(reordered)
```

In `_render_lane`, wrap each sibling group in a sortable container. Replace the
method body with:

```python
        from nicegui import ui

        siblings = [p for p in ports if p.parent_group == parent_group]
        if not siblings:
            return

        # `lane` is the caller's, never sniffed: a fold is itself a CONFIG port
        # (BOOL.as_config), so siblings[0].is_config() would mislabel an inlet
        # group and collide its sortable group with the real Config section's.
        sibling_ids = [p.id for p in siblings]

        container = ui.column().classes("w-full gap-0").style(f"padding-left: {depth * 12}px;")
        with container:
            for port in siblings:
                with ui.column().classes("w-full gap-0"):
                    if getattr(port, "is_group", False):
                        ui.label(port.label).classes("text-xs hw-text-dim px-2 pt-1")
                    else:
                        self._render_port(port, node_id, widget_factory)

        container.make_sortable(
            group=self._sortable_group(node_id, lane, parent_group),
            on_end=lambda e, n=node, ids=sibling_ids: self._on_reorder(n, ids, e),
        )

        # Fold children render in their OWN sortable, outside this one, so a
        # child can never be dropped among its parent's siblings.
        for port in siblings:
            if getattr(port, "is_group", False):
                self._render_lane(
                    node, ports, lane, node_id, widget_factory, port.id, depth + 1
                )
```

`node` and `lane` arrive as parameters — nothing is stashed on `self`. The panel
is rebuilt fresh on every redraw (`node_ports.py:46-52`), so instance state
would be a lifecycle bug waiting to happen.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/panel/test_ports_panel_reorder.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py tests/ui/panel/test_ports_panel_reorder.py
git commit -m "feat(panel): drag to reorder ports in the Ports panel

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: End-to-end verification and documentation

**Files:**
- Modify: `docs/guides/ports.md`
- Modify: `docs/reference/glossary.md` (verify the **Port order** entry matches what shipped)

**Interfaces:**
- Consumes: everything above.
- Produces: nothing code-facing.

- [ ] **Step 1: Verify in the running app**

```sh
uv run haywire
```

1. Drop a node with several inlets. Open Properties → Ports.
2. Drag an inlet to a new position. The node card reorders to match.
3. Confirm the graph is marked unsaved.
4. Save, close, reopen — the order persists.
5. Confirm an inlet cannot be dragged into the Outlets section.
6. On a node with a fold, confirm a fold child cannot be dragged out of its fold.
7. Promote a setting to an inlet, drag it, save and reload — the order persists.
8. On a dynamic node (`Switch`, or the `dynamic_port_test` testbed node), reorder,
   then change the setting that triggers `rejig()` — the order survives.
9. **Cross-session:** open the same graph in a second browser window. Reorder in
   one; the other's node card must repaint in the new order, exactly as deleting
   a pin already does. Both windows share one `GraphEntry` and one `BaseGraph`,
   so this is the same path — if it does not update, the reorder is not reaching
   `mark_node_dirty`.

- [ ] **Step 2: Run the full gate**

```sh
uv run pytest -m "not browser and not perf" -q > /tmp/ordering.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/ordering.log
grep -E "passed|failed" /tmp/ordering.log | tail -1
```

Expected: `exit=0`.

- [ ] **Step 3: Lint, format, type-check**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ tests/
```

Expected: clean.

- [ ] **Step 4: Document ordering in the ports guide**

Add an "Ordering" section to `docs/guides/ports.md`: `DataPort.order` is the sort
key; it defaults to `init()` declaration order; the graph user may drag to
reorder in the Properties → Ports panel; the user's order wins over a later
author reordering, so a port added in a new library version appends rather than
landing at its declared position. Note that reordering is not undoable.

Verify the **Port order** glossary entry still describes what shipped.

- [ ] **Step 5: Build the docs**

```sh
uv run mkdocs build --strict
```

Expected: no warnings.

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "docs: document port ordering

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Done When

- [ ] Dragging a port in Properties → Ports reorders the node card.
- [ ] The order survives save/reload, a `rejig()`, and promoted-port regeneration.
- [ ] An inlet cannot be dropped in the Outlets section; a fold child cannot leave its fold.
- [ ] `uv run pytest -m "not browser and not perf" -q` exits 0.
- [ ] `uv run ruff check .` and `uv run ruff format --check .` clean.
- [ ] `uv run mypy` over the `CLAUDE.md` package list clean.
- [ ] `uv run mkdocs build --strict` clean.
