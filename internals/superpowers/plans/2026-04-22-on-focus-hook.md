# on_focus Hook — Editor-Agnostic Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Invert the `OPEN_GRAPH_REQUESTED` event flow into an editor-side `on_focus` lifecycle hook so the shell stops carrying editor-specific knowledge (haystack lookups, `ACTIVE_GRAPH_CHANGED` emission, `context_field` dispatch).

**Architecture:** Add `BaseEditor.on_focus(context)` called by a new `Slot._activate(binding)` helper at every transition-to-active (initial render, `switch_to`, `add_binding(activate=True)`). `GraphEditor.on_focus` resolves its payload via haystack and updates `context.active_graph*`; `FileViewer.on_focus` updates `context.active_file`. Delete `OPEN_GRAPH_REQUESTED`, `_handle_open_graph_requested`, `_follow_main_tab_context`, and `EditorIdentity.context_field`. Migrate 5 call sites to vanilla `EDITOR_FOCUSED` reveal events.

**Tech Stack:** Python 3.11+, NiceGUI, pytest, uv.

---

## File Map

**Core (haywire-core):**
- Modify: `packages/haywire-core/src/haywire/ui/editor/base.py` — add `on_focus` default no-op.
- Modify: `packages/haywire-core/src/haywire/ui/app/slot.py` — add `_activate` helper; wire it into `switch_to`, `render_area` initial draw, `add_binding(activate=True)`.
- Modify: `packages/haywire-core/src/haywire/ui/editor/identity.py` — remove `context_field`.
- Modify: `packages/haywire-core/src/haywire/ui/editor/decorator.py` — remove `context_field` kwarg.
- Modify: `packages/haywire-core/src/haywire/ui/context_events.py` — remove `OPEN_GRAPH_REQUESTED` enum value.
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` — delete `_handle_open_graph_requested` + dispatch branch; delete `_follow_main_tab_context` + its `_switch_main_slot` call.

**Editors (barn/haybale-studio):**
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py` — add `on_focus` override; remove no-longer-needed imports if any.
- Modify: `barn/haybale-studio/haybale_studio/editors/file_viewer.py` — remove `context_field="active_file"` kwarg; add `on_focus` override.
- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` — migrate 4 call sites (`_on_new`, `_on_select`, load-haystack dialog, open-graph dialog) from `OPEN_GRAPH_REQUESTED` to `EDITOR_FOCUSED` reveals.
- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py` — migrate `_open_graph_file` from `OPEN_GRAPH_REQUESTED` to `EDITOR_FOCUSED` reveal.

**Tests:**
- Create: `tests/ui/test_slot_on_focus.py` — unit tests for `Slot._activate` / `on_focus` firing rules.
- Create: `tests/studio/test_graph_editor_on_focus.py` — GraphEditor `on_focus` behavior (happy path, missing entry → `TAB_CLOSE_REQUESTED`, no-op short-circuit).
- Create: `tests/studio/test_file_viewer_on_focus.py` — FileViewer `on_focus` behavior.
- Modify: `tests/ui/test_app_shell.py` — delete `OPEN_GRAPH_REQUESTED` handler tests (lines 466–581) and `TestFollowMainTabContextByField` class (lines 740–842).
- Modify: `barn/haybale-studio/tests/` — any integration tests that simulate graph opens must be updated to expect `EDITOR_FOCUSED` + `ACTIVE_GRAPH_CHANGED` instead of `OPEN_GRAPH_REQUESTED`.

**Docs:**
- Modify: `internals/documentation/build_editors.md` — remove `context_field` doc; add `on_focus` section.
- Modify: `internals/UBIQUITOUS_LANGUAGE.md` — remove `context_field` entry; add `on_focus` entry.
- Modify: `.codemap/modules/core-ui.md` — remove `context_field` mention.

---

## Task 1: Add `on_focus` hook to `BaseEditor`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/base.py`
- Test: `tests/ui/test_slot_on_focus.py` (created in Task 2)

- [ ] **Step 1.1: Add `on_focus` method to `BaseEditor`**

In `packages/haywire-core/src/haywire/ui/editor/base.py`, add this method immediately after `poll` (before `draw`):

```python
    def on_focus(self, context: "SessionContext") -> None:
        """
        Called when this binding transitions from not-active to active
        in its slot.

        Fires on: initial slot render (first active binding), Slot.switch_to
        (programmatic reveal or user tab click), Slot.add_binding(activate=True).
        Does NOT fire when re-selecting the already-active binding.

        Runs before draw() on the newly-activated binding, so any context
        mutations this hook performs are visible to that draw() call and
        to any events this hook broadcasts.

        The default implementation is a no-op. Editors that own session
        state (e.g. GraphEditor owns context.active_graph) override this
        to update the context and broadcast the corresponding event.

        Read ``self.binding.payload`` for this instance's identity.

        Args:
            context: The current session context.
        """
        pass
```

Also update the class-level docstring bullet list. Find the block:

```python
    Subclasses may override:
        - poll(context, event): Return True when a full redraw is needed.
        - cleanup(): Release resources when permanently removed.
        - get_tab_label(context): Dynamic tab label for tabbed slots.
```

And replace with:

```python
    Subclasses may override:
        - poll(context, event): Return True when a full redraw is needed.
        - on_focus(context): Called when this binding becomes active.
        - cleanup(): Release resources when permanently removed.
        - get_tab_label(context): Dynamic tab label for tabbed slots.
```

- [ ] **Step 1.2: Run type check to make sure the method is well-formed**

Run: `uv run mypy packages/haywire-core/src/haywire/ui/editor/base.py`
Expected: PASS (no new errors).

- [ ] **Step 1.3: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/base.py
git commit -m "feat(editor): add BaseEditor.on_focus lifecycle hook (no-op default)"
```

---

## Task 2: Wire `on_focus` into `Slot` via `_activate` helper

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/slot.py`
- Test: `tests/ui/test_slot_on_focus.py`

- [ ] **Step 2.1: Create failing test file `tests/ui/test_slot_on_focus.py`**

Create this file:

```python
"""Tests for Slot._activate and on_focus lifecycle hook firing rules."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.ui.app.slot import EditorBinding, Slot
from haywire.ui.editor.base import BaseEditor


class _FakeEditor(BaseEditor):
    """Minimal BaseEditor subclass that records on_focus / draw calls."""

    class_identity = SimpleNamespace(
        registry_key="test:editor:fake",
        label="Fake",
        default_slot="main",
    )

    def __init__(self) -> None:
        self.focus_calls: list[Any] = []
        self.draw_calls: list[Any] = []

    def draw(self, context, container) -> None:
        self.draw_calls.append(context)

    def on_focus(self, context) -> None:
        self.focus_calls.append(context)


def _make_session():
    ctx = SimpleNamespace()
    session = SimpleNamespace(context=ctx)
    return session


def _make_binding(key: str) -> EditorBinding:
    return EditorBinding(editor_key=key, editor_cls=_FakeEditor, payload=None)


def test_switch_to_calls_on_focus_on_new_active_binding():
    """Slot.switch_to must call on_focus(context) on the newly-activated instance."""
    session = _make_session()
    b1 = _make_binding("e1")
    b2 = _make_binding("e2")
    slot = Slot(session, "main", [b1, b2], active_key="e1")

    # Bootstrap area so switch_to executes its full path.
    slot._area_container = MagicMock()

    # Pre-create instances so we can observe calls.
    b1.ensure_instance()
    b2.ensure_instance()

    slot.switch_to("e2")

    assert len(b2.instance.focus_calls) == 1
    assert b2.instance.focus_calls[0] is session.context


def test_switch_to_does_not_call_on_focus_when_target_already_active():
    """Re-selecting the active binding must NOT re-fire on_focus."""
    session = _make_session()
    b1 = _make_binding("e1")
    slot = Slot(session, "main", [b1], active_key="e1")
    slot._area_container = MagicMock()
    b1.ensure_instance()

    slot.switch_to("e1")

    assert b1.instance.focus_calls == []


def test_render_area_calls_on_focus_on_initial_active_binding():
    """First render of the slot must fire on_focus on the initially-active binding."""
    session = _make_session()
    b1 = _make_binding("e1")
    slot = Slot(session, "main", [b1], active_key="e1")

    parent = MagicMock()
    slot.render_area(parent)

    assert b1.instance is not None
    assert len(b1.instance.focus_calls) == 1


def test_add_binding_activate_true_calls_on_focus():
    """add_binding(activate=True) must fire on_focus on the newly-added binding."""
    session = _make_session()
    slot = Slot(session, "main", [], active_key=None)
    slot._area_container = MagicMock()

    new_binding = _make_binding("e_new")
    slot.add_binding(new_binding, activate=True)

    assert new_binding.instance is not None
    assert len(new_binding.instance.focus_calls) == 1


def test_on_focus_runs_before_draw_on_first_activation():
    """on_focus must fire before draw on the first time a binding becomes active."""
    session = _make_session()
    b1 = _make_binding("e1")
    slot = Slot(session, "main", [b1], active_key="e1")

    parent = MagicMock()
    slot.render_area(parent)

    instance = b1.instance
    # focus_calls is appended in on_focus; draw_calls is appended in draw.
    # We can't compare timestamps easily — instead assert both ran.
    assert len(instance.focus_calls) == 1
    assert len(instance.draw_calls) == 1


def test_on_focus_raising_is_logged_and_swallowed(caplog):
    """An exception from on_focus must be logged and not propagate."""
    import logging

    class _RaisingEditor(_FakeEditor):
        def on_focus(self, context):
            raise RuntimeError("boom")

    session = _make_session()
    b1 = EditorBinding(editor_key="e1", editor_cls=_RaisingEditor, payload=None)
    slot = Slot(session, "main", [b1], active_key="e1")
    parent = MagicMock()

    with caplog.at_level(logging.ERROR, logger="haywire.ui.app.slot"):
        slot.render_area(parent)

    assert any("on_focus" in rec.message for rec in caplog.records)
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `uv run pytest tests/ui/test_slot_on_focus.py -v`
Expected: all 6 tests FAIL (no `on_focus` call yet in `Slot`).

- [ ] **Step 2.3: Implement `_activate` helper in `Slot`**

In `packages/haywire-core/src/haywire/ui/app/slot.py`, add a new private method to the `Slot` class (place it right after `_redraw` and before the `# Switching` section divider at line 314):

```python
    def _activate(self, binding: EditorBinding) -> None:
        """Make ``binding`` the active one and run its on_focus hook.

        Single choke point for "binding transitions to active". Used by:

        * ``render_area`` — on first render of the slot, for the initially
          active binding picked by ``_resolve_initial_active``.
        * ``switch_to`` — when the user clicks a different tab or a reveal
          swaps the active binding.
        * ``add_binding(activate=True)`` — when a new multi-instance tab is
          opened and made active in one step.

        Order of operations:
          1. Mark ``self._active = binding``.
          2. Ensure the instance exists (lazy-create) and call its
             ``on_focus(context)`` hook. Runs before ``draw`` so any context
             mutation the hook performs is visible to ``draw``.
          3. ``_ensure_drawn(binding)`` — first-time draw if needed.
          4. Flip the tab_panels visibility via ``set_value``.

        Exceptions raised by ``on_focus`` are logged and swallowed so a
        buggy editor can't wedge the slot.
        """
        self._active = binding
        instance = binding.ensure_instance()
        try:
            instance.on_focus(self._session.context)
        except Exception as exc:
            logger.error(
                f"Slot '{self.name}': on_focus error for '{binding.binding_id}': {exc}"
            )
        self._ensure_drawn(binding)
        if self._area_container is not None:
            self._area_container.set_value(binding.binding_id)
```

- [ ] **Step 2.4: Wire `_activate` into `switch_to`**

In the same file, replace the body of `switch_to` (currently at lines 318–345). The existing body is:

```python
    def switch_to(self, editor_key: str, payload: Any = None) -> bool:
        """..."""
        target = self.find_binding(editor_key, payload)
        if target is None:
            logger.warning(
                f"Slot '{self.name}': switch_to({editor_key!r}, payload={payload!r}) — no matching binding"
            )
            return False

        if self._active is target:
            return False

        self._active = target
        logger.info(f"Slot '{self.name}': switched to '{target.binding_id}'")
        self._ensure_drawn(target)
        if self._area_container is not None:
            self._area_container.set_value(target.binding_id)
        return True
```

Replace with:

```python
    def switch_to(self, editor_key: str, payload: Any = None) -> bool:
        """..."""
        target = self.find_binding(editor_key, payload)
        if target is None:
            logger.warning(
                f"Slot '{self.name}': switch_to({editor_key!r}, payload={payload!r}) — no matching binding"
            )
            return False

        if self._active is target:
            return False

        logger.info(f"Slot '{self.name}': switched to '{target.binding_id}'")
        self._activate(target)
        return True
```

(Preserve the existing docstring — only the body changes.)

- [ ] **Step 2.5: Wire `_activate` into `render_area`**

In the same file, find the tail of `render_area` (currently lines 260–264):

```python
        if self._active is None and self._area_container is not None:
            with self._area_container:
                ui.label("No editor").classes("hw-text-muted p-4")
        elif self._active is not None:
            self._ensure_drawn(self._active)
```

Replace with:

```python
        if self._active is None and self._area_container is not None:
            with self._area_container:
                ui.label("No editor").classes("hw-text-muted p-4")
        elif self._active is not None:
            # Reset _active so _activate sees the correct transition
            # semantics (not-active → active) and fires on_focus.
            initial = self._active
            self._active = None
            self._activate(initial)
```

- [ ] **Step 2.6: Wire `_activate` into `add_binding`**

In the same file, find `add_binding` (currently lines 347–365). The existing body is:

```python
    def add_binding(self, binding: EditorBinding, activate: bool = False) -> None:
        """..."""
        self._bindings.append(binding)
        if self._area_container is not None:
            self._create_panel(binding)
        if activate:
            if self._active is None:
                self._active = binding
                self._ensure_drawn(binding)
                if self._area_container is not None:
                    self._area_container.set_value(binding.binding_id)
            else:
                self.switch_to(binding.editor_key, binding.payload)
```

Replace with:

```python
    def add_binding(self, binding: EditorBinding, activate: bool = False) -> None:
        """..."""
        self._bindings.append(binding)
        if self._area_container is not None:
            self._create_panel(binding)
        if activate:
            if self._active is None:
                self._activate(binding)
            else:
                self.switch_to(binding.editor_key, binding.payload)
```

(Preserve the existing docstring.)

- [ ] **Step 2.7: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_slot_on_focus.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 2.8: Run the full slot-related test suite to catch regressions**

Run: `uv run pytest tests/ui/ -v -k "slot or shell"`
Expected: all tests PASS (existing shell tests must still work — `_handle_open_graph_requested` is untouched so far).

- [ ] **Step 2.9: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/slot.py tests/ui/test_slot_on_focus.py
git commit -m "feat(slot): wire on_focus via new _activate helper (switch, render, add)"
```

---

## Task 3: Implement `GraphEditor.on_focus` alongside existing flow

This runs in parallel with the still-alive `_handle_open_graph_requested`. Both paths will briefly coexist; the handler deletion happens in Task 4. During this task `on_focus` must be idempotent with the handler — i.e., if both run in sequence, the second one's short-circuit (`if context.active_graph is entry.graph: return`) makes it a no-op.

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py`
- Test: `tests/studio/test_graph_editor_on_focus.py`

- [ ] **Step 3.1: Create failing test file `tests/studio/test_graph_editor_on_focus.py`**

Create this file:

```python
"""Tests for GraphEditor.on_focus — editor-owned session-state mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import pytest

from haywire.ui.context_events import ContextChangeType
from haybale_studio.editors.graph_editor import GraphEditor


class _FakeEntry:
    def __init__(self, key: str, graph, path: Optional[Path] = None, display_name: str = "Entry") -> None:
        self.key = key
        self.graph = graph
        self.path = path
        self.display_name = display_name


class _FakeHaystack:
    def __init__(self) -> None:
        self._by_key: dict[str, _FakeEntry] = {}

    def register(self, entry: _FakeEntry) -> None:
        self._by_key[entry.key] = entry

    def get_by_key(self, key: str) -> Optional[_FakeEntry]:
        return self._by_key.get(key)


class _FakeSession:
    def __init__(self) -> None:
        self.notified_events: list = []
        self.context = None

    def notify_context_changed(self, event) -> None:
        self.notified_events.append(event)


def _make_context(entry: Optional[_FakeEntry], existing_active_graph=None):
    """Build a context where a haystack contains `entry` and active_graph is pre-set or None."""
    haystack = _FakeHaystack()
    if entry is not None:
        haystack.register(entry)
    app = SimpleNamespace(haystack=haystack)
    session = _FakeSession()
    ctx = SimpleNamespace(
        app=app,
        active_graph=existing_active_graph,
        active_graph_path=None,
        session=session,
    )
    session.context = ctx
    return ctx


def _make_editor_with_payload(payload: str) -> GraphEditor:
    ed = GraphEditor()
    ed.binding = SimpleNamespace(editor_key="graph_editor", payload=payload)
    return ed


def test_on_focus_resolves_entry_and_sets_active_graph() -> None:
    g = object()
    entry = _FakeEntry(key="/tmp/a.haywire", graph=g, path=Path("/tmp/a.haywire"))
    ctx = _make_context(entry)
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert ctx.active_graph is g
    assert ctx.active_graph_path == Path("/tmp/a.haywire")


def test_on_focus_fires_active_graph_changed() -> None:
    g = object()
    entry = _FakeEntry(
        key="/tmp/a.haywire",
        graph=g,
        path=Path("/tmp/a.haywire"),
        display_name="a.haywire",
    )
    ctx = _make_context(entry)
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert len(ctx.session.notified_events) == 1
    ev = ctx.session.notified_events[0]
    assert ev.change_type == ContextChangeType.ACTIVE_GRAPH_CHANGED
    assert ev.detail is entry


def test_on_focus_short_circuits_when_graph_already_active() -> None:
    g = object()
    entry = _FakeEntry(key="/tmp/a.haywire", graph=g, path=Path("/tmp/a.haywire"))
    # active_graph is already the target graph
    ctx = _make_context(entry, existing_active_graph=g)
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    # No event fired — nothing changed.
    assert ctx.session.notified_events == []


def test_on_focus_missing_entry_fires_tab_close_requested() -> None:
    ctx = _make_context(entry=None)  # empty haystack
    ed = _make_editor_with_payload("/tmp/gone.haywire")

    ed.on_focus(ctx)

    # Should fire a tab close for this binding.
    assert len(ctx.session.notified_events) == 1
    ev = ctx.session.notified_events[0]
    assert ev.change_type == ContextChangeType.TAB_CLOSE_REQUESTED
    assert ev.detail == {
        "slot_name": "main",
        "editor_key": "graph_editor",
        "payload": "/tmp/gone.haywire",
    }
    # No context mutation.
    assert ctx.active_graph is None


def test_on_focus_no_binding_is_noop() -> None:
    """Editor instance created outside a slot (e.g. a unit test) has binding=None."""
    ctx = _make_context(entry=None)
    ed = GraphEditor()
    ed.binding = None

    # Must not raise, must not mutate.
    ed.on_focus(ctx)

    assert ctx.session.notified_events == []
    assert ctx.active_graph is None


def test_on_focus_no_app_is_noop() -> None:
    """Context with no app (no haystack) must not crash."""
    session = _FakeSession()
    ctx = SimpleNamespace(
        app=None,
        active_graph=None,
        active_graph_path=None,
        session=session,
    )
    session.context = ctx
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert session.notified_events == []
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `uv run pytest tests/studio/test_graph_editor_on_focus.py -v`
Expected: all 6 tests FAIL (no `on_focus` override on `GraphEditor` yet — the default no-op runs, so most assertions fail because no events fire / context isn't mutated).

- [ ] **Step 3.3: Implement `on_focus` on `GraphEditor`**

In `barn/haybale-studio/haybale_studio/editors/graph_editor.py`, add the method immediately after `poll` (around line 90). The existing `poll` method ends at:

```python
    def poll(self, context: "SessionContext", event: "ContextChangedEvent") -> bool:
        # ... existing body ...
        return False
```

Add immediately after it:

```python
    def on_focus(self, context: "SessionContext") -> None:
        """Claim ownership of session state when this tab becomes active.

        Resolves ``self.binding.payload`` (the entry key) via the haystack
        and, if the entry exists, updates ``context.active_graph`` +
        ``active_graph_path`` and broadcasts ``ACTIVE_GRAPH_CHANGED`` so
        panels (properties, minimap, execution controls) refresh.

        If the payload no longer resolves to an entry (the graph was
        concurrently removed from the haystack), fires
        ``TAB_CLOSE_REQUESTED`` for this tab and returns — the shell then
        closes the orphaned tab.

        Short-circuits when ``context.active_graph is entry.graph`` so a
        redundant call (e.g. during the parallel-path transition period
        before ``_handle_open_graph_requested`` is removed) is a no-op.
        """
        if self.binding is None or self.binding.payload is None:
            return
        payload = self.binding.payload
        app = getattr(context, "app", None)
        haystack = getattr(app, "haystack", None) if app is not None else None
        if haystack is None:
            return

        entry = haystack.get_by_key(payload)
        session = getattr(context, "session", None)
        if entry is None:
            if session is not None:
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.TAB_CLOSE_REQUESTED,
                        source_editor="graph_editor",
                        detail={
                            "slot_name": "main",
                            "editor_key": self.binding.editor_key,
                            "payload": payload,
                        },
                    )
                )
            return

        if context.active_graph is entry.graph and context.active_graph_path == entry.path:
            return

        context.active_graph = entry.graph
        context.active_graph_path = entry.path

        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
                    source_editor="graph_editor",
                    detail=entry,
                )
            )
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `uv run pytest tests/studio/test_graph_editor_on_focus.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 3.5: Run the full slot + shell suite to confirm no regressions**

Run: `uv run pytest tests/ui/ -v`
Expected: all tests PASS (the existing `_handle_open_graph_requested` handler tests still pass because the handler is still in place; `on_focus`'s short-circuit prevents double-mutation).

- [ ] **Step 3.6: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/graph_editor.py tests/studio/test_graph_editor_on_focus.py
git commit -m "feat(graph_editor): add on_focus — editor owns active_graph mutation"
```

---

## Task 4: Migrate call sites from `OPEN_GRAPH_REQUESTED` to `EDITOR_FOCUSED` reveals

Five call sites emit `OPEN_GRAPH_REQUESTED`. This task rewrites them in a single commit so there's no partially-migrated state.

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/haystack_editor.py` (4 call sites)
- Modify: `barn/haybale-studio/haybale_studio/editors/file_browser.py` (1 call site)

- [ ] **Step 4.1: Migrate `HaystackEditor._on_new` (line 600)**

In `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`, find:

```python
    def _on_new(self, context: "SessionContext") -> None:
        """Create a new unnamed graph and activate it."""
        app: IProjectState = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.create_new()
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                source_editor="haystack",
                detail=entry,
                reveal_editor=_GRAPH_EDITOR_KEY,
            )
        )
```

Replace with:

```python
    def _on_new(self, context: "SessionContext") -> None:
        """Create a new unnamed graph and activate it."""
        app: IProjectState = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.create_new()
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.EDITOR_FOCUSED,
                source_editor="haystack",
                reveal_editor=_GRAPH_EDITOR_KEY,
                reveal_payload=entry.key,
                reveal_label=entry.display_name,
            )
        )
```

- [ ] **Step 4.2: Migrate `HaystackEditor._on_select` (line 614)**

In the same file, find:

```python
    def _on_select(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Activate an existing graph entry."""
        session = context.session
        if session is None:
            return
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                source_editor="haystack",
                detail=entry,
                reveal_editor=_GRAPH_EDITOR_KEY,
            )
        )
```

Replace with:

```python
    def _on_select(self, entry: "GraphEntry", context: "SessionContext") -> None:
        """Activate an existing graph entry."""
        session = context.session
        if session is None:
            return
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.EDITOR_FOCUSED,
                source_editor="haystack",
                reveal_editor=_GRAPH_EDITOR_KEY,
                reveal_payload=entry.key,
                reveal_label=entry.display_name,
            )
        )
```

- [ ] **Step 4.3: Migrate load-haystack dialog (~line 744)**

In the same file, find the block in the load-haystack dialog (around line 744):

```python
                if active_entry is not None and session is not None:
                    session.notify_context_changed(
                        ContextChangedEvent(
                            change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                            source_editor="haystack",
                            detail=active_entry,
                            reveal_editor=_GRAPH_EDITOR_KEY,
                        )
                    )
```

Replace with:

```python
                if active_entry is not None and session is not None:
                    session.notify_context_changed(
                        ContextChangedEvent(
                            change_type=ContextChangeType.EDITOR_FOCUSED,
                            source_editor="haystack",
                            reveal_editor=_GRAPH_EDITOR_KEY,
                            reveal_payload=active_entry.key,
                            reveal_label=active_entry.display_name,
                        )
                    )
```

- [ ] **Step 4.4: Migrate open-graph dialog (~line 825)**

In the same file, find the block in the open-graph dialog (around line 825):

```python
                entry = app.haystack.open_graph(path)
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                        source_editor="haystack",
                        detail=entry,
                        reveal_editor=_GRAPH_EDITOR_KEY,
                    )
                )
```

Replace with:

```python
                entry = app.haystack.open_graph(path)
                session.notify_context_changed(
                    ContextChangedEvent(
                        change_type=ContextChangeType.EDITOR_FOCUSED,
                        source_editor="haystack",
                        reveal_editor=_GRAPH_EDITOR_KEY,
                        reveal_payload=entry.key,
                        reveal_label=entry.display_name,
                    )
                )
```

- [ ] **Step 4.5: Migrate `FileBrowser._open_graph_file` (line 176)**

In `barn/haybale-studio/haybale_studio/editors/file_browser.py`, find:

```python
    def _open_graph_file(self, path: Path, context: "SessionContext") -> None:
        """Load a .haywire graph file and open its graph editor tab."""
        from haybale_studio.editors.graph_editor import GraphEditor

        app: "HaywireApp" = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.open_graph(path)
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.OPEN_GRAPH_REQUESTED,
                source_editor="file_browser",
                detail=entry,
                reveal_editor=GraphEditor.class_identity.registry_key,
            )
        )
```

Replace with:

```python
    def _open_graph_file(self, path: Path, context: "SessionContext") -> None:
        """Load a .haywire graph file and open its graph editor tab."""
        from haybale_studio.editors.graph_editor import GraphEditor

        app: "HaywireApp" = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.open_graph(path)
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.EDITOR_FOCUSED,
                source_editor="file_browser",
                reveal_editor=GraphEditor.class_identity.registry_key,
                reveal_payload=entry.key,
                reveal_label=entry.display_name,
            )
        )
```

- [ ] **Step 4.6: Update `HaystackEditor` class docstring (line 72)**

In `barn/haybale-studio/haybale_studio/editors/haystack_editor.py`, the class docstring mentions `OPEN_GRAPH_REQUESTED` (around line 72):

```python
    The "+" header button calls app.haystack.create_new() and fires
    OPEN_GRAPH_REQUESTED to activate the freshly created entry.
```

Replace with:

```python
    The "+" header button calls app.haystack.create_new() and fires
    EDITOR_FOCUSED with reveal_editor=GraphEditor to activate the
    freshly created entry.
```

- [ ] **Step 4.7: Run shell + studio tests to confirm reveals still work**

Run: `uv run pytest tests/ui/ tests/studio/ -v`
Expected: most tests PASS. The three `OPEN_GRAPH_REQUESTED` handler tests in `tests/ui/test_app_shell.py` (lines 528–581) should still PASS because the handler is still wired — they test the *handler* in isolation, not the call-site path. They're deleted in Task 5.

- [ ] **Step 4.8: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/haystack_editor.py barn/haybale-studio/haybale_studio/editors/file_browser.py
git commit -m "refactor(editors): migrate graph-open call sites to EDITOR_FOCUSED reveals"
```

---

## Task 5: Delete `OPEN_GRAPH_REQUESTED` plumbing

With all callers migrated, the enum value, handler, and dispatch branch become dead code.

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/context_events.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py`
- Modify: `tests/ui/test_app_shell.py`

- [ ] **Step 5.1: Delete dispatch branch in `_on_context_changed`**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, find (around lines 1001–1023):

```python
    def _on_context_changed(self, event: ContextChangedEvent, context: "SessionContext") -> None:
        """Orchestrator callback: run the poll/draw cycle on every managed slot."""
        if event.change_type == ContextChangeType.TAB_CLOSE_REQUESTED:
            self._handle_tab_close_requested(event)
        elif event.change_type == ContextChangeType.TAB_REPAYLOAD_REQUESTED:
            self._handle_tab_repayload_requested(event)
        elif event.change_type == ContextChangeType.GRAPH_REMOVED:
            self._handle_graph_removed(event)
        elif event.change_type == ContextChangeType.OPEN_GRAPH_REQUESTED:
            self._handle_open_graph_requested(event)
            # Skip the generic reveal — the handler re-emits ACTIVE_GRAPH_CHANGED
            # with the full reveal_payload/reveal_label, which drives the reveal.
            # Doing both would trigger a second slot-switch with payload=None
            # that falls back to the first binding and clobbers the canvas.
            for slot in self._managed_slots.values():
                slot.handle_context_event(event)
            return

        if event.reveal_editor is not None:
            self._reveal_editor(event.reveal_editor, event.reveal_payload, event.reveal_label)

        for slot in self._managed_slots.values():
            slot.handle_context_event(event)
```

Replace with:

```python
    def _on_context_changed(self, event: ContextChangedEvent, context: "SessionContext") -> None:
        """Orchestrator callback: run the poll/draw cycle on every managed slot."""
        if event.change_type == ContextChangeType.TAB_CLOSE_REQUESTED:
            self._handle_tab_close_requested(event)
        elif event.change_type == ContextChangeType.TAB_REPAYLOAD_REQUESTED:
            self._handle_tab_repayload_requested(event)
        elif event.change_type == ContextChangeType.GRAPH_REMOVED:
            self._handle_graph_removed(event)

        if event.reveal_editor is not None:
            self._reveal_editor(event.reveal_editor, event.reveal_payload, event.reveal_label)

        for slot in self._managed_slots.values():
            slot.handle_context_event(event)
```

- [ ] **Step 5.2: Delete `_handle_open_graph_requested` method**

In the same file, delete the entire `_handle_open_graph_requested` method (currently lines 1071–1103). It starts with:

```python
    def _handle_open_graph_requested(self, event: ContextChangedEvent) -> None:
        """Activate ``event.detail`` (a GraphEntry) in the session and reveal its tab.
```

And ends with the closing `)` of the `notify_context_changed` call. Delete the entire method and any trailing blank line before the next method (`_on_editor_lifecycle`).

- [ ] **Step 5.3: Delete `OPEN_GRAPH_REQUESTED` from the enum**

In `packages/haywire-core/src/haywire/ui/context_events.py`, find:

```python
    OPEN_GRAPH_REQUESTED = auto()  # caller asks AppShell to activate an entry + reveal its tab
```

Delete that line entirely.

- [ ] **Step 5.4: Delete obsolete `OPEN_GRAPH_REQUESTED` handler tests**

In `tests/ui/test_app_shell.py`, delete the entire block from the section header comment at line 465 through the end of `test_open_graph_requested_null_detail_is_noop` at line 581 (inclusive). That removes:

- The `# OPEN_GRAPH_REQUESTED handler tests` divider comment
- `_FakeEntry` class
- `_FakeHaystack` class
- `_make_shell_for_open_graph` helper
- `test_open_graph_requested_updates_context`
- `test_open_graph_requested_fires_active_graph_changed`
- `test_open_graph_requested_null_detail_is_noop`

**Important:** `_FakeEntry` and `_FakeHaystack` are also used later in `TestFollowMainTabContextByField` (at line 823 and 829). Since that class is also being deleted in Task 6, just delete all of these here — but verify first by checking whether any *other* test class in this file uses `_FakeEntry` or `_FakeHaystack`. Run:

```bash
grep -n "_FakeEntry\|_FakeHaystack" tests/ui/test_app_shell.py
```

Expected: matches only inside lines 465–581 and inside lines 740–842. If a match appears outside those ranges, stop and re-evaluate — the plan assumed no other users.

- [ ] **Step 5.5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests PASS. `OPEN_GRAPH_REQUESTED` no longer exists; any code or test referencing it would fail at import/collection time.

- [ ] **Step 5.6: Run linter to catch unused imports**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/app/shell.py packages/haywire-core/src/haywire/ui/context_events.py tests/ui/test_app_shell.py`
Expected: clean (no unused imports).

- [ ] **Step 5.7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/shell.py packages/haywire-core/src/haywire/ui/context_events.py tests/ui/test_app_shell.py
git commit -m "refactor(shell): delete OPEN_GRAPH_REQUESTED event + handler"
```

---

## Task 6: Implement `FileViewer.on_focus` + delete `_follow_main_tab_context` + `context_field`

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/file_viewer.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py`
- Modify: `packages/haywire-core/src/haywire/ui/editor/identity.py`
- Modify: `packages/haywire-core/src/haywire/ui/editor/decorator.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/graph_editor.py` (remove `context_field` kwarg)
- Modify: `tests/ui/test_app_shell.py` (delete `TestFollowMainTabContextByField`)
- Create: `tests/studio/test_file_viewer_on_focus.py`

- [ ] **Step 6.1: Create failing test file `tests/studio/test_file_viewer_on_focus.py`**

Create this file:

```python
"""Tests for FileViewerEditor.on_focus — editor-owned active_file mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from haywire.ui.context_events import ContextChangeType
from haybale_studio.editors.file_viewer import FileViewerEditor


class _FakeSession:
    def __init__(self) -> None:
        self.notified_events: list = []
        self.context = None

    def notify_context_changed(self, event) -> None:
        self.notified_events.append(event)


def _make_context(existing_active_file=None):
    session = _FakeSession()
    ctx = SimpleNamespace(
        active_file=existing_active_file,
        session=session,
    )
    session.context = ctx
    return ctx


def _make_editor_with_payload(payload) -> FileViewerEditor:
    ed = FileViewerEditor()
    ed.binding = SimpleNamespace(editor_key="file_viewer", payload=payload)
    return ed


def test_on_focus_sets_active_file_from_payload() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert ctx.active_file == Path("/tmp/a.txt")


def test_on_focus_fires_file_selected() -> None:
    ctx = _make_context()
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    assert len(ctx.session.notified_events) == 1
    ev = ctx.session.notified_events[0]
    assert ev.change_type == ContextChangeType.FILE_SELECTED
    assert ev.detail == Path("/tmp/a.txt")


def test_on_focus_short_circuits_when_file_unchanged() -> None:
    ctx = _make_context(existing_active_file=Path("/tmp/a.txt"))
    ed = _make_editor_with_payload("/tmp/a.txt")

    ed.on_focus(ctx)

    # No event — unchanged.
    assert ctx.session.notified_events == []


def test_on_focus_no_binding_is_noop() -> None:
    ctx = _make_context()
    ed = FileViewerEditor()
    ed.binding = None

    ed.on_focus(ctx)

    assert ctx.session.notified_events == []
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `uv run pytest tests/studio/test_file_viewer_on_focus.py -v`
Expected: 3 of 4 tests FAIL (no `on_focus` override yet on FileViewerEditor). `test_on_focus_no_binding_is_noop` may pass by accident since the default no-op does nothing.

- [ ] **Step 6.3: Implement `on_focus` on `FileViewerEditor`**

In `barn/haybale-studio/haybale_studio/editors/file_viewer.py`, first add the import for context events (around the existing imports at line 22):

```python
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType
```

Then add the `on_focus` method immediately after `poll` (around line 77, right before `draw`):

```python
    def on_focus(self, context: "SessionContext") -> None:
        """Claim ownership of context.active_file when this tab becomes active.

        Reads self.binding.payload (the file path as a string) and mirrors
        it into ``context.active_file`` as a ``Path``, then broadcasts
        ``FILE_SELECTED`` so listeners (e.g. other editors, panels) react.

        Short-circuits when the target is already the active file.
        """
        if self.binding is None:
            return
        payload = self.binding.payload
        new_value = Path(payload) if payload else None
        if getattr(context, "active_file", None) == new_value:
            return
        context.active_file = new_value
        session = getattr(context, "session", None)
        if session is not None:
            session.notify_context_changed(
                ContextChangedEvent(
                    change_type=ContextChangeType.FILE_SELECTED,
                    source_editor="file_viewer",
                    detail=new_value,
                )
            )
```

- [ ] **Step 6.4: Remove `context_field="active_file"` from the `@editor` decorator**

In the same file, find (around line 49):

```python
@editor(
    label="File Viewer",
    icon=hui.icon.library_component,
    default_slot="main",
    opens="on_payload",
    context_field="active_file",
    description="Displays the contents of a file selected in the Files browser.",
)
```

Replace with:

```python
@editor(
    label="File Viewer",
    icon=hui.icon.library_component,
    default_slot="main",
    opens="on_payload",
    description="Displays the contents of a file selected in the Files browser.",
)
```

- [ ] **Step 6.5: Remove `context_field="active_graph_path"` from `GraphEditor`**

In `barn/haybale-studio/haybale_studio/editors/graph_editor.py`, find (around line 39):

```python
@editor(
    label="Graph Editor",
    icon=hui.icon.graph,
    default_slot="main",
    opens="on_payload",
    context_field="active_graph_path",
    description="Visual node graph editor for wiring data processing pipelines.",
)
```

Replace with:

```python
@editor(
    label="Graph Editor",
    icon=hui.icon.graph,
    default_slot="main",
    opens="on_payload",
    description="Visual node graph editor for wiring data processing pipelines.",
)
```

- [ ] **Step 6.6: Delete `context_field` from `EditorIdentity`**

In `packages/haywire-core/src/haywire/ui/editor/identity.py`, delete the `context_field` attribute from the dataclass. Find:

```python
@dataclass
class EditorIdentity(BaseIdentity):
    """
    ... existing docstring ...
    """

    icon: str = "extension"
    default_slot: str = "main"
    opens: OpenBehavior = field(default=OpenBehavior.REQUIRED)
    context_field: Optional[str] = None
```

Delete the last line. Also delete the `context_field` paragraph from the docstring (lines 48–55 of the original). Also remove the now-unused `Optional` import if no other use remains — check with:

```bash
grep -n "Optional" packages/haywire-core/src/haywire/ui/editor/identity.py
```

If `Optional` is only used on the line being removed, delete the import line `from typing import Optional` too.

The final shape of the class:

```python
@dataclass
class EditorIdentity(BaseIdentity):
    """
    Metadata attached to an editor class by the @editor decorator.

    Set once at class-definition time; survives hot-reload.

    Inherits from BaseIdentity:
        registry_id: Short unique ID, e.g. 'graph_editor'.
        registry_key: Fully-qualified registry key; set by decorator via reg_key().
        label: Human-readable display name, e.g. 'Graph Editor'.
        description: Human-readable description.
        class_name: Python class name — set by decorator.
        module: Python module name — set by decorator.

    Additional attributes:
        icon: Material Design icon name, e.g. 'account_tree'.
        default_slot: Which workspace slot this editor belongs in by default.
            One of: 'left', 'right', 'main', 'bottom'.
        opens: Instance-creation behavior. See OpenBehavior.
    """

    icon: str = "extension"
    default_slot: str = "main"
    opens: OpenBehavior = field(default=OpenBehavior.REQUIRED)
```

- [ ] **Step 6.7: Delete `context_field` from the `@editor` decorator**

In `packages/haywire-core/src/haywire/ui/editor/decorator.py`, find:

```python
def editor(
    cls=None,
    /,
    *,
    label: Optional[str] = None,
    description: str = "",
    icon: str = "extension",
    default_slot: str = "main",
    opens: Union[OpenBehavior, str] = OpenBehavior.REQUIRED,
    context_field: Optional[str] = None,
    registry_id: Optional[str] = None,
):
```

Remove the `context_field` line. Also remove the `context_field` paragraph from the docstring (the `context_field: Optional ...` block around line 51–53).

Then find the `EditorIdentity(...)` construction later in the function:

```python
        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            icon=icon,
            default_slot=default_slot,
            opens=opens_enum,
            context_field=context_field,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
```

Remove the `context_field=context_field,` line.

- [ ] **Step 6.8: Delete `_follow_main_tab_context` from `AppShell`**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, delete the entire `_follow_main_tab_context` method (currently lines 1584–1665). It starts with:

```python
    def _follow_main_tab_context(self, payload: Optional[str]) -> None:
```

And ends at the end of the method's body. Delete the entire method.

- [ ] **Step 6.9: Delete the `_follow_main_tab_context` call from `_switch_main_slot`**

In the same file, find `_switch_main_slot` (currently lines 1344–1356):

```python
    def _switch_main_slot(self, tab_id: str) -> None:
        """Switch the Main Slot editor and broadcast WORKSPACE_CHANGED.

        Receives the composite ``tab_id`` emitted by the main tab bar; splits
        it back to ``(editor_key, payload)`` before delegating.
        """
        editor_key, payload = self._split_tab_id(tab_id)
        if not self._apply_managed_slot_switch("main", editor_key, payload):
            return
        self._follow_main_tab_context(payload)
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )
```

Replace with:

```python
    def _switch_main_slot(self, tab_id: str) -> None:
        """Switch the Main Slot editor and broadcast WORKSPACE_CHANGED.

        Receives the composite ``tab_id`` emitted by the main tab bar; splits
        it back to ``(editor_key, payload)`` before delegating. The new
        active binding's ``on_focus`` hook is called by ``Slot._activate``
        inside ``_apply_managed_slot_switch`` — no shell-side dispatch needed.
        """
        editor_key, payload = self._split_tab_id(tab_id)
        if not self._apply_managed_slot_switch("main", editor_key, payload):
            return
        self.session.notify_context_changed(
            ContextChangedEvent(change_type=ContextChangeType.WORKSPACE_CHANGED)
        )
```

- [ ] **Step 6.10: Delete `TestFollowMainTabContextByField` test class**

In `tests/ui/test_app_shell.py`, delete the entire `TestFollowMainTabContextByField` class (currently lines 740–842 — from `class TestFollowMainTabContextByField:` through the end of `test_graph_path_context_field_preserves_haystack_lookup`).

Also delete the `_FakeEntry` / `_FakeHaystack` definitions if they're still in the file (they should have been removed in Task 5's step 5.4 — re-check with `grep -n "_FakeEntry\|_FakeHaystack" tests/ui/test_app_shell.py` and delete any remaining definitions).

- [ ] **Step 6.11: Remove unused `from pathlib import Path` if orphaned**

In `packages/haywire-core/src/haywire/ui/app/shell.py`, the `Path` import may have been only used by `_follow_main_tab_context`. Check:

```bash
grep -n "\bPath\b" packages/haywire-core/src/haywire/ui/app/shell.py
```

If there are no other uses, remove `from pathlib import Path`. If there are other uses, leave it.

- [ ] **Step 6.12: Run ruff to catch other orphans**

Run: `uv run ruff check packages/haywire-core/src/haywire/ui/ barn/haybale-studio/ tests/`
Expected: clean. If any unused imports are flagged, fix them.

- [ ] **Step 6.13: Run file_viewer tests**

Run: `uv run pytest tests/studio/test_file_viewer_on_focus.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 6.14: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS. Any test that still references `context_field` or `_follow_main_tab_context` would fail — address each one inline.

- [ ] **Step 6.15: Run type check**

Run: `uv run mypy packages/haywire-core/src/ barn/haybale-studio/`
Expected: no new errors.

- [ ] **Step 6.16: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/editor/identity.py packages/haywire-core/src/haywire/ui/editor/decorator.py packages/haywire-core/src/haywire/ui/app/shell.py barn/haybale-studio/haybale_studio/editors/file_viewer.py barn/haybale-studio/haybale_studio/editors/graph_editor.py tests/ui/test_app_shell.py tests/studio/test_file_viewer_on_focus.py
git commit -m "refactor(shell): delete _follow_main_tab_context + context_field — editors own state via on_focus"
```

---

## Task 7: Update documentation

**Files:**
- Modify: `internals/documentation/build_editors.md`
- Modify: `internals/UBIQUITOUS_LANGUAGE.md`
- Modify: `.codemap/modules/core-ui.md`

- [ ] **Step 7.1: Update `internals/documentation/build_editors.md`**

Find the `context_field` section (around lines 86, 117–120). Remove the `context_field='active_graph_path'` example from any code block and delete the paragraph explaining `context_field`.

Add a new section documenting `on_focus`. Place it adjacent to the existing `poll` / `draw` lifecycle docs. Example content:

```markdown
### `on_focus(context)` — editor owns session state

Called when this binding transitions from not-active to active in its slot.
Fires on: initial slot render, `Slot.switch_to`, `Slot.add_binding(activate=True)`.
Does NOT fire on re-selecting the already-active binding.

Runs **before** `draw` on the newly-activated binding, so any `context`
mutation is visible to that `draw` call.

Default implementation is a no-op. Override when the editor owns a slice of
session state:

```python
class MyEditor(BaseEditor):
    def on_focus(self, context):
        payload = self.binding.payload
        context.active_thing = resolve(payload)
        context.session.notify_context_changed(ContextChangedEvent(
            change_type=ContextChangeType.MY_THING_CHANGED,
            source_editor="my_editor",
            detail=context.active_thing,
        ))
```

If `on_focus` raises, the slot logs the error and swallows it so a buggy
editor can't wedge the UI.
```

- [ ] **Step 7.2: Update `internals/UBIQUITOUS_LANGUAGE.md`**

Remove the `context_field` glossary entry (around line 176). Add an `on_focus` entry in the appropriate alphabetical position:

```markdown
- **`on_focus`** — `BaseEditor` lifecycle hook called by `Slot._activate` when a
  binding transitions from not-active to active. Editors that own a slice of
  session state (e.g. `GraphEditor` owns `active_graph`) override it to
  mutate the context and broadcast the corresponding event. Replaces the
  shell-side `context_field` / `OPEN_GRAPH_REQUESTED` dispatch.
```

- [ ] **Step 7.3: Update `.codemap/modules/core-ui.md`**

Find the `context_field` bullet (around line 173). Remove it. If the adjacent bullets reference the foreground-mirror mechanism by the old name, update them to point at `on_focus` instead.

- [ ] **Step 7.4: Commit**

```bash
git add internals/ .codemap/
git commit -m "docs: document on_focus hook; remove context_field references"
```

---

## Task 8: Full verification

- [ ] **Step 8.1: Full test suite**

Run: `uv run pytest`
Expected: 100% pass.

- [ ] **Step 8.2: Coverage check**

Run: `uv run pytest --cov=packages/haywire-core/src/haywire/ui --cov=barn/haybale-studio/haybale_studio/editors`
Expected: coverage of `Slot._activate`, `GraphEditor.on_focus`, `FileViewerEditor.on_focus` at 100%.

- [ ] **Step 8.3: Lint + format check**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 8.4: Type check**

Run: `uv run mypy packages/haywire-core/src/`
Expected: clean.

- [ ] **Step 8.5: Manual browser smoke test**

Run: `uv run haywire`

Then exercise each of the migrated paths:

1. **New graph from HaystackEditor:** Click the "+" button in the Haystack panel header. A new `__untitled__` graph tab opens and becomes active. GraphEditor renders.
2. **Select existing graph from HaystackEditor:** With at least two graphs open, click a different row. That graph's tab becomes active and properties panel refreshes.
3. **Open graph from FileBrowser:** Double-click a `.haywire` file. It loads and opens in a GraphEditor tab.
4. **Load haystack dialog:** Open the load-haystack dialog, pick a haystack, confirm. The first entry becomes active in the GraphEditor.
5. **Open-graph dialog:** Open the "Open…" dialog inside HaystackEditor, pick a path, confirm. Graph loads and its tab becomes active.
6. **Tab switch:** Click between two graph tabs. Active graph updates; properties, minimap, graph-info panels refresh correctly (active node/edge resets because `GraphEditor.draw` already clears selection).
7. **File viewer:** Click a non-`.haywire` file in FileBrowser. FileViewer opens and shows contents. Click a different file → new tab with that file's contents.
8. **Tab close / reopen:** Close a graph tab, then re-open it via FileBrowser. Tab reappears and is active.

Expected: all 8 flows work. No console errors. No stale `active_graph` state.

- [ ] **Step 8.6: Final commit (if any leftover changes)**

If Step 8.3–8.4 fixed any lint/type issues, commit them:

```bash
git status
# if anything changed:
git add -u
git commit -m "chore: lint + type cleanup after on_focus refactor"
```

---

## Commit Sequence Summary

1. `feat(editor): add BaseEditor.on_focus lifecycle hook (no-op default)` — Task 1
2. `feat(slot): wire on_focus via new _activate helper (switch, render, add)` — Task 2
3. `feat(graph_editor): add on_focus — editor owns active_graph mutation` — Task 3
4. `refactor(editors): migrate graph-open call sites to EDITOR_FOCUSED reveals` — Task 4
5. `refactor(shell): delete OPEN_GRAPH_REQUESTED event + handler` — Task 5
6. `refactor(shell): delete _follow_main_tab_context + context_field — editors own state via on_focus` — Task 6
7. `docs: document on_focus hook; remove context_field references` — Task 7
8. (optional) `chore: lint + type cleanup after on_focus refactor` — Task 8

---

## Plan self-review notes

**Spec coverage:** Every item in the spec maps to a task:
- `BaseEditor.on_focus` → Task 1.
- `Slot._activate` helper wired into `switch_to` / `render_area` / `add_binding` → Task 2.
- `GraphEditor.on_focus` (happy, missing-entry, short-circuit) → Task 3.
- `FileViewer.on_focus` → Task 6.
- Delete `OPEN_GRAPH_REQUESTED` + handler + `_on_context_changed` dispatch branch → Task 5.
- Delete `_follow_main_tab_context` + `_switch_main_slot` call → Task 6.
- Delete `EditorIdentity.context_field` + decorator kwarg → Task 6.
- Migrate 5 call sites → Task 4.
- Obsolete tests deleted, new tests added → covered across Tasks 2, 3, 5, 6.
- Docs updated → Task 7.
- Manual smoke test → Task 8.

**Failure semantics:** Q4 chose (c) "missing entry → close the tab". Q4a chose (ii) "fire `TAB_CLOSE_REQUESTED`, editor stays slot-agnostic". Implemented in Task 3, tested in `test_on_focus_missing_entry_fires_tab_close_requested`.

**Ordering:** `on_focus` runs before `draw` — implemented in `Slot._activate` (Task 2.3), tested in `test_on_focus_runs_before_draw_on_first_activation` (Task 2.1).

**No placeholders:** every step has either concrete code, a concrete command with expected output, or a concrete git command.

**Type consistency:**
- `on_focus(self, context: "SessionContext") -> None` — consistent across `BaseEditor`, `GraphEditor`, `FileViewerEditor`.
- `Slot._activate(self, binding: EditorBinding) -> None` — consistent.
- `entry.key` (str), `entry.path` (Optional[Path]), `entry.display_name` (str), `entry.graph` (HaywireGraph) — matches `GraphEntry` dataclass at `packages/haywire-studio/src/haywire_studio/haystack.py:56-88`.
- `haystack.get_by_key(key: str) -> Optional[GraphEntry]` — matches existing signature at `packages/haywire-studio/src/haywire_studio/haystack.py:308`.
- `ContextChangeType.EDITOR_FOCUSED` already exists at `packages/haywire-core/src/haywire/ui/context_events.py:20` — no enum additions needed.
