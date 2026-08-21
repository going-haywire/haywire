"""Tests for _signal_emit on each of the three host bases.

Verifies routing: SessionContext/SessionState publish to the local bus;
AppState broadcasts to every peer via SignalDispatcher."""

from typing import Any, cast

import weakref
from unittest.mock import MagicMock

from haywire.core.signals import Signal, SignalSource
from haywire.core.state.base import AppState, SessionState


def test_session_context_signal_emit_delegates_to_session_publish():
    from haywire.core.session.context import SessionContext

    class Tick(Signal):
        pass

    from tests.conftest import attach_stub_session

    # Use __new__ to bypass __init__ — _signal_emit only needs `session` attribute,
    # not a full IProjectState.
    ctx = attach_stub_session(SessionContext.__new__(SessionContext))
    sig = Tick()
    ctx._signal_emit(sig)
    ctx.session.publish.assert_called_once_with(sig)


def test_session_state_inherits_signal_source():
    # Inherited transitively via LibraryState, not declared on the class itself —
    # a refactor of that middle layer could silently sever it.
    assert issubclass(SessionState, SignalSource)


def test_app_state_inherits_signal_source():
    assert issubclass(AppState, SignalSource)


def test_session_state_signal_emit_via_weakref_session():
    """SessionState._signal_emit derefs self.session weakref and calls publish."""

    class Tick(Signal):
        pass

    class MyState(SessionState):
        pass

    mock_session = MagicMock()
    state = MyState()
    state.session = weakref.ref(mock_session)
    state._signal_emit(Tick())
    mock_session.publish.assert_called_once()


def test_session_state_signal_emit_silent_when_session_gone():
    """If the Session has been garbage-collected, _signal_emit is a silent no-op."""

    class Tick(Signal):
        pass

    class MyState(SessionState):
        pass

    class _Disposable:
        pass

    sess = _Disposable()
    state = MyState()
    state.session = weakref.ref(sess)
    del sess  # weakref now dead
    # Must not raise; must not call anything.
    state._signal_emit(Tick())


def test_app_state_signal_emit_via_weakref_dispatcher():
    class Tick(Signal):
        pass

    class MyAppState(AppState):
        pass

    mock_dispatcher = MagicMock()
    state = MyAppState()
    state._dispatcher = weakref.ref(mock_dispatcher)
    state._signal_emit(Tick())
    mock_dispatcher.broadcast.assert_called_once()


def test_app_state_signal_emit_silent_when_dispatcher_gone():
    class Tick(Signal):
        pass

    class MyAppState(AppState):
        pass

    class _Disposable:
        pass

    dispatcher = _Disposable()
    state = MyAppState()
    state._dispatcher = weakref.ref(cast(Any, dispatcher))
    del dispatcher
    state._signal_emit(Tick())  # must not raise
