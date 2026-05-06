"""Tests for GraphEditor.on_focus — editor-owned session-state mutation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

from haywire.ui.context_signals import ActiveGraphMoved
from haywire.ui.reactive import Reactive
from haybale_studio.editors.graph_editor import GraphEditor


def _make_data_with_edit_state(initial_active_graph=None, initial_active_graph_path=None):
    """Build a fake ``ctx.data`` whose ``[EditState]`` lookup yields a stub.

    GraphEditor.on_focus reads and writes via
    ``ctx.data[EditState].active_graph``. Returns a MagicMock whose
    ``__getitem__`` (regardless of the EditState class identity passed —
    important after library hot-reload swaps in a new class object)
    returns a SimpleNamespace whose ``.active_graph`` and
    ``.active_graph_path`` are real Reactive[T] instances. Tests read
    assertions against this stub.
    """
    edit_stub = SimpleNamespace(
        active_graph=Reactive(initial_active_graph),
        active_graph_path=Reactive(initial_active_graph_path),
        active_node=Reactive(None),
        active_edge=Reactive(None),
        active_port=Reactive(None),
        selected_nodes=Reactive(set()),
        selected_edges=Reactive(set()),
        clipboard=Reactive(None),
    )
    data = MagicMock()
    data.__getitem__.return_value = edit_stub
    # Expose the stub directly so callers can use it without importing
    # EditState (and re-resolving across reloads).
    data.edit_stub = edit_stub
    return data


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
        self.signals: list = []
        self.context = None

    def signal(self, signal) -> None:
        self.signals.append(signal)


def _make_context(entry: Optional[_FakeEntry], existing_active_graph=None):
    haystack = _FakeHaystack()
    if entry is not None:
        haystack.register(entry)
    app = SimpleNamespace(haystack=haystack)
    session = _FakeSession()
    # GraphEditor.on_focus reads/writes active_graph via
    # ctx.data[EditState]. Build a fake `data` whose `[EditState]` lookup
    # yields a stub with real Reactive fields.
    data = _make_data_with_edit_state(
        initial_active_graph=existing_active_graph,
    )
    ctx = SimpleNamespace(
        app=app,
        active_graph=Reactive(existing_active_graph),
        active_graph_path=Reactive(None),
        session=session,
        data=data,
    )
    session.context = ctx
    return ctx


def _make_editor_with_payload(payload: str) -> GraphEditor:
    ed = GraphEditor()

    force_close_calls: list = []

    def _force_close():
        force_close_calls.append(True)

    ed.wrapper = SimpleNamespace(
        editor_key="graph_editor",
        payload=payload,
        force_close=_force_close,
        force_close_calls=force_close_calls,
    )
    return ed


def test_on_focus_resolves_entry_and_sets_active_graph() -> None:
    g = object()
    entry = _FakeEntry(entry_id="/tmp/a.haywire", graph=g, path=Path("/tmp/a.haywire"))
    ctx = _make_context(entry)
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    edit = ctx.data.edit_stub
    assert edit.active_graph.value is g
    assert edit.active_graph_path.value == Path("/tmp/a.haywire")


def test_on_focus_fires_active_graph_moved() -> None:
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

    assert len(ctx.session.signals) == 1
    assert isinstance(ctx.session.signals[0], ActiveGraphMoved)


def test_on_focus_short_circuits_when_graph_already_active() -> None:
    g = object()
    entry = _FakeEntry(entry_id="/tmp/a.haywire", graph=g, path=Path("/tmp/a.haywire"))
    ctx = _make_context(entry, existing_active_graph=g)
    # Also pre-set active_graph_path to match — the short-circuit requires both.
    # Reader sources from EditState (post-C3).
    ctx.data.edit_stub.active_graph_path.value = Path("/tmp/a.haywire")
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert ctx.session.signals == []


def test_on_focus_missing_entry_force_closes_via_wrapper() -> None:
    ctx = _make_context(entry=None)
    ed = _make_editor_with_payload("/tmp/gone.haywire")

    ed.on_focus(ctx)

    # Editor closes itself via wrapper.force_close — no event emitted.
    assert ctx.session.signals == []
    assert ed.wrapper.force_close_calls == [True]
    assert ctx.data.edit_stub.active_graph.value is None


def test_on_focus_no_binding_is_noop() -> None:
    ctx = _make_context(entry=None)
    ed = GraphEditor()
    ed.wrapper = None

    ed.on_focus(ctx)

    assert ctx.session.signals == []
    assert ctx.data.edit_stub.active_graph.value is None


def test_on_focus_no_app_is_noop() -> None:
    session = _FakeSession()
    ctx = SimpleNamespace(
        app=None,
        active_graph=Reactive(None),
        active_graph_path=Reactive(None),
        session=session,
        data=_make_data_with_edit_state(),
    )
    session.context = ctx
    ed = _make_editor_with_payload("/tmp/a.haywire")

    ed.on_focus(ctx)

    assert session.signals == []
