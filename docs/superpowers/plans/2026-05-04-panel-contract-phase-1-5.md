# Panel Contract Phase 1.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the 14 context-menu panels and 3 edge-side panels (EdgeErrorsPanel, EdgeWarningsPanel, DeleteEdgePanel) from the legacy `BasePanel` system to the new `Panel` contract using Protocol-per-context action contracts. Lift gesture state out of the SessionContext metadata dict, rename DOM attributes from scope-string to focus-id, then remove all legacy framework infrastructure (`BasePanel`, `register_scope`, `ScopeDescriptor`, etc.).

**Architecture:** Protocol-per-context — five small action Protocols (`CanvasContextActions`, `NodeContextActions`, `EdgeContextActions`, `SelectionContextActions`, `PortContextActions`), each scoped to one right-click context. `SessionContextMenuProvider` directly implements all five. Each `_open_menu` invocation queries one (action, focus) pair. Panels that appear in multiple contexts (paste, edge-diagnostics) get one explicit class per context, sharing module-private helpers. Gesture state moves from `metadata` dict to a private `_OpenMenuContext` dataclass on the provider; clipboard moves to `SessionContext.clipboard` reactive field. After all migrations, the legacy framework code is removed in a single cleanup pass.

**Tech Stack:** Python 3.12+, NiceGUI, pytest, mypy, ruff. The codebase uses `uv` for package management.

**Reference specs:**
- [`docs/speculative/spec_panel_contract.md`](../../speculative/archive/spec_panel_contract.md) — Phase 1 contract (the destination).
- [`docs/speculative/spec_panel_migration.md`](../../speculative/archive/spec_panel_migration.md) — full inventory.

**Phase 1.5 scope (locked via inquisition 2026-05-04):**
- 14 context-menu panels migrated to Protocol-per-context.
- EdgeErrorsPanel, EdgeWarningsPanel split per host (one class for properties, one for context-menu) sharing helpers.
- DeleteEdgePanel migrated to `EdgeContextActions`.
- PasteSelectionPanel split into `CanvasPasteSelectionPanel` + `SelectionPasteSelectionPanel`.
- 12 test fixture panels migrated against test-specific Protocols + Focuses.
- DOM attribute rename: `data-hw-custom-menu-scope` → `data-hw-custom-menu-focus-id` (Vue + Python).
- `_OpenMenuContext` dataclass replaces gesture state in `metadata` dict.
- Clipboard moves to `SessionContext.clipboard: Reactive[ClipboardData | None]`.
- Cleanup: remove `BasePanel`, `register_scope`, `get_scopes`, `ScopeDescriptor`, `scopes.py`, dual-mode `_class_filter`, dual-mount path in PropertiesEditor, legacy `_index`, `_host_class_to_editor_key` helper, and `editors=`/`scopes=` decorator args.
- `PropertiesEditorActions` moves from `haybale-studio` to `haybale-core` (cross-package layering fix).

**Out of scope:**
- Phase 2 reactivity (Subscriptions, auto-tracking, `@reads`).
- Full clipboard paste implementation (`SelectionHandlers.process_paste_clipboard` is currently `# Full paste implementation: editor.paste(clipboard, x, y) — pending` — Phase 1.5 establishes the SessionContext clipboard contract; the actual graph-level paste is left as it is).
- UX changes beyond what migrations naturally produce.

---

## Codebase research findings (locking the plan to reality)

The inquisition assumed a few things that the actual codebase confirmed or refined:

1. **`ClipboardData` already exists** at `haywire.core.undo.actions.graph_actions`. Phase 1.5 does NOT create a new dataclass — it imports the existing one. Fields: `nodes: list[str]`, `edges: list[str]`, `original_to_new_ids: dict`, `bounding_box: dict`, `timestamp: float`, `source_session_id: str`.

2. **The clipboard already lives in the wrong place** — on `SelectionHandlers.clipboard` in `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py`. Phase 1.5 migrates the writer (`process_copy_selection`) to write to `ctx.clipboard.value`, and the reader (`process_paste_clipboard`) to read from `ctx.clipboard.value`. The `self.clipboard` instance attribute is removed.

3. **PasteSelectionPanel is currently unwired** — it reads `context.metadata.get("clipboard")` but nothing writes there. So PasteSelectionPanel never sees a clipboard today (latent bug). Phase 1.5 fixes this as a side effect of the move.

4. **`metadata["recent_nodes"]` is dead** — read by CreateNodePanel, never written. Phase 1.5 removes the read (defaults to `[]` always was the de-facto behavior).

5. **Two metadata key conventions for click position**: `metadata["canvas_position"]` (CreateNodePanel, dict `{x, y}`) vs `metadata["canvas_x"]`/`["canvas_y"]` (PasteSelectionPanel, two floats). Phase 1.5 unifies: `_OpenMenuContext.canvas_pos: tuple[float, float] | None`.

6. **DOM attribute usage sites**: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` lines 651–678 (port + custom menu detection); `packages/haywire-core/src/haywire/ui/graph_canvas/event_definitions.py` lines 219, 234 (event docstrings reference the attribute name).

7. **`PROPERTIES_SCOPES` registration site**: `barn/haybale-studio/haybale_studio/__init__.py` lines 90–95 calls `panel_registry.register_scope("properties", descriptor)` for each entry. With cleanup, this call site goes away (the scope-descriptor metadata is no longer needed once PropertiesEditor reads from focus classes only).

---

## File Structure

### New files
- `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py` — 5 Protocol classes for context-menu actions
- `barn/haybale-core/haybale_core/focuses.py` — add `SelectionFocus` (existing module already has GraphFocus, NodeFocus, EdgeFocus, PortFocus)
- `barn/haybale-testing/haybale_testing/test_actions.py` — test-specific action Protocols
- `barn/haybale-testing/haybale_testing/test_focuses.py` — test-specific Focus classes
- `tests/ui/graph_canvas/test_context_menu_actions.py` — tests for the new Protocols
- `tests/ui/graph_canvas/test_session_context_menu_provider.py` — tests for the provider's new shape
- `tests/libraries/test_clipboard_reactive.py` — tests for the new clipboard reactive field

### Modified files
- `packages/haywire-core/src/haywire/ui/context.py` — add `clipboard` reactive field
- `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py` — write/read `ctx.clipboard.value` instead of `self.clipboard`
- `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py` — implement 5 Protocols, add `_OpenMenuContext`, change `_open_menu` signature, add focus-id resolution
- `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` — DOM attribute rename
- `packages/haywire-core/src/haywire/ui/graph_canvas/event_definitions.py` — update docstrings referencing the old DOM attribute name
- `packages/haywire-core/src/haywire/ui/panel/decorator.py` — remove `editors=`/`scopes=` args (cleanup)
- `packages/haywire-core/src/haywire/ui/panel/registry.py` — remove `register_scope`, `get_scopes`, dual-mode `_class_filter`, legacy `_index`, `_host_class_to_editor_key` (cleanup)
- `packages/haywire-core/src/haywire/ui/panel/__init__.py` — remove BasePanel/ScopeDescriptor exports (cleanup)
- 14 context-menu panel files in `barn/haybale-core/haybale_core/panels/context_menu/` — migrate to Protocol-per-context
- `barn/haybale-core/haybale_core/panels/edge_panels.py` — split into per-host classes (3 panels)
- `barn/haybale-studio/haybale_studio/editors/properties_editor.py` — remove dual-mount path (cleanup)
- `barn/haybale-studio/haybale_studio/__init__.py` — remove `register_scope` call (cleanup)
- 5 test-fixture panel files in `barn/haybale-testing/haybale_testing/panels/` — migrate to test-specific Protocols
- `barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py` — moves to `barn/haybale-core/haybale_core/properties_editor_actions.py` (cross-package layering fix)

### Deleted files
- `packages/haywire-core/src/haywire/ui/panel/base.py` — `BasePanel` (cleanup)
- `packages/haywire-core/src/haywire/ui/panel/scope.py` — `ScopeDescriptor` (cleanup)
- `barn/haybale-studio/haybale_studio/editors/scopes.py` — `PROPERTIES_SCOPES` (cleanup)

---

## Tracks

The plan groups tasks into five tracks. Order matters — earlier tracks unblock later ones.

- **Track A (Foundation):** Tasks 1–4. New action Protocols, SelectionFocus, SessionContext.clipboard, _OpenMenuContext.
- **Track B (Provider rewrite):** Tasks 5–8. SessionContextMenuProvider implements the Protocols; new `_open_menu(action, focus, pos)` signature; on_custom_context / on_port_context use focus_by_id.
- **Track C (Selection handler clipboard migration):** Task 9. SelectionHandlers writes to ctx.clipboard.value.
- **Track D (Panel migrations):** Tasks 10–24. The 14 context-menu panels + 3 edge panels + 12 test fixtures.
- **Track E (DOM rename):** Tasks 25–26. Vue + Python DOM attribute migration.
- **Track F (Cleanup):** Tasks 27–33. Remove BasePanel, ScopeDescriptor, register_scope, dual-mount path, legacy _index, _host_class_to_editor_key, properties_editor_actions.py move.

---

## Track A — Foundation

### Task 1: Add ContextMenuActions Protocols

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py`
- Test: `tests/ui/graph_canvas/test_context_menu_actions.py`

The 5 Protocols are runtime_checkable so the registry's isinstance filter works.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/graph_canvas/test_context_menu_actions.py
"""ContextMenuActions Protocols are runtime_checkable; structural impl satisfies them."""
from haywire.ui.graph_canvas.handlers.context_menu_actions import (
    CanvasContextActions,
    EdgeContextActions,
    NodeContextActions,
    PortContextActions,
    SelectionContextActions,
)


class _CompleteImpl:
    """Implements every Protocol — used to verify isinstance against all five."""

    def create_node_at_click(self, registry_key: str) -> None: ...
    def paste_at_click(self) -> None: ...
    def delete_node(self, node_id: str) -> None: ...
    def copy_node(self, node_id: str) -> None: ...
    def redraw_node(self, node_id: str) -> None: ...
    def revalidate_node(self, node_id: str) -> None: ...
    def reset_node(self, node_id: str) -> None: ...
    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...
    def copy_selection(self) -> None: ...


def test_canvas_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), CanvasContextActions)


def test_node_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), NodeContextActions)


def test_edge_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), EdgeContextActions)


def test_selection_context_actions_is_runtime_checkable():
    assert isinstance(_CompleteImpl(), SelectionContextActions)


def test_port_context_actions_is_empty_marker_protocol():
    """PortContextActions has no methods; any class satisfies it."""

    class Anything:
        pass

    assert isinstance(Anything(), PortContextActions)


def test_partial_impl_does_not_satisfy_full_protocol():
    """A class missing methods does not satisfy a Protocol that requires them."""

    class _PartialImpl:
        def delete_node(self, node_id: str) -> None: ...

    assert not isinstance(_PartialImpl(), NodeContextActions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/graph_canvas/test_context_menu_actions.py -v`
Expected: FAIL — ImportError, the module doesn't exist yet.

- [ ] **Step 3: Create the module**

```python
# packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py
"""Action contracts for context-menu host (SessionContextMenuProvider).

Five Protocols, one per right-click context. Each Protocol declares only
the verbs valid in that context. The provider implements all five
structurally on a single class.

Phase 1.5 of the panel-contract migration. See
docs/superpowers/plans/2026-05-04-panel-contract-phase-1-5.md.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CanvasContextActions(Protocol):
    """Verbs available when the user right-clicks on empty canvas space."""

    def create_node_at_click(self, registry_key: str) -> None: ...
    def paste_at_click(self) -> None: ...


@runtime_checkable
class NodeContextActions(Protocol):
    """Verbs available when the user right-clicks on a node."""

    def delete_node(self, node_id: str) -> None: ...
    def copy_node(self, node_id: str) -> None: ...
    def redraw_node(self, node_id: str) -> None: ...
    def revalidate_node(self, node_id: str) -> None: ...
    def reset_node(self, node_id: str) -> None: ...


@runtime_checkable
class EdgeContextActions(Protocol):
    """Verbs available when the user right-clicks on an edge."""

    def delete_edge(self, edge_id: str) -> None: ...
    def reconnect_active_edge(self) -> None: ...


@runtime_checkable
class SelectionContextActions(Protocol):
    """Verbs available when the user right-clicks on a multi-element selection."""

    def copy_selection(self) -> None: ...
    def paste_at_click(self) -> None: ...


@runtime_checkable
class PortContextActions(Protocol):
    """Marker Protocol for port-context panels.

    Empty by design — the only built-in port-context panel today is
    PortInfoPanel, which is display-only. Library authors can declare
    additional verbs here as needed.
    """
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/graph_canvas/test_context_menu_actions.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verify the test directory has an __init__.py**

Run: `ls tests/ui/graph_canvas/__init__.py 2>&1`
If missing, create an empty one:
```bash
touch tests/ui/graph_canvas/__init__.py
```

- [ ] **Step 6: Run quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py tests/ui/graph_canvas/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py tests/ui/graph_canvas/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu_actions.py \
        tests/ui/graph_canvas/test_context_menu_actions.py \
        tests/ui/graph_canvas/__init__.py
git commit -m "feat(context-menu): add ContextMenuActions Protocols (Canvas/Node/Edge/Selection/Port)"
```

---

### Task 2: Add SelectionFocus

**Files:**
- Modify: `barn/haybale-core/haybale_core/focuses.py`
- Test: `tests/libraries/test_focuses_have_ids.py` (extend)

`SelectionFocus.available` returns True iff there's a multi-element selection.

- [ ] **Step 1: Write the failing test (extend existing test file)**

Append to `tests/libraries/test_focuses_have_ids.py`:

```python
def test_selection_focus_has_id():
    from haybale_core.focuses import SelectionFocus

    assert SelectionFocus.id == "selection"
    assert focus_by_id("selection") is SelectionFocus


def test_selection_focus_available_when_nodes_selected():
    from unittest.mock import MagicMock

    from haybale_core.focuses import SelectionFocus
    from haywire.ui.context import SessionContext

    ctx = SessionContext(session_id="t", app=MagicMock())
    assert SelectionFocus.available(ctx) is False  # nothing selected

    ctx.selected_nodes.value = {"node-1"}
    assert SelectionFocus.available(ctx) is True


def test_selection_focus_available_when_edges_selected():
    from unittest.mock import MagicMock

    from haybale_core.focuses import SelectionFocus
    from haywire.ui.context import SessionContext

    ctx = SessionContext(session_id="t", app=MagicMock())
    ctx.selected_edges.value = {"edge-1"}
    assert SelectionFocus.available(ctx) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/libraries/test_focuses_have_ids.py -v -k selection`
Expected: FAIL — `SelectionFocus` doesn't exist.

- [ ] **Step 3: Add SelectionFocus to the focus module**

Append to `barn/haybale-core/haybale_core/focuses.py`:

```python
class SelectionFocus(Focus):
    id = "selection"
    label = "Selection"
    icon = "select_all"
    order = 90

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return bool(ctx.selected_nodes.value) or bool(ctx.selected_edges.value)
```

Also add `SelectionFocus` to the module's exports if there's an `__all__` (check the existing file structure first).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/libraries/test_focuses_have_ids.py -v`
Expected: all tests pass (existing + 3 new).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green (Phase 1 baseline + 3 new tests).

- [ ] **Step 6: Quality suite**

Run: `uv run ruff check barn/haybale-core/haybale_core/focuses.py tests/libraries/test_focuses_have_ids.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/focuses.py tests/libraries/test_focuses_have_ids.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-core/haybale_core/focuses.py \
        tests/libraries/test_focuses_have_ids.py
git commit -m "feat(focus): add SelectionFocus for context-menu selection panels"
```

---

### Task 3: Add `clipboard` reactive field to SessionContext

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context.py`
- Test: `tests/libraries/test_clipboard_reactive.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/libraries/test_clipboard_reactive.py
"""SessionContext.clipboard is a reactive field carrying ClipboardData | None."""
from unittest.mock import MagicMock

from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.ui.context import SessionContext
from haywire.ui.reactive import Reactive, ReactivePath


def test_clipboard_class_access_is_reactive_path():
    p = SessionContext.clipboard
    assert isinstance(p, ReactivePath)
    assert p.owner is SessionContext
    assert p.attr == "clipboard"


def test_clipboard_instance_access_is_reactive():
    ctx = SessionContext(session_id="t", app=MagicMock())
    assert isinstance(ctx.clipboard, Reactive)
    assert ctx.clipboard.value is None


def test_clipboard_write_through_value():
    ctx = SessionContext(session_id="t", app=MagicMock())
    data = ClipboardData(
        nodes=["a", "b"],
        edges=[],
        original_to_new_ids={},
        bounding_box={"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        timestamp=1.0,
        source_session_id="t",
    )
    ctx.clipboard.value = data
    assert ctx.clipboard.value is data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/libraries/test_clipboard_reactive.py -v`
Expected: FAIL — `SessionContext` doesn't have a `clipboard` field yet.

- [ ] **Step 3: Add the field to SessionContext**

Read `packages/haywire-core/src/haywire/ui/context.py` to find where the existing reactive fields are declared. Add `clipboard` alongside the other reactive fields:

```python
# In packages/haywire-core/src/haywire/ui/context.py
# Add to TYPE_CHECKING block:
if TYPE_CHECKING:
    # ... existing imports ...
    from haywire.core.undo.actions.graph_actions import ClipboardData

# Add to the reactive fields section (alphabetical or grouped — match existing convention):
    clipboard: Reactive[Optional["ClipboardData"]] = reactive_field(None)
```

The exact placement depends on the existing file structure. Insert near other `Reactive[Optional[...]]` declarations (e.g., after `active_component` or `active_file`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/libraries/test_clipboard_reactive.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green.

- [ ] **Step 6: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/context.py tests/libraries/test_clipboard_reactive.py`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/context.py tests/libraries/test_clipboard_reactive.py`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/context.py`
Expected: clean (mypy at baseline; no new errors).

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/context.py \
        tests/libraries/test_clipboard_reactive.py
git commit -m "feat(context): add clipboard reactive field for context-menu copy/paste"
```

---

### Task 4: Add _OpenMenuContext dataclass to context_menu module

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
- Test: `tests/ui/graph_canvas/test_session_context_menu_provider.py`

The `_OpenMenuContext` dataclass holds gesture state per popup. It's created when a popup opens and cleared when it closes. Replaces several entries from the metadata dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/graph_canvas/test_session_context_menu_provider.py
"""Tests for SessionContextMenuProvider's _OpenMenuContext lifecycle and action methods."""
from typing import Tuple
from unittest.mock import MagicMock

from haywire.ui.context import SessionContext
from haywire.ui.graph_canvas.handlers.context_menu import (
    SessionContextMenuProvider,
    _OpenMenuContext,
)
from haywire.ui.panel.registry import PanelRegistry


def _make_provider(on_emit_event=None, on_emit_sync_event=None) -> SessionContextMenuProvider:
    """Construct a provider with mock dependencies."""
    ctx = SessionContext(session_id="t", app=MagicMock())
    session = MagicMock()
    session.context = ctx
    return SessionContextMenuProvider(
        context=ctx,
        session=session,
        panel_registry=PanelRegistry(),
        on_emit_event=on_emit_event,
        on_emit_sync_event=on_emit_sync_event,
    )


def test_open_menu_context_is_initially_none():
    provider = _make_provider()
    assert provider._open_ctx is None


def test_open_menu_context_holds_canvas_pos():
    """A handler that builds an _OpenMenuContext sets it correctly."""
    ctx = _OpenMenuContext(
        click_pos=(100.0, 200.0),
        canvas_pos=(50.0, 60.0),
    )
    assert ctx.click_pos == (100.0, 200.0)
    assert ctx.canvas_pos == (50.0, 60.0)
    assert ctx.pending_connection is None
    assert ctx.edge_state is None
    assert ctx.edge_reconnect_end is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -v`
Expected: FAIL — `_OpenMenuContext` doesn't exist; `_open_ctx` attribute doesn't exist.

- [ ] **Step 3: Add the dataclass and instance attribute**

Edit `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`. Add the dataclass near the top of the module (after imports, before classes):

```python
# packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py

# (existing imports near the top)
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, TYPE_CHECKING


# Add after the IContextMenuProvider class definition, before SessionContextMenuProvider:

@dataclass
class _OpenMenuContext:
    """Per-popup gesture state held by SessionContextMenuProvider.

    Created when _open_menu opens a popup; cleared on popup close.
    Replaces several entries from the legacy metadata dict
    (canvas_position, canvas_x, canvas_y, edge_state,
    context_menu_screen_pos, edge_reconnect_end, pending_connection).

    Phase 1.5 of the panel-contract migration.
    """

    click_pos: Tuple[float, float]
    canvas_pos: Optional[Tuple[float, float]] = None
    pending_connection: Optional[dict] = None
    edge_state: Any = None
    edge_reconnect_end: bool = False
```

Then add the `_open_ctx` attribute to `SessionContextMenuProvider.__init__`:

```python
class SessionContextMenuProvider(IContextMenuProvider):
    def __init__(
        self,
        context: "SessionContext",
        session: "Session",
        panel_registry: "PanelRegistry",
        on_emit_event: Optional[Callable] = None,
        on_emit_sync_event: Optional[Callable] = None,
    ):
        # ... existing assignments ...
        self._open_ctx: Optional[_OpenMenuContext] = None  # NEW: per-popup gesture state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green (no regression).

- [ ] **Step 6: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py tests/ui/graph_canvas/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py tests/ui/graph_canvas/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py \
        tests/ui/graph_canvas/test_session_context_menu_provider.py
git commit -m "feat(context-menu): add _OpenMenuContext dataclass for popup-local gesture state"
```

---

## Track B — Provider Rewrite

### Task 5: Implement Protocol methods on SessionContextMenuProvider

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
- Test: `tests/ui/graph_canvas/test_session_context_menu_provider.py` (extend)

Add the action verbs as methods on the provider. They're thin wrappers around `self._on_emit_event(legacy_event)`, except for `copy_selection` (writes ctx.clipboard.value via the existing event flow — see Task 9).

- [ ] **Step 1: Extend the test file**

Append to `tests/ui/graph_canvas/test_session_context_menu_provider.py`:

```python
def test_provider_satisfies_node_context_actions():
    from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions

    provider = _make_provider()
    assert isinstance(provider, NodeContextActions)


def test_provider_satisfies_edge_context_actions():
    from haywire.ui.graph_canvas.handlers.context_menu_actions import EdgeContextActions

    provider = _make_provider()
    assert isinstance(provider, EdgeContextActions)


def test_provider_satisfies_canvas_context_actions():
    from haywire.ui.graph_canvas.handlers.context_menu_actions import CanvasContextActions

    provider = _make_provider()
    assert isinstance(provider, CanvasContextActions)


def test_provider_satisfies_selection_context_actions():
    from haywire.ui.graph_canvas.handlers.context_menu_actions import SelectionContextActions

    provider = _make_provider()
    assert isinstance(provider, SelectionContextActions)


def test_delete_node_emits_user_remove_event():
    from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.delete_node("node-1")

    assert len(captured) == 1
    assert isinstance(captured[0], UserRemoveEvent)
    assert captured[0].nodes == ["node-1"]
    assert captured[0].edges == []


def test_delete_edge_emits_user_remove_event():
    from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.delete_edge("edge-1")

    assert len(captured) == 1
    assert captured[0].nodes == []
    assert captured[0].edges == ["edge-1"]


def test_copy_node_emits_user_copy_selected_event():
    from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.copy_node("node-1")

    assert len(captured) == 1
    assert isinstance(captured[0], UserCopySelectedEvent)
    assert captured[0].selectedNodes == ["node-1"]
    assert captured[0].selectedEdges == []


def test_redraw_node_emits_element_redraw_event():
    from haywire.ui.graph_canvas.event_definitions import ElementRedrawEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.redraw_node("node-1")

    assert len(captured) == 1
    assert isinstance(captured[0], ElementRedrawEvent)
    assert captured[0].nodes == ["node-1"]


def test_revalidate_node_emits_element_revalidate_event():
    from haywire.ui.graph_canvas.event_definitions import ElementRevalidateEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.revalidate_node("node-1")

    assert isinstance(captured[0], ElementRevalidateEvent)


def test_reset_node_emits_element_reset_event():
    from haywire.ui.graph_canvas.event_definitions import ElementResetEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.reset_node("node-1")

    assert isinstance(captured[0], ElementResetEvent)


def test_copy_selection_uses_session_context_selection():
    """copy_selection reads ctx.selected_nodes/edges and emits UserCopySelectedEvent."""
    from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._context.selected_nodes.value = {"a", "b"}
    provider._context.selected_edges.value = {"e1"}

    provider.copy_selection()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, UserCopySelectedEvent)
    assert set(event.selectedNodes) == {"a", "b"}
    assert event.selectedEdges == ["e1"]


def test_paste_at_click_emits_paste_event_with_canvas_pos():
    """paste_at_click emits UserPasteClipboardEvent using _open_ctx.canvas_pos."""
    from haywire.ui.graph_canvas.event_definitions import UserPasteClipboardEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        canvas_pos=(123.0, 456.0),
    )

    provider.paste_at_click()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, UserPasteClipboardEvent)
    assert event.canvasX == 123.0
    assert event.canvasY == 456.0


def test_paste_at_click_no_open_ctx_is_noop():
    """If no popup is open, paste_at_click does nothing."""
    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = None

    provider.paste_at_click()

    assert captured == []


def test_create_node_at_click_emits_node_create_request_event():
    from haywire.ui.graph_canvas.event_definitions import NodeCreateRequestEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        canvas_pos=(50.0, 60.0),
    )

    provider.create_node_at_click("core:node:foo")

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, NodeCreateRequestEvent)
    assert event.registryKey == "core:node:foo"
    assert event.position == {"x": 50.0, "y": 60.0}


def test_reconnect_active_edge_uses_open_ctx_and_active_edge():
    """reconnect_active_edge reads ctx.active_edge.value AND _open_ctx.edge_reconnect_end."""
    from haywire.ui.graph_canvas.event_definitions import SyncEdgeReconnectEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)

    # Set up a fake edge in active_edge so reconnect_active_edge sees it.
    wrapper = MagicMock()
    wrapper._edge_id = "edge-1"
    wrapper.source_node_id = "src-node"
    wrapper.outlet_port_id = "out-pin"
    wrapper.sink_node_id = "snk-node"
    wrapper.inlet_port_id = "in-pin"

    provider._context.active_edge.value = wrapper
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        edge_reconnect_end=True,  # clicked near inlet → anchor on outlet (source) side
    )

    provider.reconnect_active_edge()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, SyncEdgeReconnectEvent)
    assert event.anchorNodeId == "src-node"
    assert event.anchorPinId == "out-pin"


def test_reconnect_active_edge_no_active_edge_is_noop():
    """If no active edge, reconnect_active_edge does nothing."""
    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(click_pos=(0, 0))
    # active_edge is None by default

    provider.reconnect_active_edge()

    assert captured == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -v`
Expected: most tests FAIL — the action methods don't exist yet on the provider.

- [ ] **Step 3: Add action methods to SessionContextMenuProvider**

Add to `SessionContextMenuProvider` in `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`:

```python
    # ------------------------------------------------------------------
    # ContextMenuActions Protocol implementations (Phase 1.5)
    # ------------------------------------------------------------------

    # CanvasContextActions

    def create_node_at_click(self, registry_key: str) -> None:
        """Emit NodeCreateRequestEvent at the click's canvas position."""
        from haywire.ui.graph_canvas.event_definitions import NodeCreateRequestEvent

        if self._open_ctx is None or self._open_ctx.canvas_pos is None:
            return
        x, y = self._open_ctx.canvas_pos
        if self._on_emit_event:
            self._on_emit_event(
                NodeCreateRequestEvent(
                    registryKey=registry_key,
                    position={"x": x, "y": y},
                )
            )

    def paste_at_click(self) -> None:
        """Emit UserPasteClipboardEvent at the click's canvas position."""
        from haywire.ui.graph_canvas.event_definitions import UserPasteClipboardEvent

        if self._open_ctx is None or self._open_ctx.canvas_pos is None:
            return
        x, y = self._open_ctx.canvas_pos
        if self._on_emit_event:
            self._on_emit_event(UserPasteClipboardEvent(canvasX=x, canvasY=y))

    # NodeContextActions

    def delete_node(self, node_id: str) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

        if self._on_emit_event:
            self._on_emit_event(UserRemoveEvent(nodes=[node_id], edges=[]))

    def copy_node(self, node_id: str) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent

        if self._on_emit_event:
            self._on_emit_event(UserCopySelectedEvent(selectedNodes=[node_id], selectedEdges=[]))

    def redraw_node(self, node_id: str) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementRedrawEvent

        if self._on_emit_event:
            self._on_emit_event(ElementRedrawEvent(nodes=[node_id], edges=[]))

    def revalidate_node(self, node_id: str) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementRevalidateEvent

        if self._on_emit_event:
            self._on_emit_event(ElementRevalidateEvent(nodes=[node_id], edges=[]))

    def reset_node(self, node_id: str) -> None:
        from haywire.ui.graph_canvas.event_definitions import ElementResetEvent

        if self._on_emit_event:
            self._on_emit_event(ElementResetEvent(nodes=[node_id], edges=[]))

    # EdgeContextActions

    def delete_edge(self, edge_id: str) -> None:
        from haywire.ui.graph_canvas.event_definitions import UserRemoveEvent

        if self._on_emit_event:
            self._on_emit_event(UserRemoveEvent(nodes=[], edges=[edge_id]))

    def reconnect_active_edge(self) -> None:
        """Emit SyncEdgeReconnectEvent for the active edge.

        Reads `ctx.active_edge.value` (the edge to reconnect) and
        `self._open_ctx.edge_reconnect_end` (which end was right-clicked)
        to compute the anchor pin. Panels never pass these as arguments —
        the provider holds them as gesture state.
        """
        from haywire.ui.graph_canvas.event_definitions import SyncEdgeReconnectEvent

        wrapper = self._context.active_edge.value
        if wrapper is None or self._open_ctx is None:
            return

        at_sink_end = self._open_ctx.edge_reconnect_end
        if at_sink_end:
            # Clicked near inlet → anchor on outlet (source) side
            anchor_node_id = wrapper.source_node_id
            anchor_pin_id = wrapper.outlet_port_id
        else:
            # Clicked near outlet → anchor on inlet (sink) side
            anchor_node_id = wrapper.sink_node_id
            anchor_pin_id = wrapper.inlet_port_id

        if self._on_emit_event:
            self._on_emit_event(
                SyncEdgeReconnectEvent(
                    edge_id=wrapper._edge_id,
                    anchorNodeId=anchor_node_id,
                    anchorPinId=anchor_pin_id,
                )
            )

    # SelectionContextActions

    def copy_selection(self) -> None:
        """Emit UserCopySelectedEvent for the current ctx.selected_nodes/edges."""
        from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent

        if self._on_emit_event:
            self._on_emit_event(
                UserCopySelectedEvent(
                    selectedNodes=list(self._context.selected_nodes.value),
                    selectedEdges=list(self._context.selected_edges.value),
                )
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -v`
Expected: all 14+ tests pass.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green.

- [ ] **Step 6: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py tests/ui/graph_canvas/`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py tests/ui/graph_canvas/`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
Expected: clean (or no new errors beyond baseline).

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py \
        tests/ui/graph_canvas/test_session_context_menu_provider.py
git commit -m "feat(context-menu): SessionContextMenuProvider implements 5 action Protocols"
```

---

### Task 6: Refactor `_open_menu` to take (action, focus, pos) and use _OpenMenuContext

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
- Test: `tests/ui/graph_canvas/test_session_context_menu_provider.py` (extend)

The current `_open_menu(trigger: str, pos)` takes a string trigger and queries `panel_registry.get_panels(EDITOR_CONTEXT_MENU, trigger)`. After refactor: `_open_menu(action: type, focus: type[Focus], pos)` queries `panel_registry.get_panels_for(actions_provider=self, focus=focus)` AND filters by isinstance against the action class. During the panel-migration transition, also queries the legacy path so unmigrated panels keep working.

- [ ] **Step 1: Add a test for the new `_open_menu` signature**

Append to `tests/ui/graph_canvas/test_session_context_menu_provider.py`:

```python
def test_open_menu_creates_open_ctx_with_click_pos():
    """_open_menu records click_pos in _open_ctx."""
    from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions
    from haybale_core.focuses import NodeFocus

    provider = _make_provider()
    # _open_menu opens a Popup which requires NiceGUI runtime — patch it.
    provider._build_popup = MagicMock(return_value=MagicMock())  # see implementation below

    provider._open_menu(NodeContextActions, NodeFocus, (100.0, 200.0))

    assert provider._open_ctx is not None
    assert provider._open_ctx.click_pos == (100.0, 200.0)


def test_open_menu_clears_open_ctx_on_close(monkeypatch):
    """When the popup's on_close fires, _open_ctx is set to None."""
    from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions
    from haybale_core.focuses import NodeFocus

    provider = _make_provider()
    popup = MagicMock()
    on_close_callback = []

    def capture_on_close(cb):
        on_close_callback.append(cb)

    popup.on_close = capture_on_close
    provider._build_popup = MagicMock(return_value=popup)

    provider._open_menu(NodeContextActions, NodeFocus, (0.0, 0.0))
    assert provider._open_ctx is not None

    # Trigger the close callback
    on_close_callback[0]()
    assert provider._open_ctx is None
```

The tests assume a helper `_build_popup` that subclasses can mock. The implementation creates this helper to keep the popup creation testable.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -v -k open_menu`
Expected: FAIL — `_build_popup` doesn't exist; `_open_menu` signature doesn't match.

- [ ] **Step 3: Refactor `_open_menu`**

Replace the `_open_menu` method in `SessionContextMenuProvider`:

```python
    def _build_popup(self, pos: Tuple[float, float]):
        """Build a Popup at the given position. Extracted for testability."""
        return Popup(position_x=pos[0], position_y=pos[1], backdrop_click_close=True)

    def _open_menu(
        self,
        action: type,
        focus: type,  # type[Focus] but loose to avoid circular import
        pos: Tuple[float, float],
    ) -> None:
        """Common logic: build popup, query panels for (action, focus), draw.

        Phase 1.5: queries both the new class-keyed lookup
        (get_panels_for) AND the legacy string-keyed lookup
        (get_panels) so unmigrated context-menu panels keep working
        during the transition. Phase 1.5's cleanup track removes the
        legacy branch.
        """
        # Open _OpenMenuContext for this popup; the intent handlers above
        # (on_canvas_context, on_node_context, etc.) populated the rest of
        # its fields before calling _open_menu.
        if self._open_ctx is None:
            # Defensive: an intent handler called _open_menu without
            # building _open_ctx. Build a minimal one.
            self._open_ctx = _OpenMenuContext(click_pos=pos)
        else:
            self._open_ctx.click_pos = pos

        popup = self._build_popup(pos)

        def _emit_and_close(event):
            if self._on_emit_event:
                self._on_emit_event(event)
            popup.close()

        # Legacy bridge: panels still using metadata['on_emit_event']
        # need this until they migrate. Cleanup track removes it.
        self._context.metadata["on_emit_event"] = _emit_and_close

        def _on_close():
            self._context.context_menu_trigger.value = None
            self._context.active_port.value = None
            self._context.active_edge.value = None
            # Resume drag if pending_connection wasn't consumed
            pending = (
                self._open_ctx.pending_connection if self._open_ctx else None
            )
            self._open_ctx = None
            self._context.metadata.pop("on_emit_event", None)
            if pending is not None and self._on_emit_sync_event:
                self._on_emit_sync_event(SyncEdgeConnectResumeEvent())

        popup.on_close(_on_close)

        # Query panels: new (class-keyed) + legacy (string-keyed) for transition
        new_panels = self._panel_registry.get_panels_for(
            actions_provider=self, focus=focus
        )
        legacy_panels = self._panel_registry.get_panels(
            editor_key=EDITOR_CONTEXT_MENU, scope_id=focus.id
        )

        # Dedupe and merge (a class won't normally appear in both)
        seen = set(new_panels)
        merged = list(new_panels) + [p for p in legacy_panels if p not in seen]
        merged.sort(
            key=lambda c: getattr(getattr(c, "class_identity", None), "order", 100)
        )

        visible = [cls for cls in merged if cls.poll(self._context)]
        if not visible:
            return

        layout = PanelLayout(popup.content)
        for cls in visible:
            try:
                instance = cls()
                action_class = getattr(
                    getattr(cls, "class_identity", None), "action", None
                )
                if action_class is not None:
                    # New-form Panel: draw(ctx, layout, actions)
                    instance.draw(self._context, layout, self)
                else:
                    # Legacy BasePanel: draw(ctx, layout)
                    instance.draw(self._context, layout)
            except Exception as exc:
                logger.exception(
                    f"Error drawing context menu panel {cls.__name__}: {exc}"
                )
        popup.open()
```

Update the intent handlers to populate `_open_ctx` and call `_open_menu` with the right (action, focus) pair:

```python
    def on_canvas_context(self, pos, canvas_pos, pending_connection=None):
        from haybale_core.focuses import GraphFocus  # for canvas, GraphFocus or no focus
        from haybale_studio.focuses import CanvasFocus  # canvas-mode focus
        from haywire.ui.graph_canvas.handlers.context_menu_actions import CanvasContextActions

        self._open_ctx = _OpenMenuContext(
            click_pos=pos,
            canvas_pos=canvas_pos,
            pending_connection=pending_connection,
        )
        self._context.context_menu_trigger.value = SCOPE_CANVAS
        self._open_menu(CanvasContextActions, CanvasFocus, pos)

    def on_node_context(self, pos, node_id):
        from haybale_core.focuses import NodeFocus
        from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions

        graph = self._context.active_graph.value
        if graph is not None:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.active_node.value = wrapper

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        self._context.context_menu_trigger.value = SCOPE_NODE
        self._open_menu(NodeContextActions, NodeFocus, pos)

    def on_edge_context(self, pos, edge_id, edge, state, at_sink_end=False):
        from haybale_core.focuses import EdgeFocus
        from haywire.ui.graph_canvas.handlers.context_menu_actions import EdgeContextActions

        graph = self._context.active_graph.value
        if graph is not None:
            wrapper = graph.get_edge_wrapper(edge_id)
            if wrapper is not None:
                self._context.active_edge.value = wrapper

        self._open_ctx = _OpenMenuContext(
            click_pos=pos,
            edge_state=state,
            edge_reconnect_end=at_sink_end,
        )
        self._context.context_menu_trigger.value = SCOPE_EDGE
        self._open_menu(EdgeContextActions, EdgeFocus, pos)

    def on_port_context(self, pos, node_id, port_id, scope):
        from haybale_core.focuses import PortFocus
        from haywire.ui.graph_canvas.handlers.context_menu_actions import PortContextActions
        from haywire.ui.panel.focus import focus_by_id

        graph = self._context.active_graph.value
        if graph is not None:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.active_node.value = wrapper
                self._context.active_port.value = wrapper.node.ports.get(port_id)

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        self._context.context_menu_trigger.value = scope
        # Resolve the focus from the DOM-supplied id; fall back to PortFocus.
        focus = focus_by_id(scope) or PortFocus
        self._open_menu(PortContextActions, focus, pos)

    def on_selection_context(self, pos, nodes, edges):
        from haybale_core.focuses import SelectionFocus
        from haywire.ui.graph_canvas.handlers.context_menu_actions import SelectionContextActions

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        self._context.context_menu_trigger.value = SCOPE_SELECTION
        self._open_menu(SelectionContextActions, SelectionFocus, pos)

    def on_custom_context(self, pos, node_id, scope):
        """Resolve the focus via Focus.id; uses NodeContextActions by default.

        Library authors can declare a custom focus and register panels
        against it; the DOM attribute carries the focus id.
        """
        from haybale_core.focuses import NodeFocus
        from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions
        from haywire.ui.panel.focus import focus_by_id

        graph = self._context.active_graph.value
        if graph is not None:
            wrapper = graph.get_node_wrapper(node_id)
            if wrapper is not None:
                self._context.active_node.value = wrapper

        self._open_ctx = _OpenMenuContext(click_pos=pos)
        self._context.context_menu_trigger.value = scope
        focus = focus_by_id(scope) or NodeFocus
        self._open_menu(NodeContextActions, focus, pos)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/ui/graph_canvas/test_session_context_menu_provider.py -v`
Expected: all tests pass.

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green (existing legacy panels continue to work via the dual-query path).

- [ ] **Step 5: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py \
        tests/ui/graph_canvas/test_session_context_menu_provider.py
git commit -m "refactor(context-menu): _open_menu takes (action, focus, pos); intent handlers use _OpenMenuContext"
```

---

### Task 7: Smoke test the refactored provider

**Files:**
- None modified. Verification only.

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest tests/ 2>&1 | tail -3`
Expected: green.

- [ ] **Step 2: Smoke test the app**

Run: `uv run haywire` (in another terminal). Open the browser. Try right-clicking on:
- Empty canvas → CreateNodePanel renders.
- A node → DeleteNode/CopyNode/etc. render.
- An edge → DeleteEdge/Reconnect render.
- A multi-element selection → CopySelection renders.

All of these should still work because:
- The panels are still legacy (BasePanel) and the dual-mount path queries them.
- The intent handlers populate `_open_ctx` (used by future migrated panels) AND set `metadata["on_emit_event"]` (used by current legacy panels).

Verify nothing crashes. The visual behavior should be identical to Phase 1.

- [ ] **Step 3: No commit (verification only)**

If anything fails, return to Task 6 and fix.

---

### Task 8: PropertiesEditorActions — placeholder for cross-package move

**Files:**
- None modified yet — flagging the move for the cleanup track.

This task is a no-op placeholder. The cross-package move of `PropertiesEditorActions` from haybale-studio to haybale-core happens in Track F (cleanup) after all migrations land. Listed here so the plan structure is explicit about deferring it.

- [ ] **No steps. Skip to Task 9.**

---

## Track C — Selection Handler Clipboard Migration

### Task 9: SelectionHandlers writes/reads ctx.clipboard.value

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py`
- Test: `tests/libraries/test_clipboard_reactive.py` (extend)

`SelectionHandlers.process_copy_selection` currently writes to `self.clipboard`. After this task, it writes to `ctx.clipboard.value` (where ctx is the session's SessionContext). `process_paste_clipboard` reads from `ctx.clipboard.value`. The `self.clipboard` instance attribute is removed.

- [ ] **Step 1: Extend the test**

Append to `tests/libraries/test_clipboard_reactive.py`:

```python
def test_copy_selection_handler_writes_to_session_context():
    """SelectionHandlers.process_copy_selection writes to ctx.clipboard.value."""
    from unittest.mock import MagicMock

    from haywire.core.undo.actions.graph_actions import ClipboardData
    from haywire.ui.context import SessionContext
    from haywire.ui.graph_canvas.event_definitions import UserCopySelectedEvent
    from haywire.ui.graph_canvas.handlers.selection import SelectionHandlers

    # Build a SessionContext + Session
    ctx = SessionContext(session_id="t", app=MagicMock())
    session = MagicMock()
    session.context = ctx

    # Build a fake graph with one node
    wrapper = MagicMock()
    wrapper.node = MagicMock()
    wrapper.node.props.posX = 10.0
    wrapper.node.props.posY = 20.0

    graph = MagicMock()
    graph.get_node_wrapper.return_value = wrapper

    handlers = SelectionHandlers(graph=graph, editor=MagicMock(), session_id="t", session=session)

    # Initially clipboard is None
    assert ctx.clipboard.value is None

    # Process a copy event
    handlers.process_copy_selection(
        UserCopySelectedEvent(selectedNodes=["a"], selectedEdges=[])
    )

    # Now ctx.clipboard.value is a ClipboardData
    assert ctx.clipboard.value is not None
    assert isinstance(ctx.clipboard.value, ClipboardData)
    assert ctx.clipboard.value.nodes == ["a"]


def test_paste_clipboard_handler_reads_from_session_context():
    """SelectionHandlers.process_paste_clipboard reads from ctx.clipboard.value."""
    from unittest.mock import MagicMock

    from haywire.core.undo.actions.graph_actions import ClipboardData
    from haywire.ui.context import SessionContext
    from haywire.ui.graph_canvas.event_definitions import UserPasteClipboardEvent
    from haywire.ui.graph_canvas.handlers.selection import SelectionHandlers

    ctx = SessionContext(session_id="t", app=MagicMock())
    session = MagicMock()
    session.context = ctx

    handlers = SelectionHandlers(graph=MagicMock(), editor=MagicMock(), session_id="t", session=session)

    # No clipboard → no-op (logs warning, doesn't crash)
    handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=0, canvasY=0))
    # No assertion — just verify no crash.

    # With clipboard → handler reads ctx.clipboard.value
    ctx.clipboard.value = ClipboardData(
        nodes=["a"],
        edges=[],
        original_to_new_ids={},
        bounding_box={"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        timestamp=1.0,
        source_session_id="t",
    )
    handlers.process_paste_clipboard(UserPasteClipboardEvent(canvasX=10, canvasY=20))
    # Handler reads clipboard from ctx; the actual paste logic is pending.
    # Verify no crash.
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/libraries/test_clipboard_reactive.py -v`
Expected: FAIL on the new tests (handler still uses `self.clipboard`).

- [ ] **Step 3: Update SelectionHandlers**

Edit `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py`:

Remove `self.clipboard: Optional[ClipboardData] = None` from `__init__`.

Update `process_copy_selection`:

```python
    @handles_event(UserCopySelectedEvent)
    def process_copy_selection(self, event: UserCopySelectedEvent):
        """Store selected elements in the session clipboard."""
        logger.info(
            f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedEdges)} connections"
        )
        if self._session is None:
            logger.warning("Copy ignored: no session bound to handler")
            return
        try:
            bounding_box = self._calculate_selection_bounds(event.selectedNodes)
            self._session.context.clipboard.value = ClipboardData(
                nodes=event.selectedNodes,
                edges=event.selectedEdges,
                original_to_new_ids={},
                bounding_box=bounding_box,
                timestamp=time.time(),
                source_session_id=self.session_id,
            )
        except Exception as e:
            logger.error(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type="negative")
            traceback.print_exc()
```

Update `process_paste_clipboard`:

```python
    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Paste clipboard contents — full implementation pending."""
        if self._session is None:
            logger.warning("Paste ignored: no session bound to handler")
            return

        clipboard = self._session.context.clipboard.value
        if not clipboard:
            logger.warning("❌ No clipboard content to paste")
            ui.notify("Nothing to paste", type="warning")
            return

        logger.info(
            f"📄 Pasting {len(clipboard.nodes)} nodes and "
            f"{len(clipboard.edges)} connections "
            f"at ({event.canvasX}, {event.canvasY})"
        )
        # Full paste implementation: editor.paste(clipboard, x, y) — pending
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/libraries/test_clipboard_reactive.py -v`
Expected: all tests pass.

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green.

- [ ] **Step 5: Quality suite**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py tests/libraries/test_clipboard_reactive.py`
Run: `uv run ruff format packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py tests/libraries/test_clipboard_reactive.py`
Run: `uv run mypy packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/graph_canvas/handlers/selection.py \
        tests/libraries/test_clipboard_reactive.py
git commit -m "refactor(selection): move clipboard from handler instance to ctx.clipboard reactive field"
```

---

## Track D — Panel Migrations

The 14 context-menu panels and 3 edge panels migrate one (file or file-group) at a time. Each migration follows the standard pattern:

1. Read the existing panel.
2. Update imports: `BasePanel` → `Panel`; add the appropriate action Protocol import.
3. Update decorator: `@panel(editors="context_menu", scopes="X", ...)` → `@panel(action=XContextActions, focus=XFocus, ...)`.
4. Update class declaration: `class P(BasePanel)` → `class P(Panel)`.
5. Update method signatures: `draw(self, context, layout)` → `draw(self, ctx, layout, actions)`.
6. Replace `_emit(context, Event(...))` calls with `actions.verb(...)` calls.
7. Run the related tests; smoke test if needed; commit.

### Task 10: Migrate node_actions.py (5 panels)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/context_menu/node_actions.py`

Migrate all 5 panels in this file: DeleteNodePanel, CopyNodePanel, RedrawNodePanel, RevalidateNodePanel, ResetNodePanel.

- [ ] **Step 1: Replace the file contents**

```python
# barn/haybale-core/haybale_core/panels/context_menu/node_actions.py
"""
Context menu panels for node actions.

Phase 1.5 of the panel-contract migration. action=NodeContextActions,
focus=NodeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_core.focuses import NodeFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Delete Node",
    icon=hui.icon.delete,
    order=10,
)
class DeleteNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Delete Node",
            icon=hui.icon.delete,
            on_click=lambda: actions.delete_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Copy Node",
    icon=hui.icon.copy,
    order=20,
)
class CopyNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Copy Node",
            icon=hui.icon.copy,
            on_click=lambda: actions.copy_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Redraw Node",
    icon=hui.icon.refresh,
    order=30,
)
class RedrawNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Redraw Node",
            icon=hui.icon.refresh,
            on_click=lambda: actions.redraw_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Revalidate Node",
    icon=hui.icon.node_status,
    order=40,
)
class RevalidateNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Revalidate Node",
            icon=hui.icon.node_status,
            on_click=lambda: actions.revalidate_node(node_id),
        )


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Reset Node",
    icon=hui.icon.reset,
    order=50,
)
class ResetNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        node = ctx.active_node.value
        if node is None:
            return
        node_id = node.node_id
        layout.button(
            "Reset Node",
            icon=hui.icon.reset,
            on_click=lambda: actions.reset_node(node_id),
        )
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -k "node_actions or context_menu" -v 2>&1 | tail -10`
Expected: green.

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green.

- [ ] **Step 3: Quality**

Run: `uv run ruff check barn/haybale-core/haybale_core/panels/context_menu/node_actions.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/panels/context_menu/node_actions.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-core/haybale_core/panels/context_menu/node_actions.py
git commit -m "refactor(panels): migrate node_actions (5 panels) to NodeContextActions"
```

---

### Task 11: Migrate edge_actions.py (ReconnectEdgePanel)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py`

ReconnectEdgePanel calls `actions.reconnect_active_edge()` (no args). The provider reads `ctx.active_edge.value` and `_open_ctx.edge_reconnect_end` internally to compute the anchor pin. This shape was set in Tasks 1 and 5 (`reconnect_active_edge` Protocol method + provider implementation).

- [ ] **Step 1: Replace the file contents**

```python
# barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py
"""
Context menu panels for edge actions.

Phase 1.5: action=EdgeContextActions, focus=EdgeFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_core.focuses import EdgeFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import EdgeContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=EdgeContextActions,
    focus=EdgeFocus,
    label="Reconnect Edge",
    icon=hui.icon.edge,
    order=10,
)
class ReconnectEdgePanel(Panel):
    """Removes the edge and starts a new connection drag from the anchor pin.

    The provider's reconnect_active_edge action reads the active edge
    and the gesture state (which end was right-clicked) from its own
    _OpenMenuContext. The panel just invokes the verb.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_edge.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: EdgeContextActions,
    ) -> None:
        layout.button(
            "Reconnect",
            icon=hui.icon.edge,
            on_click=actions.reconnect_active_edge,
        )
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -k "edge_actions or reconnect" -v 2>&1 | tail -10`
Expected: green.

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Expected: green.

- [ ] **Step 3: Quality**

Run: `uv run ruff check barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add barn/haybale-core/haybale_core/panels/context_menu/edge_actions.py
git commit -m "refactor(panels): migrate ReconnectEdgePanel to EdgeContextActions"
```

---

### Task 12: Migrate selection_actions.py (CopySelectionPanel + SelectionPasteSelectionPanel)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/context_menu/selection_actions.py`

CopySelectionPanel: `action=SelectionContextActions, focus=SelectionFocus`. Calls `actions.copy_selection()`.
PasteSelectionPanel renamed to `SelectionPasteSelectionPanel`, also `action=SelectionContextActions, focus=SelectionFocus`, gates on clipboard.

A second class `CanvasPasteSelectionPanel` lives in `create_node_panel.py` (Task 13) — both share the same paste verb but appear in different contexts.

- [ ] **Step 1: Replace file contents**

```python
# barn/haybale-core/haybale_core/panels/context_menu/selection_actions.py
"""
Context menu panels for selection actions.

Phase 1.5: action=SelectionContextActions, focus=SelectionFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_core.focuses import SelectionFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import SelectionContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=SelectionContextActions,
    focus=SelectionFocus,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class CopySelectionPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return bool(ctx.selected_nodes.value or ctx.selected_edges.value)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: SelectionContextActions,
    ) -> None:
        layout.button(
            "Copy Selection",
            icon=hui.icon.copy,
            on_click=actions.copy_selection,
        )


@panel(
    action=SelectionContextActions,
    focus=SelectionFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=20,
)
class SelectionPasteSelectionPanel(Panel):
    """Paste panel under the selection focus.

    A separate CanvasPasteSelectionPanel lives in create_node_panel.py
    for the canvas-context popup. Both share the underlying paste action.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.clipboard.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: SelectionContextActions,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=actions.paste_at_click,
        )
```

- [ ] **Step 2-4: Run tests, quality, commit**

Run: `uv run pytest tests/ -k "selection_actions or paste or copy_selection" -v 2>&1 | tail -10`
Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Run: `uv run ruff check barn/haybale-core/haybale_core/panels/context_menu/selection_actions.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/panels/context_menu/selection_actions.py`

Commit:
```bash
git add barn/haybale-core/haybale_core/panels/context_menu/selection_actions.py
git commit -m "refactor(panels): migrate selection_actions to SelectionContextActions"
```

---

### Task 13: Migrate create_node_panel.py (CreateNodePanel + CanvasPasteSelectionPanel)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py`

Adds `CanvasPasteSelectionPanel` to this file. Removes `metadata.get("recent_nodes", [])` since that's never set anywhere.

- [ ] **Step 1: Replace file**

```python
# barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py
"""
CreateNodePanel — context menu panel for the canvas trigger.

Phase 1.5: action=CanvasContextActions, focus=CanvasFocus.
Also hosts CanvasPasteSelectionPanel (paste in canvas context).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.focuses import CanvasFocus
from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.context_signals import ActiveComponentMoved, Reveal
from haywire.ui.graph_canvas.handlers.context_menu_actions import CanvasContextActions
from haywire.ui.graph_canvas.node_menu_builder import NodeMenuBuilder
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=CanvasContextActions,
    focus=CanvasFocus,
    label="Create Node",
    icon=hui.icon.add,
    order=0,
)
class CreateNodePanel(Panel):
    """Render the hierarchical node-creation menu with search on canvas right-click."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: CanvasContextActions,
    ) -> None:
        node_factory = ctx.app.node_factory
        if node_factory is None:
            layout.label("No node factory available.")
            return

        def _on_node_selected(node_info: NodeInfo) -> None:
            actions.create_node_at_click(node_info.identity.registry_key)

        def _on_context_click(node_info: NodeInfo) -> None:
            if ctx.app.library_manager.is_installed(node_info.library.id):
                from haybale_studio.editors.library_component_editor import LibraryComponentEditor

                ctx.active_component.value = node_info.identity.registry_key
                ctx.session.signal(ActiveComponentMoved())
                ctx.session.lifecycle(Reveal(editor=LibraryComponentEditor))

        with layout:
            builder = NodeMenuBuilder(node_factory)
            builder.create_node_menu(
                on_node_selected=_on_node_selected,
                on_context_click=_on_context_click,
                recent_nodes=[],  # legacy metadata read; never populated
                show_search=True,
            )


@panel(
    action=CanvasContextActions,
    focus=CanvasFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=10,
)
class CanvasPasteSelectionPanel(Panel):
    """Paste panel in the canvas context.

    Companion to SelectionPasteSelectionPanel for the selection context.
    Both share the paste_at_click verb on their respective Protocols.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.clipboard.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: CanvasContextActions,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=actions.paste_at_click,
        )
```

- [ ] **Step 2-4: Test, quality, commit**

Run: `uv run pytest tests/ -k "create_node or canvas_paste" -v 2>&1 | tail -10`
Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Run: `uv run ruff check barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py`

Commit:
```bash
git add barn/haybale-core/haybale_core/panels/context_menu/create_node_panel.py
git commit -m "refactor(panels): migrate create_node_panel and add CanvasPasteSelectionPanel"
```

---

### Task 14: Migrate port_info.py (PortInfoPanel)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/context_menu/port_info.py`

Display-only panel. `action=PortContextActions` (empty marker), `focus=PortFocus`.

- [ ] **Step 1: Replace file**

Read the existing `barn/haybale-core/haybale_core/panels/context_menu/port_info.py` to preserve the rendering logic. The migration changes only the imports/decorator/class declaration/draw signature.

```python
# barn/haybale-core/haybale_core/panels/context_menu/port_info.py
"""
PortInfoPanel — display-only panel showing port info on port right-click.

Phase 1.5: action=PortContextActions (empty marker), focus=PortFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_core.focuses import PortFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import PortContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=PortContextActions,
    focus=PortFocus,
    label="Port Info",
    icon=hui.icon.edge,
    order=10,
)
class PortInfoPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_port.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PortContextActions,
    ) -> None:
        port = ctx.active_port.value
        if port is None:
            return
        # Preserve the original rendering. Read the file before this task
        # to copy the exact content that was rendered.
        with layout:
            hui.label(f"Port: {port.id if hasattr(port, 'id') else port}")
            # Add additional info_row calls per the original file's content.
```

**NOTE FOR IMPLEMENTER**: Read the original `port_info.py` to copy the exact rendering content into `draw`. The example above is a placeholder showing the structure.

- [ ] **Step 2-4: Test, quality, commit**

Run: `uv run pytest tests/ -k "port_info" -v 2>&1 | tail -5`
Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Run: `uv run ruff check barn/haybale-core/haybale_core/panels/context_menu/port_info.py`
Run: `uv run ruff format barn/haybale-core/haybale_core/panels/context_menu/port_info.py`

Commit:
```bash
git add barn/haybale-core/haybale_core/panels/context_menu/port_info.py
git commit -m "refactor(panels): migrate port_info to PortContextActions"
```

---

### Task 15: Migrate node_errors.py (NodeErrorsPanel)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/context_menu/node_errors.py`

Display-only panel. Today registered with `scopes="node.errors"`. Per migration spec §4.3, this folds into NodeFocus + panel-level poll. `action=NodeContextActions, focus=NodeFocus`. Poll gates on `node.has_errors()` (or equivalent).

- [ ] **Step 1: Read the existing file** to preserve rendering content. Then replace:

```python
# barn/haybale-core/haybale_core/panels/context_menu/node_errors.py
"""
NodeErrorsPanel — shows error info for a node on right-click.

Phase 1.5: action=NodeContextActions, focus=NodeFocus, gated on
the active node having errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_core.focuses import NodeFocus
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import NodeContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=NodeContextActions,
    focus=NodeFocus,
    label="Node Errors",
    icon=hui.icon.error,
    order=10,
)
class NodeErrorsPanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node = ctx.active_node.value
        return node is not None and bool(node.state.get_errors())

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: NodeContextActions,
    ) -> None:
        # Preserve original rendering — read the file before this task.
        node = ctx.active_node.value
        if node is None:
            return
        errors = node.state.get_errors()
        # ... render errors using layout helpers
```

**NOTE FOR IMPLEMENTER**: Copy the exact rendering content from the original file's `draw` body.

- [ ] **Step 2-4: Test, quality, commit**

```bash
git add barn/haybale-core/haybale_core/panels/context_menu/node_errors.py
git commit -m "refactor(panels): migrate node_errors to NodeContextActions/NodeFocus"
```

---

### Task 16: Migrate edge_panels.py (split EdgeErrorsPanel/WarningsPanel/DeleteEdgePanel)

**Files:**
- Modify: `barn/haybale-core/haybale_core/panels/edge_panels.py`

This is the biggest panel migration. The file has 5 BasePanel classes:
- EdgeErrorsPanel — was dual-host (`editors=["context_menu", "properties"]`). Splits into TWO classes.
- EdgeWarningsPanel — same dual-host. Splits.
- DeleteEdgePanel — context-menu-only.
- ExecutionStatisticsEdgePanel — already migrated (Phase 1).
- ConnectionPathEdgePanel — already migrated (Phase 1).

The dual-host split per Phase 1.5 inquisition Q7=C: explicit dual-class with shared module-private helpers.

- [ ] **Step 1: Read the existing file** to capture the rendering helpers and current Phase 1 migrated classes.

- [ ] **Step 2: Replace contents**

```python
# barn/haybale-core/haybale_core/panels/edge_panels.py
"""
PropertiesEditor + canvas-context-menu edge panels.

Phase 1.5: dual-host panels (EdgeErrors, EdgeWarnings) split into
explicit per-host classes. DeleteEdgePanel migrates to
EdgeContextActions. ExecutionStatistics and ConnectionPath stay as
they were after Phase 1 (PropertiesEditor only).

Module-private helpers ensure both host versions render identically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haybale_core.focuses import EdgeFocus
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haywire.ui import elements as hui
from haywire.ui.graph_canvas.handlers.context_menu_actions import EdgeContextActions
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapperState
    from haywire.ui.context import SessionContext


# ---------------------------------------------------------------------------
# Shared helpers (module-private)
# ---------------------------------------------------------------------------


def _state_from_context(ctx: "SessionContext") -> "EdgeWrapperState | None":
    wrapper = ctx.active_edge.value
    return wrapper.get_state() if wrapper is not None else None


def _has_edge_errors(state: "EdgeWrapperState | None") -> bool:
    return state is not None and state.get_error() is not None


def _has_edge_warnings(state: "EdgeWrapperState | None") -> bool:
    return state is not None and state.has_warning()


def _render_edge_errors(state: "EdgeWrapperState | None") -> None:
    if not _has_edge_errors(state):
        return
    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.ui.errors.error_info import error_render_detail

    error = state.get_error()
    with ui.column().classes("w-full gap-1 p-2"):
        if isinstance(error, HaywireException):
            error_render_detail(error)
        else:
            hui.error_label(str(error)).classes("whitespace-pre-wrap break-words")


def _render_edge_warnings(state: "EdgeWrapperState | None") -> None:
    if not _has_edge_warnings(state):
        return
    with ui.column().classes("w-full gap-1 p-2"):
        hui.warning_label("Warnings").classes("font-semibold")
        for warning in state.warnings:
            hui.warning_label(f"• {warning}").classes("whitespace-pre-wrap break-words ml-1")


# ---------------------------------------------------------------------------
# EdgeErrors — dual-host (one class per host)
# ---------------------------------------------------------------------------


@panel(
    action=PropertiesEditorActions,
    focus=EdgeFocus,
    label="Connection Errors",
    icon=hui.icon.error,
    order=10,
)
class EdgeErrorsPanel(Panel):
    """Edge errors panel for PropertiesEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_errors(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        with layout:
            _render_edge_errors(_state_from_context(ctx))


@panel(
    action=EdgeContextActions,
    focus=EdgeFocus,
    label="Connection Errors",
    icon=hui.icon.error,
    order=10,
)
class ContextMenuEdgeErrorsPanel(Panel):
    """Edge errors panel for the context menu (right-click on edge)."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_errors(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: EdgeContextActions,
    ) -> None:
        with layout:
            _render_edge_errors(_state_from_context(ctx))


# ---------------------------------------------------------------------------
# EdgeWarnings — dual-host
# ---------------------------------------------------------------------------


@panel(
    action=PropertiesEditorActions,
    focus=EdgeFocus,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=20,
)
class EdgeWarningsPanel(Panel):
    """Edge warnings panel for PropertiesEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_warnings(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        with layout:
            _render_edge_warnings(_state_from_context(ctx))


@panel(
    action=EdgeContextActions,
    focus=EdgeFocus,
    label="Connection Warnings",
    icon=hui.icon.warning,
    order=20,
)
class ContextMenuEdgeWarningsPanel(Panel):
    """Edge warnings panel for the context menu."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _has_edge_warnings(_state_from_context(ctx))

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: EdgeContextActions,
    ) -> None:
        with layout:
            _render_edge_warnings(_state_from_context(ctx))


# ---------------------------------------------------------------------------
# DeleteEdgePanel — context-menu only
# ---------------------------------------------------------------------------


@panel(
    action=EdgeContextActions,
    focus=EdgeFocus,
    label="Delete Connection",
    icon=hui.icon.delete,
    order=30,
)
class DeleteEdgePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.active_edge.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: EdgeContextActions,
    ) -> None:
        edge = ctx.active_edge.value
        if edge is None:
            return
        edge_id = edge.edge_id

        layout.button(
            "Delete Connection",
            icon=hui.icon.delete,
            on_click=lambda: actions.delete_edge(edge_id),
        )


# ---------------------------------------------------------------------------
# ExecutionStatistics + ConnectionPath — already migrated in Phase 1
# (PropertiesEditor only). Keep as-is.
# ---------------------------------------------------------------------------

# IMPLEMENTER NOTE: Copy the existing ExecutionStatisticsEdgePanel and
# ConnectionPathEdgePanel classes from the file BEFORE this task — they
# are Phase 1 migrated panels and don't need changes. They use
# action=PropertiesEditorActions, focus=EdgeFocus.
```

**NOTE FOR IMPLEMENTER**: After replacing, append the existing `ExecutionStatisticsEdgePanel` and `ConnectionPathEdgePanel` classes from the previous version of the file (these were migrated in Phase 1 and don't need re-migration).

- [ ] **Step 3-5: Test, quality, commit**

```bash
git add barn/haybale-core/haybale_core/panels/edge_panels.py
git commit -m "refactor(panels): split dual-host edge panels; migrate DeleteEdgePanel to EdgeContextActions"
```

---

### Task 17: Verify all production context-menu panels migrated

**Files:**
- None modified. Verification only.

- [ ] **Step 1: Verify no BasePanel context-menu panels remain**

Run: `grep -rn "class.*BasePanel" barn/haybale-core/haybale_core/panels/context_menu/`
Expected: empty output.

Run: `grep -rn "BasePanel" barn/haybale-core/haybale_core/panels/edge_panels.py`
Expected: empty (the imports for BasePanel are also removed).

Run: `grep -rn "BasePanel\|from haywire.ui.panel.base" barn/haybale-core/haybale_core/panels/`
Expected: imports of `PanelLayout` from `haywire.ui.panel.base` may remain (it's still re-exported there for transition); `BasePanel` references should be gone.

- [ ] **Step 2: Smoke test the app**

Run: `uv run haywire`. Right-click on each context (canvas, node, edge, selection, port). Verify all panels render correctly. Click action buttons. Verify the legacy event flow still works (delete, copy, etc.).

- [ ] **Step 3: No commit (verification only)**

---

### Task 18: Migrate test_create_node_panel.py

**Files:**
- Create: `barn/haybale-testing/haybale_testing/test_actions.py` (new)
- Create: `barn/haybale-testing/haybale_testing/test_focuses.py` (new)
- Modify: `barn/haybale-testing/haybale_testing/panels/test_create_node_panel.py`

Test fixtures use test-specific Protocols and Focuses to avoid contaminating production behavior.

- [ ] **Step 1: Create the test Protocols**

```python
# barn/haybale-testing/haybale_testing/test_actions.py
"""Test-specific action Protocols.

Mirror the structure of production ContextMenuActions but with
test-specific names so test fixtures appear only when test-specific
hosts (which structurally satisfy these Protocols) query them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TestCanvasContextActions(Protocol):
    def test_create_node_at_click(self, registry_key: str) -> None: ...


@runtime_checkable
class TestNodeContextActions(Protocol):
    def test_delete_node(self, node_id: str) -> None: ...
    def test_copy_node(self, node_id: str) -> None: ...
    def test_redraw_node(self, node_id: str) -> None: ...
    def test_revalidate_node(self, node_id: str) -> None: ...
    def test_reset_node(self, node_id: str) -> None: ...


@runtime_checkable
class TestEdgeContextActions(Protocol):
    def test_delete_edge(self, edge_id: str) -> None: ...
    def test_inspect_edge(self, edge_id: str) -> None: ...


@runtime_checkable
class TestSelectionContextActions(Protocol):
    def test_copy_selection(self) -> None: ...
    def test_paste_at_click(self) -> None: ...
```

- [ ] **Step 2: Create the test focuses**

```python
# barn/haybale-testing/haybale_testing/test_focuses.py
"""Test-specific Focus classes.

Mirror NodeFocus/EdgeFocus/etc. with test-specific ids so test
fixtures don't appear under production focus tabs.
"""

from __future__ import annotations

from haywire.ui.context import SessionContext
from haywire.ui.panel.focus import Focus


class TestCanvasFocus(Focus):
    id = "test_canvas"
    label = "Test Canvas"
    icon = "grid_on"
    order = 100

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class TestNodeFocus(Focus):
    id = "test_node"
    label = "Test Node"
    icon = "account_tree"
    order = 110

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_node.value is not None


class TestEdgeFocus(Focus):
    id = "test_edge"
    label = "Test Edge"
    icon = "cable"
    order = 120

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.active_edge.value is not None


class TestSelectionFocus(Focus):
    id = "test_selection"
    label = "Test Selection"
    icon = "select_all"
    order = 130

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return bool(ctx.selected_nodes.value) or bool(ctx.selected_edges.value)
```

- [ ] **Step 3: Migrate test_create_node_panel.py**

Read the existing file to preserve the rendering, then:

```python
# barn/haybale-testing/haybale_testing/panels/test_create_node_panel.py
"""Test fixture: TestCreateNodePanel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_testing.test_actions import TestCanvasContextActions
from haybale_testing.test_focuses import TestCanvasFocus
from haywire.ui import elements as hui
from haywire.ui.panel import Panel
from haywire.ui.panel.base import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    action=TestCanvasContextActions,
    focus=TestCanvasFocus,
    label="Test Create Node",
    icon=hui.icon.add,
    order=0,
)
class TestCreateNodePanel(Panel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return True

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestCanvasContextActions,
    ) -> None:
        layout.button(
            "Test Create",
            icon=hui.icon.add,
            on_click=lambda: actions.test_create_node_at_click("test:registry-key"),
        )
```

- [ ] **Step 4-6: Test, quality, commit**

Run: `uv run pytest tests/ -k "test_create_node or testing" -v 2>&1 | tail -10`
Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Run: `uv run ruff check barn/haybale-testing/`
Run: `uv run ruff format barn/haybale-testing/`

```bash
git add barn/haybale-testing/haybale_testing/test_actions.py \
        barn/haybale-testing/haybale_testing/test_focuses.py \
        barn/haybale-testing/haybale_testing/panels/test_create_node_panel.py
git commit -m "refactor(test fixtures): migrate test_create_node_panel; add test Protocols/Focuses"
```

---

### Task 19: Migrate test_node_panels.py (5 panels)

**Files:**
- Modify: `barn/haybale-testing/haybale_testing/panels/test_node_panels.py`

Apply the same pattern as Task 10 but with test-specific Protocols/Focuses.

- [ ] **Step 1: Replace the file** with the 5 test panels using `TestNodeContextActions, TestNodeFocus`. Each panel mirrors a production node-action panel but calls test-specific verbs (`actions.test_delete_node` etc.).

(Read the existing file first to copy the exact button labels and icons.)

- [ ] **Step 2-4: Test, quality, commit**

```bash
git add barn/haybale-testing/haybale_testing/panels/test_node_panels.py
git commit -m "refactor(test fixtures): migrate test_node_panels (5 panels)"
```

---

### Task 20: Migrate test_edge_panels.py (5 panels including TestInspectEdgePanel)

**Files:**
- Modify: `barn/haybale-testing/haybale_testing/panels/test_edge_panels.py`

Same pattern. Includes `TestInspectEdgePanel` which has no production counterpart.

- [ ] **Step 1: Replace** with 5 test panels using `TestEdgeContextActions, TestEdgeFocus`.

- [ ] **Step 2-4: Test, quality, commit**

```bash
git add barn/haybale-testing/haybale_testing/panels/test_edge_panels.py
git commit -m "refactor(test fixtures): migrate test_edge_panels (5 panels)"
```

---

### Task 21: Migrate test_selection_panels.py (2 panels)

**Files:**
- Modify: `barn/haybale-testing/haybale_testing/panels/test_selection_panels.py`

- [ ] **Step 1: Replace** with `TestCopySelectionPanel` and `TestPasteSelectionPanel` using `TestSelectionContextActions, TestSelectionFocus`.

- [ ] **Step 2-4: Test, quality, commit**

```bash
git add barn/haybale-testing/haybale_testing/panels/test_selection_panels.py
git commit -m "refactor(test fixtures): migrate test_selection_panels (2 panels)"
```

---

### Task 22-24: Smoke test, verify, dual-mount path stays

These three tasks are verification placeholders. Run the full suite + smoke test the app after panel migrations.

- [ ] **Task 22**: Run `uv run pytest tests/ -v 2>&1 | tail -10` — expect green.
- [ ] **Task 23**: Smoke test the app. Right-click on each context. Verify all migrated context-menu panels render and act correctly.
- [ ] **Task 24**: No code changes. Confirm Phase 1's dual-mount path in PropertiesEditor still works (its now-mostly-redundant legacy queries return nothing, but the new queries return the migrated panels).

Commit after each verification: skipped (no changes).

---

## Track E — DOM Rename

### Task 25: Rename DOM attributes (Vue side)

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue`

The two attribute names: `data-hw-custom-menu-scope` → `data-hw-custom-menu-focus-id`, `data-hw-port-menu-scope` → `data-hw-port-menu-focus-id`.

- [ ] **Step 1: Edit canvas.vue**

Locate the two `closest('[data-hw-custom-menu-scope]')` and `closest('[data-hw-port-menu-scope]')` calls (around lines 654 and 675). Update both attribute selectors and the `getAttribute(...)` calls to use the new attribute names.

Sample edit:
```javascript
// Before:
const portMenuEl = target.closest('[data-hw-port-menu-scope]');
if (portMenuEl) {
    const scope = portMenuEl.getAttribute('data-hw-port-menu-scope');
    ...
}

// After:
const portMenuEl = target.closest('[data-hw-port-menu-focus-id]');
if (portMenuEl) {
    const scope = portMenuEl.getAttribute('data-hw-port-menu-focus-id');
    ...
}
```

Same for `data-hw-custom-menu-scope` → `data-hw-custom-menu-focus-id`.

- [ ] **Step 2: Update event docstrings**

Edit `packages/haywire-core/src/haywire/ui/graph_canvas/event_definitions.py` lines 219 and 234:

```python
# line 219:
description="Custom-scope context menu triggered via data-hw-custom-menu-focus-id attribute",
# line 234:
description="Port context menu triggered via data-hw-port-menu-focus-id attribute",
```

- [ ] **Step 3: Verify no other references**

Run: `grep -rn "data-hw-custom-menu-scope\|data-hw-port-menu-scope" --include="*.py" --include="*.vue" --include="*.ts" .`
Expected: empty output.

- [ ] **Step 4: Smoke test**

Run: `uv run haywire`. Verify port and custom-scope context menus still work (they should — Vue side passes the new string, Python side resolves via `focus_by_id` per Task 6).

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/components/graph/canvas.vue \
        packages/haywire-core/src/haywire/ui/graph_canvas/event_definitions.py
git commit -m "refactor(canvas): rename data-hw-*-menu-scope to data-hw-*-menu-focus-id"
```

---

### Task 26: Update docstrings/comments referencing "scope" semantics

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`

Update the IContextMenuProvider docstrings for `on_custom_context` and `on_port_context` to reference the new attribute name:

```python
    def on_custom_context(
        self,
        pos: Tuple[float, float],
        node_id: str,
        scope: str,
    ) -> None:
        """User right-clicked a custom-scope element (data-hw-custom-menu-focus-id)."""
        ...

    def on_port_context(
        self,
        pos: Tuple[float, float],
        node_id: str,
        port_id: str,
        scope: str,
    ) -> None:
        """User right-clicked a port-scope element (data-hw-port-menu-focus-id)."""
        ...
```

The `scope: str` parameter name stays (legacy interface) but its meaning is "focus_id" now.

- [ ] **Step 1: Edit the docstrings**

- [ ] **Step 2: Run tests + quality + commit**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`
Run: `uv run ruff check packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py`

```bash
git add packages/haywire-core/src/haywire/ui/graph_canvas/handlers/context_menu.py
git commit -m "docs(context-menu): update IContextMenuProvider docstrings for renamed DOM attribute"
```

---

## Track F — Cleanup

After all migrations land, the cleanup track removes the legacy infrastructure.

### Task 27: Remove `editors=`/`scopes=` from @panel decorator

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/decorator.py`
- Modify: `tests/ui/panel/test_panel_decorator.py`

The decorator no longer accepts `editors=` or `scopes=`. Required: `action=`, `focus=`, `label=`.

- [ ] **Step 1: Update decorator** — remove the `editors` and `scopes` parameters and the validation branches that handle the legacy form. Keep the new-form-only path. The `_host_class_to_editor_key` helper (which was used for legacy translation) also goes away.

- [ ] **Step 2: Update tests** — remove the `test_panel_legacy_and_new_args_mutually_exclusive` test (the legacy form is gone), replace with a test verifying that omitting `action=` or `focus=` raises ValueError.

- [ ] **Step 3: Test + commit**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`. If legacy panel tests fail, those panels weren't migrated; revisit prior tracks.

```bash
git commit -m "refactor(panel): remove legacy editors=/scopes= decorator args"
```

---

### Task 28: Remove `register_scope`, `get_scopes`, `ScopeDescriptor` from PanelRegistry

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/registry.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/__init__.py`
- Delete: `packages/haywire-core/src/haywire/ui/panel/scope.py`
- Modify: `barn/haybale-studio/haybale_studio/__init__.py` (remove `register_scope` call)
- Delete: `barn/haybale-studio/haybale_studio/editors/scopes.py`

- [ ] **Step 1: Remove all references to `register_scope`/`get_scopes`/`ScopeDescriptor`/`PROPERTIES_SCOPES` outside their definition files.**

Search: `grep -rn "register_scope\|get_scopes\|ScopeDescriptor\|PROPERTIES_SCOPES" --include="*.py" .`
For each remaining reference, remove or update.

- [ ] **Step 2: Delete `packages/haywire-core/src/haywire/ui/panel/scope.py` and remove from package init.**

- [ ] **Step 3: Delete `barn/haybale-studio/haybale_studio/editors/scopes.py` and remove the import from `haybale_studio/__init__.py` register_components.**

- [ ] **Step 4: Delete `register_scope`/`get_scopes` methods and `_scope_index` from `PanelRegistry`.**

- [ ] **Step 5: Test + commit**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`

```bash
git commit -m "refactor: remove ScopeDescriptor, register_scope, get_scopes, scopes.py"
```

---

### Task 29: Remove dual-mode `_class_filter` and legacy `_index` in PanelRegistry

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/registry.py`

`_class_filter` accepts only `Panel` subclasses. The legacy `_index` keyed by `(editor_key, scope_id)` collapses; add a class-keyed index if needed for performance, or drop the index and rely on `get_panels_for` walking all classes (fine for small N).

- [ ] **Step 1: Update `_class_filter`** — remove the BasePanel branch:

```python
    def _class_filter(self, cls) -> bool:
        try:
            if not inspect.isclass(cls):
                return False
            if not hasattr(cls, "class_identity"):
                return False
            if cls is Panel:
                return False
            return issubclass(cls, Panel)
        except TypeError:
            return False
```

- [ ] **Step 2: Remove `get_panels`, `get_all_for_editor`, `_index`, `_index_panel`, `_deindex_panel`** — these are the legacy string-keyed lookups. Update PropertiesEditor's `_mount_panels_for_active_focus` to use only `get_panels_for`.

- [ ] **Step 3: Update PropertiesEditor.**

In `barn/haybale-studio/haybale_studio/editors/properties_editor.py`, remove the dual-mount path:

```python
    def _mount_panels_for_active_focus(self, focus: type[Focus]) -> list[type]:
        if self._panel_registry is None:
            return []
        return self._panel_registry.get_panels_for(actions_provider=self, focus=focus)
```

- [ ] **Step 4: Update SessionContextMenuProvider.**

In `_open_menu`, remove the legacy `get_panels` query and the dedupe logic:

```python
    visible_classes = self._panel_registry.get_panels_for(
        actions_provider=self, focus=focus
    )
    visible = [cls for cls in visible_classes if cls.poll(self._context)]
```

- [ ] **Step 5: Test + commit**

```bash
git commit -m "refactor: remove legacy _index and dual-mount path; Panel-only filter"
```

---

### Task 30: Delete BasePanel

**Files:**
- Delete: `packages/haywire-core/src/haywire/ui/panel/base.py`
- Modify: `packages/haywire-core/src/haywire/ui/panel/__init__.py`

`BasePanel` should now have no consumers. `PanelLayout` (defined in the same file) needs a new home — move to a new `panel/layout.py` or to `panel/__init__.py`.

- [ ] **Step 1: Move `PanelLayout` to `packages/haywire-core/src/haywire/ui/panel/layout.py`.**

- [ ] **Step 2: Delete `BasePanel` from base.py.** Or delete the entire file and update imports across the codebase.

- [ ] **Step 3: Update package __init__.py** to import `PanelLayout` from its new location.

- [ ] **Step 4: Update every panel file's import** of `PanelLayout` to use the new path. Use grep + sed:

```bash
grep -rln "from haywire.ui.panel.base import.*PanelLayout" --include="*.py" . | xargs -I{} sed -i.bak 's|from haywire.ui.panel.base import.*PanelLayout|from haywire.ui.panel.layout import PanelLayout|g' {}
find . -name "*.bak" -delete
```

- [ ] **Step 5: Test + commit**

Run: `uv run pytest tests/ -x 2>&1 | tail -3`. If any test imports BasePanel, it's a stale test from Phase 1; remove or update.

```bash
git commit -m "refactor: delete BasePanel; relocate PanelLayout to panel/layout.py"
```

---

### Task 31: Move PropertiesEditorActions to haybale-core

**Files:**
- Create: `barn/haybale-core/haybale_core/properties_editor_actions.py`
- Delete: `barn/haybale-studio/haybale_studio/editors/properties_editor_actions.py`
- Modify: every panel file that imports from the old path

- [ ] **Step 1: Move the module.** Copy contents to the new path; delete the old.

- [ ] **Step 2: Update all imports.**

```bash
grep -rln "from haybale_studio.editors.properties_editor_actions" --include="*.py" . | \
    xargs -I{} sed -i.bak 's|haybale_studio.editors.properties_editor_actions|haybale_core.properties_editor_actions|g' {}
find . -name "*.bak" -delete
```

- [ ] **Step 3: Test + commit**

```bash
git commit -m "refactor: move PropertiesEditorActions from haybale-studio to haybale-core"
```

---

### Task 32: Final cleanup verification

**Files:**
- None modified. Verification.

- [ ] **Step 1: No BasePanel references remain.**

Run: `grep -rn "BasePanel" --include="*.py" packages barn tests`
Expected: empty.

- [ ] **Step 2: No `register_scope`/`ScopeDescriptor` references remain.**

Run: `grep -rn "register_scope\|ScopeDescriptor" --include="*.py" --include="*.vue" packages barn tests`
Expected: empty.

- [ ] **Step 3: No `data-hw-custom-menu-scope`/`data-hw-port-menu-scope` references remain.**

Run: `grep -rn "data-hw-custom-menu-scope\|data-hw-port-menu-scope" packages barn`
Expected: empty.

- [ ] **Step 4: No `metadata["on_emit_event"]` references in panels.**

Run: `grep -rn "metadata\[.on_emit_event.\]\|metadata\.get\(.on_emit_event.\)" --include="*.py" barn`
Expected: empty.

- [ ] **Step 5: Final smoke test of the app.**

Run: `uv run haywire`. Walk through every right-click context. Verify all panels render and act correctly.

- [ ] **Step 6: No commit (verification only).**

---

### Task 33: Update spec docs to mark Phase 1.5 complete

**Files:**
- Modify: `docs/speculative/spec_panel_contract.md`
- Modify: `docs/speculative/spec_panel_migration.md`

- [ ] **Step 1: Update the contract spec status header** to indicate Phase 1.5 complete (all panels migrated, legacy infrastructure removed).

- [ ] **Step 2: Update the migration spec** to note: 0 BasePanel panels remain. All 33 production panels migrated. Cleanup complete.

- [ ] **Step 3: Commit**

```bash
git add docs/speculative/spec_panel_contract.md docs/speculative/spec_panel_migration.md
git commit -m "docs(spec): mark Phase 1.5 of panel-contract migration as complete"
```

---

## Phase 1.5 Done

Codebase ends Phase 1.5 with:
- 33 production panels + 12 test fixtures all on the new `Panel` contract.
- 5 ContextMenuActions Protocols in framework code.
- SelectionFocus + the existing 8 focuses, all with `id` ClassVar.
- `SessionContext.clipboard` reactive field (replaces metadata-dict consumer).
- DOM attributes renamed.
- All legacy framework code removed: BasePanel, ScopeDescriptor, register_scope, dual-mode filter, dual-mount path, editors=/scopes= decorator args.
- PropertiesEditorActions in haybale-core (cross-package layering fixed).

Phase 2 (reactivity: Subscriptions, auto-tracking, @reads, classmethod→instance method poll) starts next.
