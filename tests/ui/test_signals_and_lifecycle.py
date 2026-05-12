"""Tests for the ContextSignal / LifecycleCommand vocabulary.

Covers:
- ContextSignal base class (frozen, default subject, cross_session ClassVar,
  is_local / is_from_peer predicates)
- Subject value object (SELF singleton, peer factory, equality)
- Concrete signal classes (cross_session flags)
- LifecycleCommand subclasses: Reveal, Close
- Session.signal() local-only routing for cross_session=False signals
- Session.signal() + SessionManager.broadcast_signal for cross_session=True
- SessionManager.broadcast_signal subject-stamping (origin sees SELF, peers see peer(id))
- Session.lifecycle() routing
- Signal/lifecycle sequential ordering (§4.4 contract)
"""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.signals_and_lifecycle import (
    ActiveComponentMoved,
    ActiveFileMoved,
    ActiveGraphMoved,
    ActiveLibraryMoved,
    Close,
    ContextSignal,
    GraphDataMutated,
    LibraryCatalogChanged,
    LifecycleCommand,
    Reveal,
    SelectionMoved,
    Subject,
    ThemeMoved,
)
from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.session.session import Session
from haywire.core.session.session_manager import SessionManager


# ----------------------------------------------------------------------
# Subject
# ----------------------------------------------------------------------


def test_subject_self_is_singleton_value():
    assert Subject.SELF == Subject.SELF
    assert Subject.SELF == Subject(peer_id=None)


def test_subject_peer_equality_by_id():
    assert Subject.peer("abc") == Subject.peer("abc")
    assert Subject.peer("abc") != Subject.peer("xyz")
    assert Subject.peer("abc") != Subject.SELF


def test_subject_is_frozen():
    s = Subject.peer("abc")
    with pytest.raises(FrozenInstanceError):
        s.peer_id = "xyz"  # type: ignore[misc]


# ----------------------------------------------------------------------
# ContextSignal base
# ----------------------------------------------------------------------


def test_context_signal_default_subject_is_self():
    s = SelectionMoved()
    assert s.subject == Subject.SELF


def test_context_signal_cross_session_defaults_false():
    assert ContextSignal.cross_session is False
    assert SelectionMoved.cross_session is False
    assert ActiveGraphMoved.cross_session is False
    assert ActiveFileMoved.cross_session is False
    assert ActiveLibraryMoved.cross_session is False
    assert ActiveComponentMoved.cross_session is False
    assert ThemeMoved.cross_session is False


def test_cross_session_signals_declared_correctly():
    assert GraphDataMutated.cross_session is True
    assert LibraryCatalogChanged.cross_session is True


def test_is_local_and_is_from_peer():
    local = SelectionMoved()
    assert local.is_local()
    assert not local.is_from_peer()

    peer = SelectionMoved(subject=Subject.peer("xyz"))
    assert not peer.is_local()
    assert peer.is_from_peer()


def test_signal_is_frozen():
    s = SelectionMoved()
    with pytest.raises(FrozenInstanceError):
        s.subject = Subject.peer("x")  # type: ignore[misc]


# ----------------------------------------------------------------------
# Reveal / Close (lifecycle commands)
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


def test_reveal_is_lifecycle_command():
    assert isinstance(Reveal(editor=MagicMock()), LifecycleCommand)


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


def test_close_is_lifecycle_command():
    assert isinstance(Close(binding_id="x"), LifecycleCommand)


# ----------------------------------------------------------------------
# Session.signal() routing
# ----------------------------------------------------------------------


def _make_session(session_manager=None):
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=session_manager or MagicMock(),
    )


def test_session_signal_local_only_for_cross_session_false():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.set_signal_orchestrator(handler)

    s = SelectionMoved()
    session.signal(s)

    handler.assert_called_once_with(s)
    sm.broadcast_signal.assert_not_called()


def test_session_signal_broadcasts_for_cross_session_true():
    """For cross_session=True signals, Session.signal() delegates to
    SessionManager.broadcast_signal which is responsible for dispatching
    to every session (including origin). The local callback is NOT called
    directly — the broadcast path handles origin delivery.
    """
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.set_signal_orchestrator(handler)

    s = GraphDataMutated()
    session.signal(s)

    # No direct local callback — broadcast handles it.
    handler.assert_not_called()
    sm.broadcast_signal.assert_called_once_with(s, origin_session_id=session.session_id)


def test_session_signal_swallows_handler_exceptions():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock(side_effect=RuntimeError("boom"))
    session.set_signal_orchestrator(handler)

    # Should not raise — error is logged.
    session.signal(SelectionMoved())


def test_session_signal_no_handler_is_noop():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    # No handler registered — must not raise.
    session.signal(SelectionMoved())


# ----------------------------------------------------------------------
# Session.lifecycle()
# ----------------------------------------------------------------------


def test_session_lifecycle_reveal_calls_callback():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.set_lifecycle_orchestrator(handler)

    r = Reveal(editor=MagicMock(), binding_id="p")
    session.lifecycle(r)

    handler.assert_called_once_with(r)


def test_session_lifecycle_close_calls_callback():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    handler = MagicMock()
    session.set_lifecycle_orchestrator(handler)

    c = Close(binding_id="x")
    session.lifecycle(c)

    handler.assert_called_once_with(c)


def test_session_lifecycle_does_not_broadcast():
    """Lifecycle commands are local-only; they never cross sessions."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    session.set_lifecycle_orchestrator(MagicMock())

    session.lifecycle(Reveal(editor=MagicMock()))
    session.lifecycle(Close(binding_id="x"))

    sm.broadcast.assert_not_called()
    sm.broadcast_signal.assert_not_called()


# ----------------------------------------------------------------------
# Signal / lifecycle ordering (§4.4)
# ----------------------------------------------------------------------


def test_signal_runs_before_lifecycle_when_called_in_order():
    """Authors call signal() then lifecycle(); the signal handler must
    complete before the lifecycle handler starts."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)

    call_order = []
    session.set_signal_orchestrator(lambda s: call_order.append("signal"))
    session.set_lifecycle_orchestrator(lambda c: call_order.append("lifecycle"))

    session.signal(SelectionMoved())
    session.lifecycle(Reveal(editor=MagicMock()))

    assert call_order == ["signal", "lifecycle"]


# ----------------------------------------------------------------------
# SessionManager.broadcast_signal — subject stamping
# ----------------------------------------------------------------------


def test_broadcast_signal_stamps_peer_subject_on_non_origin_sessions():
    """Origin session receives signal with subject=SELF; every other
    session receives the same signal with subject=peer(origin_id)."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer_a = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer_b = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    received: dict[str, list] = {origin.session_id: [], peer_a.session_id: [], peer_b.session_id: []}
    origin.set_signal_orchestrator(lambda s: received[origin.session_id].append(s))
    peer_a.set_signal_orchestrator(lambda s: received[peer_a.session_id].append(s))
    peer_b.set_signal_orchestrator(lambda s: received[peer_b.session_id].append(s))

    s = GraphDataMutated()
    sm.broadcast_signal(s, origin_session_id=origin.session_id)

    # Origin sees SELF.
    assert len(received[origin.session_id]) == 1
    assert received[origin.session_id][0].subject == Subject.SELF
    # Peers see peer(origin_id).
    expected_peer_subject = Subject.peer(origin.session_id)
    for peer_id in (peer_a.session_id, peer_b.session_id):
        assert len(received[peer_id]) == 1
        assert received[peer_id][0].subject == expected_peer_subject


def test_broadcast_signal_swallows_per_peer_exceptions():
    """A subscriber raising in one session does not abort delivery to others."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    bad = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    good = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    delivered = []
    origin.set_signal_orchestrator(lambda s: delivered.append(("origin", s)))
    bad.set_signal_orchestrator(MagicMock(side_effect=RuntimeError("boom")))
    good.set_signal_orchestrator(lambda s: delivered.append(("good", s)))

    sm.broadcast_signal(GraphDataMutated(), origin_session_id=origin.session_id)

    # Origin and the good peer still received the signal even though "bad" raised.
    assert ("origin", GraphDataMutated()) in delivered
    delivered_kinds = {kind for kind, _ in delivered}
    assert "origin" in delivered_kinds
    assert "good" in delivered_kinds


def test_session_signal_end_to_end_with_session_manager():
    """A cross_session=True signal emitted via Session.signal() flows to
    every peer's signal callback with correct subject stamping."""
    sm = SessionManager(container=LibraryStateContainer(LibraryStateRegistry()))
    origin = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())
    peer = sm.create_session(project_state=MagicMock(), workspace_manager=MagicMock())

    origin_received = []
    peer_received = []
    origin.set_signal_orchestrator(origin_received.append)
    peer.set_signal_orchestrator(peer_received.append)

    origin.signal(GraphDataMutated())

    # Origin's local handler ran with SELF (the original signal, not stamped).
    assert len(origin_received) == 1
    assert origin_received[0].subject == Subject.SELF
    # Peer received the broadcast with peer(origin_id).
    assert len(peer_received) == 1
    assert peer_received[0].subject == Subject.peer(origin.session_id)
