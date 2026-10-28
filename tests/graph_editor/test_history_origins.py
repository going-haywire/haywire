"""Who the graph editor credits steps to, and the bridge from a file's history to ``GraphHistoryChanged``."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from haywire.core.graph.editor import Editor
from haywire.core.signals import GraphHistoryChanged
from haywire.core.undo.config import UndoConfig
from haywire.core.undo.history_manager import HistoryManager
from haywire.core.undo.origin import StepOrigin

from haybale_graph_editor.state.graph_app_state import GraphAppState

pytestmark = pytest.mark.unit


def _editor() -> Editor:
    return Editor(cast(Any, SimpleNamespace(graph_id="g")), cast(Any, None), UndoConfig())


def _container(binding_id: str, editor: Editor | None = None) -> Any:
    return SimpleNamespace(binding_id=binding_id, editor=editor or _editor())


def _history(container: Any) -> HistoryManager:
    return cast(HistoryManager, container.editor.history_manager)


# ---------------------------------------------------------------------------
# Origins
# ---------------------------------------------------------------------------


def test_a_session_origin_shortens_the_session_id():
    assert StepOrigin.of_session("alice", "3f2a9b1c") == StepOrigin("alice", "3f2a", "canvas")
    assert StepOrigin.of_session(None, "") == StepOrigin(None, None, "canvas")


def test_a_level_route_credits_the_session():
    from tests.graph_editor.test_graph_editor_levels import DOCUMENT_LEVEL, _editor as level_editor

    editor, context, _ = level_editor()

    route = editor._levels[DOCUMENT_LEVEL].route
    assert route is not None
    assert route.origin == StepOrigin.of_session(context.principal, context.session_id)


def test_a_farmhand_editor_credits_the_calling_principal():
    from haybale_graph_editor.farmhands import editor_tools

    container = _container("doc")
    ctx: Any = SimpleNamespace(principal="agent", state=lambda cls: SimpleNamespace(get=lambda b: container))

    editor = editor_tools._editor(ctx, "doc")

    assert editor.origin == StepOrigin("agent", None, "farmhand")
    assert editor.history_manager is container.editor.history_manager


# ---------------------------------------------------------------------------
# GraphAppState bridge
# ---------------------------------------------------------------------------


def test_a_registered_file_is_listened_to_until_unregistered():
    state = GraphAppState()
    container = _container("doc")

    state.register(container)
    assert state._on_history_changed in _history(container)._listeners

    state.unregister("doc")
    assert _history(container)._listeners == []


def test_replacing_a_container_stops_listening_to_the_old_history():
    state = GraphAppState()
    old, new = _container("doc"), _container("doc")

    state.register(old)
    state.register(new)

    assert _history(old)._listeners == []
    assert _history(new)._listeners == [state._on_history_changed]


class _Loop:
    def __init__(self, running: bool):
        self.running = running
        self.calls: list[tuple] = []

    def is_running(self) -> bool:
        return self.running

    def call_soon_threadsafe(self, fn, *args) -> None:
        self.calls.append((fn, *args))


def test_a_history_change_publishes_on_the_loop(monkeypatch):
    from nicegui import core

    loop = _Loop(running=True)
    monkeypatch.setattr(core, "loop", loop)
    state = GraphAppState()
    container = _container("doc")
    state.register(container)

    _history(container).add_fence()

    ((fn, signal),) = loop.calls
    assert fn == state._signal_emit
    assert isinstance(signal, GraphHistoryChanged)


def test_a_history_change_without_a_running_loop_is_dropped(monkeypatch):
    from nicegui import core

    loop = _Loop(running=False)
    monkeypatch.setattr(core, "loop", loop)
    state = GraphAppState()
    container = _container("doc")
    state.register(container)

    _history(container).add_fence()

    assert loop.calls == []
