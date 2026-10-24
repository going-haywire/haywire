"""An EditorCommand reaches only the wrapper it is addressed to, and only at its access requirement."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

from haywire.core.access.tier import AccessTier
from haywire.core.session.handlers import react_on
from haywire.core.session.session import Session
from haywire.core.signals import Copy, Delete, Signal
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.editor.wrapper import EditorWrapper


@dataclass(frozen=True)
class _Plain(Signal):
    pass


def _identity(key: str) -> Any:
    return SimpleNamespace(registry_key=key, label=key, default_slot=SlotName.EDIT, opens=None)


class _CommandEditor(BaseEditor):
    class_identity = _identity("test:editor:command")

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.calls: list[Signal] = []

    def draw(self, context, container):
        pass

    @react_on(Copy, Delete, _Plain)
    def on_signal(self, ctx, event):
        self.calls.append(event)


def _make_session() -> Session:
    session = Session(app_state=MagicMock(), workspace_manager=MagicMock(), dispatcher=MagicMock())
    session.context.app = SimpleNamespace()
    return session


def _make_wrapper(session: Session, binding_id: str) -> EditorWrapper:
    wrapper = EditorWrapper(
        editor_key="test:editor:command",
        editor_cls=_CommandEditor,
        registry=EditorTypeRegistry(),
        session=session,
        binding_id=binding_id,
    )
    assert wrapper._instantiate() is True
    return wrapper


def _calls(wrapper: EditorWrapper) -> list[Signal]:
    return cast(Any, wrapper.instance).calls


def test_command_reaches_only_matching_binding():
    session = _make_session()
    a = _make_wrapper(session, "a")
    b = _make_wrapper(session, "b")
    assert a.editor_binding_id == "test:editor:command::a"
    assert b.editor_binding_id == "test:editor:command::b"

    command = Copy(binding_id=a.editor_binding_id)
    session.publish(command)

    assert _calls(a) == [command]
    assert _calls(b) == []


def test_command_below_tier_is_dropped():
    session = _make_session()
    wrapper = _make_wrapper(session, "a")

    def _can_access(required: AccessTier) -> bool:
        return required is AccessTier.VIEW

    with patch.object(session.context, "can_access", side_effect=_can_access):
        session.publish(Delete(binding_id=wrapper.editor_binding_id))
        assert _calls(wrapper) == []

        copy = Copy(binding_id=wrapper.editor_binding_id)
        session.publish(copy)
        assert _calls(wrapper) == [copy]


def test_plain_signals_unaffected():
    session = _make_session()
    a = _make_wrapper(session, "a")
    b = _make_wrapper(session, "b")

    signal = _Plain()
    with patch.object(session.context, "can_access", return_value=False):
        session.publish(signal)

    assert _calls(a) == [signal]
    assert _calls(b) == [signal]


def test_dispatch_asks_the_editor():
    session = _make_session()
    wrapper = _make_wrapper(session, "a")
    editor = cast(Any, wrapper.instance)
    editor.accepts_command = lambda context, command: False  # type: ignore[method-assign]

    session.publish(Copy(binding_id=wrapper.editor_binding_id))
    assert _calls(wrapper) == []

    editor.accepts_command = lambda context, command: True  # type: ignore[method-assign]
    copy = Copy(binding_id=wrapper.editor_binding_id)
    session.publish(copy)
    assert _calls(wrapper) == [copy]
