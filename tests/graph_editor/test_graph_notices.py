"""Graph notices and the graphs listener on GraphAppState."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager

from haybale_graph_editor.notices import GraphNotice, GraphNoticesChanged
from haybale_graph_editor.states.graph_app_state import GraphAppState


@dataclass
class _Editor:
    graph: object = None
    history_manager: Any = field(default_factory=NoOpHistoryManager)


@dataclass
class _Container:
    binding_id: str
    editor: Any = field(default_factory=_Editor)


class _Loop:
    def is_running(self) -> bool:
        return True

    def call_soon_threadsafe(self, fn: Any, *args: Any) -> None:
        fn(*args)


@pytest.fixture
def app_state(monkeypatch):
    from nicegui import core

    monkeypatch.setattr(core, "loop", _Loop())
    state = GraphAppState()
    monkeypatch.setattr(state, "_signal_emit", lambda signal: None)
    return state


@pytest.fixture
def emitted(app_state, monkeypatch):
    signals: list[Any] = []
    monkeypatch.setattr(app_state, "_signal_emit", signals.append)
    return signals


@pytest.fixture
def container():
    return cast(Any, _Container("a"))


def test_post_replace_retract(app_state, container):
    app_state.register(container)
    app_state.post_notice(container.binding_id, GraphNotice("lib:a", "one"))
    app_state.post_notice(container.binding_id, GraphNotice("lib:a", "two"))
    assert [n.text for n in app_state.notices(container.binding_id)] == ["two"]
    app_state.retract_notice(container.binding_id, "lib:a")
    assert app_state.notices(container.binding_id) == []


def test_insertion_order(app_state, container):
    app_state.register(container)
    app_state.post_notice("a", GraphNotice("k1", "1"))
    app_state.post_notice("a", GraphNotice("k2", "2"))
    assert [n.key for n in app_state.notices("a")] == ["k1", "k2"]


def test_unregister_drops_and_rekey_moves_notices(app_state, container):
    app_state.register(container)
    app_state.post_notice("a", GraphNotice("k", "t"))
    app_state.rekey("a", "b")
    assert app_state.notices("a") == []
    assert [n.key for n in app_state.notices("b")] == ["k"]
    app_state.unregister("b")
    assert app_state.notices("b") == []
    app_state.register(cast(Any, _Container("b")))
    assert app_state.notices("b") == []


def test_post_to_unknown_binding_is_ignored(app_state, emitted):
    app_state.post_notice("nope", GraphNotice("k", "t"))
    assert app_state.notices("nope") == []
    assert emitted == []


def test_retract_is_idempotent(app_state, container, emitted):
    app_state.register(container)
    app_state.retract_notice("a", "missing")
    app_state.retract_notice("nope", "missing")
    assert emitted == []


def test_graphs_listener_fires_on_register_unregister_rekey(app_state, container):
    calls: list[int] = []
    app_state.add_graphs_listener(lambda: calls.append(1))
    app_state.register(container)
    app_state.rekey("a", "b")
    app_state.unregister("b")
    assert len(calls) == 3


def test_remove_graphs_listener(app_state, container):
    calls: list[int] = []

    def cb() -> None:
        calls.append(1)

    app_state.add_graphs_listener(cb)
    app_state.remove_graphs_listener(cb)
    app_state.remove_graphs_listener(cb)
    app_state.register(container)
    assert calls == []


def test_raising_listener_does_not_block_others(app_state, container):
    calls: list[int] = []

    def bad() -> None:
        raise RuntimeError("boom")

    app_state.add_graphs_listener(bad)
    app_state.add_graphs_listener(lambda: calls.append(1))
    app_state.register(container)
    assert calls == [1]


def test_changes_emit_once_and_identical_repost_emits_nothing(app_state, container, emitted):
    app_state.register(container)
    n = GraphNotice("k", "t")
    app_state.post_notice("a", n)
    assert len(emitted) == 1
    assert isinstance(emitted[0], GraphNoticesChanged)
    app_state.post_notice("a", GraphNotice("k", "t"))
    assert len(emitted) == 1
    app_state.post_notice("a", GraphNotice("k", "t2"))
    assert len(emitted) == 2
    app_state.retract_notice("a", "k")
    assert len(emitted) == 3


def test_unregister_with_notices_emits(app_state, container, emitted):
    app_state.register(container)
    app_state.post_notice("a", GraphNotice("k", "t"))
    emitted.clear()
    app_state.unregister("a")
    assert len(emitted) == 1


def test_cross_session():
    assert GraphNoticesChanged.cross_session is True


def test_register_posts_compatibility_findings(app_state):
    graph = type("G", (), {"library_compatibility_findings": ["f0", "f1"]})()
    app_state.register(cast(Any, _Container("c", _Editor(graph=graph))))
    notices = app_state.notices("c")
    assert [n.key for n in notices] == ["haywire:compatibility:0", "haywire:compatibility:1"]
    assert [n.text for n in notices] == ["f0", "f1"]
    assert all(n.dismissable for n in notices)
