"""Tests for GraphEditor.on_focus — editor-owned session-state mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from haywire.ui.context_events import ContextChangeType
from haybale_studio.editors.graph_editor import GraphEditor


class _FakeEntry:
    def __init__(
        self, entry_id: str, graph, path: Optional[Path] = None, display_name: str = "Entry"
    ) -> None:
        self.entry_id = entry_id
        self.graph = graph
        self.path = path
        self.display_name = display_name


class _FakeHaystack:
    def __init__(self) -> None:
        self._by_id: dict[str, _FakeEntry] = {}

    def register(self, entry: _FakeEntry) -> None:
        self._by_id[entry.entry_id] = entry

    def get_by_id(self, entry_id: str) -> Optional[_FakeEntry]:
        return self._by_id.get(entry_id)


class _FakeSession:
    def __init__(self) -> None:
        self.notified_events: list = []
        self.context = None

    def notify_context_changed(self, event) -> None:
        self.notified_events.append(event)


def _make_context(entry: Optional[_FakeEntry], existing_active_graph=None):
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
    entry = _FakeEntry(entry_id="/tmp/a.haywire", graph=g, path=Path("/tmp/a.haywire"))
    ctx = _make_context(entry)
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert ctx.active_graph is g
    assert ctx.active_graph_path == Path("/tmp/a.haywire")


def test_on_focus_fires_active_graph_changed() -> None:
    g = object()
    entry = _FakeEntry(
        entry_id="/tmp/a.haywire",
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
    entry = _FakeEntry(entry_id="/tmp/a.haywire", graph=g, path=Path("/tmp/a.haywire"))
    ctx = _make_context(entry, existing_active_graph=g)
    # Also pre-set active_graph_path to match — the short-circuit requires both.
    ctx.active_graph_path = Path("/tmp/a.haywire")
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert ctx.session.notified_events == []


def test_on_focus_missing_entry_fires_tab_close_requested() -> None:
    ctx = _make_context(entry=None)
    ed = _make_editor_with_payload("/tmp/gone.haywire")

    ed.on_focus(ctx)

    assert len(ctx.session.notified_events) == 1
    ev = ctx.session.notified_events[0]
    assert ev.change_type == ContextChangeType.TAB_CLOSE_REQUESTED
    assert ev.detail == {
        "slot_name": "main",
        "editor_key": "graph_editor",
        "payload": "/tmp/gone.haywire",
    }
    assert ctx.active_graph is None


def test_on_focus_no_binding_is_noop() -> None:
    ctx = _make_context(entry=None)
    ed = GraphEditor()
    ed.binding = None

    ed.on_focus(ctx)

    assert ctx.session.notified_events == []
    assert ctx.active_graph is None


def test_on_focus_no_app_is_noop() -> None:
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
