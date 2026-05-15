"""Tests for the Signal / CommandSignal vocabulary.

Both observation (plain ``Signal``) and imperative (``CommandSignal``)
payloads share the :class:`~haywire.core.session.signals.Signal` base and
travel through the same per-session bus. ``Session.publish(...)`` routes
either; ``Session.subscribe(SignalType, handler)`` listens for either.

Covers:
- Signal base + CommandSignal inheritance
- Concrete signal classes (cross_session flags)
- CommandSignal subclasses: Reveal, Close, BroadcastClose
- Session.publish() local-only routing for cross_session=False signals
- Session.publish() + SessionManager.broadcast for cross_session=True signals
- SessionManager.broadcast fan-out (every session, including origin)
- Signal / lifecycle sequential ordering contract
"""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.signals import (
    ActiveGraphMoved,
    BroadcastClose,
    Close,
    Signal,
    GraphDataMutated,
    LibraryCatalogChanged,
    CommandSignal,
    Reveal,
    SelectionMoved,
)
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.session import Session
from haywire.core.session.session_manager import SessionManager


# ----------------------------------------------------------------------
# Signal base + hierarchy
# ----------------------------------------------------------------------


def test_command_signal_is_signal_subclass():
    assert issubclass(CommandSignal, Signal)


def test_observation_signals_are_signal_subclass():
    assert issubclass(SelectionMoved, Signal)
    assert issubclass(GraphDataMutated, Signal)


def test_signal_cross_session_defaults_false():
    assert Signal.cross_session is False
    assert SelectionMoved.cross_session is False
    assert ActiveGraphMoved.cross_session is False


def test_cross_session_signals_declared_correctly():
    assert GraphDataMutated.cross_session is True
    assert LibraryCatalogChanged.cross_session is True


def test_signal_is_frozen():
    s = SelectionMoved()
    with pytest.raises(FrozenInstanceError):
        s.foo = "x"  # type: ignore[attr-defined]


# ----------------------------------------------------------------------
# Reveal / Close / BroadcastClose (lifecycle commands)
# ----------------------------------------------------------------------


def test_reveal_request_basic():
    editor_cls = MagicMock()
    r = Reveal(editor=editor_cls, binding_id="abc", label="My Tab")
    assert r.editor is editor_cls
    assert r.binding_id == "abc"
    assert r.label == "My Tab"


def test_reveal_request_is_frozen():
    r = Reveal(editor=MagicMock())
    with pytest.raises(FrozenInstanceError):
        r.binding_id = "new"  # type: ignore[misc]


def test_reveal_request_optional_payload_label():
    r = Reveal(editor=MagicMock())
    assert r.binding_id is None
    assert r.label is None


def test_reveal_is_command_signal():
    assert isinstance(Reveal(editor=MagicMock()), CommandSignal)


def test_close_carries_payload():
    c = Close(binding_id="entry-42")
    assert c.binding_id == "entry-42"


def test_close_is_frozen():
    c = Close(binding_id="x")
    with pytest.raises(FrozenInstanceError):
        c.binding_id = "y"  # type: ignore[misc]


def test_close_requires_payload():
    with pytest.raises(TypeError):
        Close()  # type: ignore[call-arg]


def test_close_is_command_signal():
    assert isinstance(Close(binding_id="x"), CommandSignal)


def test_broadcast_close_cross_session():
    assert BroadcastClose.cross_session is True
    assert Close.cross_session is False


# ----------------------------------------------------------------------
# Session.publish() routing through the signal bus
# ----------------------------------------------------------------------


def _make_session(session_manager=None):
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=session_manager or MagicMock(),
    )


def test_publish_local_only_for_cross_session_false_signal():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.subscribe(SelectionMoved, handler)

    s = SelectionMoved()
    session.publish(s)

    handler.assert_called_once_with(s)
    sm.broadcast.assert_not_called()


def test_publish_local_only_for_cross_session_false_command():
    """A local Close goes only to local subscribers — no broadcast."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.subscribe(Close, handler)

    c = Close(binding_id="x")
    session.publish(c)

    handler.assert_called_once_with(c)
    sm.broadcast.assert_not_called()


def test_publish_broadcasts_for_cross_session_true_signal():
    """For cross_session=True signals, Session.publish() delegates to
    SessionManager.broadcast which is responsible for dispatching to every
    session (including origin). Local subscribers are NOT called directly —
    the broadcast path reaches them via _dispatch.
    """
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.subscribe(GraphDataMutated, handler)

    s = GraphDataMutated()
    session.publish(s)

    handler.assert_not_called()
    sm.broadcast.assert_called_once_with(s)


def test_publish_broadcasts_for_cross_session_true_command():
    """A BroadcastClose flows through SessionManager.broadcast, just like
    cross-session observation signals."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.subscribe(BroadcastClose, handler)

    c = BroadcastClose(binding_id="x")
    session.publish(c)

    handler.assert_not_called()
    sm.broadcast.assert_called_once_with(c)


def test_publish_swallows_handler_exceptions():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock(side_effect=RuntimeError("boom"))
    session.subscribe(SelectionMoved, handler)

    # Should not raise — bus is error-isolated per handler.
    session.publish(SelectionMoved())


def test_publish_no_handler_is_noop():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    # No subscriber registered — must not raise.
    session.publish(SelectionMoved())


# ----------------------------------------------------------------------
# Subscribe by exact type — no subclass inheritance
# ----------------------------------------------------------------------


def test_subscribing_to_close_does_not_receive_broadcast_close():
    """The bus matches by exact type. A subscriber to ``Close`` does not
    fire for ``BroadcastClose`` — handlers that want both must subscribe
    to both classes (which is how AppShell wires itself)."""
    session = _make_session()
    close_handler = MagicMock()
    session.subscribe(Close, close_handler)

    # A *local* BroadcastClose (we'd need to bypass cross_session routing
    # to land it on the local bus). Use the internal _dispatch hook the
    # transport uses to fan out cross-session events.
    session._dispatch(BroadcastClose(binding_id="x"))

    close_handler.assert_not_called()


def test_subscribing_to_broadcast_close_receives_only_broadcast_close():
    session = _make_session()
    handler = MagicMock()
    session.subscribe(BroadcastClose, handler)

    bc = BroadcastClose(binding_id="x")
    session._dispatch(bc)

    handler.assert_called_once_with(bc)


# ----------------------------------------------------------------------
# Signal / command sequential ordering
# ----------------------------------------------------------------------


def test_observation_runs_before_command_when_published_in_order():
    """Authors publish an observation signal and then a command; the
    observation handler completes before the command handler starts."""
    session = _make_session()

    call_order: list[str] = []
    session.subscribe(SelectionMoved, lambda s: call_order.append("signal"))
    session.subscribe(Reveal, lambda c: call_order.append("command"))

    session.publish(SelectionMoved())
    session.publish(Reveal(editor=MagicMock()))

    assert call_order == ["signal", "command"]


# ----------------------------------------------------------------------
# SessionManager.broadcast — fan-out delivery
# ----------------------------------------------------------------------


def test_broadcast_delivers_to_every_session_including_origin():
    """Every registered session — including the origin — receives the
    signal exactly once."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer_a = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer_b = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    received: dict[str, list] = {origin.session_id: [], peer_a.session_id: [], peer_b.session_id: []}
    origin.subscribe(GraphDataMutated, lambda s: received[origin.session_id].append(s))
    peer_a.subscribe(GraphDataMutated, lambda s: received[peer_a.session_id].append(s))
    peer_b.subscribe(GraphDataMutated, lambda s: received[peer_b.session_id].append(s))

    s = GraphDataMutated()
    sm.broadcast(s)

    for sid in (origin.session_id, peer_a.session_id, peer_b.session_id):
        assert received[sid] == [s]


def test_broadcast_swallows_per_peer_exceptions():
    """A subscriber raising in one session does not abort delivery to others."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    bad = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    good = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    delivered: list[tuple[str, Signal]] = []
    origin.subscribe(GraphDataMutated, lambda s: delivered.append(("origin", s)))
    bad.subscribe(GraphDataMutated, MagicMock(side_effect=RuntimeError("boom")))
    good.subscribe(GraphDataMutated, lambda s: delivered.append(("good", s)))

    sm.broadcast(GraphDataMutated())

    delivered_kinds = {kind for kind, _ in delivered}
    assert "origin" in delivered_kinds
    assert "good" in delivered_kinds


def test_publish_end_to_end_with_session_manager():
    """A cross_session=True signal published via Session.publish() reaches
    every peer's bus subscribers."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    origin_received: list[GraphDataMutated] = []
    peer_received: list[GraphDataMutated] = []
    origin.subscribe(GraphDataMutated, origin_received.append)
    peer.subscribe(GraphDataMutated, peer_received.append)

    s = GraphDataMutated()
    origin.publish(s)

    assert origin_received == [s]
    assert peer_received == [s]


def test_broadcast_close_end_to_end_with_session_manager():
    """A BroadcastClose published on one session reaches every session's
    BroadcastClose subscribers."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    origin_received: list[BroadcastClose] = []
    peer_received: list[BroadcastClose] = []
    origin.subscribe(BroadcastClose, origin_received.append)
    peer.subscribe(BroadcastClose, peer_received.append)

    bc = BroadcastClose(binding_id="entry-x")
    origin.publish(bc)

    assert origin_received == [bc]
    assert peer_received == [bc]
