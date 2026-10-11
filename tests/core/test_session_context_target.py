"""``SessionContext.target_binding_id`` and ``SessionContext.keymap`` are signal fields."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import react_on
from haywire.core.session.session import Session
from haywire.core.signals import Signal
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper
from haywire.ui.keymap import build_keymap


def _make_session() -> Session:
    session = Session(app_state=MagicMock(), workspace_manager=MagicMock(), dispatcher=MagicMock())
    # The wrapper skips panel-bus subscription when the app carries no panel registry.
    session.context.app = SimpleNamespace()
    return session


class _TargetListener(BaseEditor):
    class_identity = cast(
        Any,
        SimpleNamespace(registry_key="test:target", label="target", default_slot=SlotName.EDIT, opens=None),
    )

    def __init__(self, wrapper: Any) -> None:
        super().__init__(wrapper)
        self.target_signals: list[Signal] = []
        self.keymap_signals: list[Signal] = []

    def draw(self, context: Any, container: Any) -> None:
        pass

    @react_on(SessionContext.target_binding_id)
    def _on_target(self, ctx: Any, signal: Signal) -> None:
        self.target_signals.append(signal)

    @react_on(SessionContext.keymap)
    def _on_keymap(self, ctx: Any, signal: Signal) -> None:
        self.keymap_signals.append(signal)


def _listener(session: Session) -> _TargetListener:
    wrapper = EditorWrapper(
        editor_key="test:target",
        editor_cls=_TargetListener,
        registry=EditorTypeRegistry(),
        session=session,
    )
    assert wrapper._instantiate() is True
    return cast(_TargetListener, wrapper.instance)


def test_target_binding_id_defaults_to_none() -> None:
    assert _make_session().context.target_binding_id is None


def test_keymap_defaults_to_none() -> None:
    assert _make_session().context.keymap is None


def test_writing_target_binding_id_fires_react_on_subscriber() -> None:
    session = _make_session()
    editor = _listener(session)

    session.context.target_binding_id = "haybale_graph_editor:graph::graphs/a.haywire"

    assert session.context.target_binding_id == "haybale_graph_editor:graph::graphs/a.haywire"
    assert len(editor.target_signals) == 1
    assert editor.keymap_signals == []


def test_writing_keymap_fires_react_on_subscriber() -> None:
    session = _make_session()
    editor = _listener(session)
    keymap = build_keymap({}, lambda _tier: True)

    session.context.keymap = keymap

    assert session.context.keymap is keymap
    assert len(editor.keymap_signals) == 1
    assert editor.target_signals == []
