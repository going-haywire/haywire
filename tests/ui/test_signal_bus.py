"""Tests for the session-scoped typed signal bus.

- SignalBus.subscribe / publish / unsubscribe semantics
- Exact-class match on dispatch (no isinstance, no inheritance)
- Registration-order dispatch
- Error isolation per handler
- Snapshot iteration (mid-dispatch subscribe/unsubscribe is safe)
- Session.publish / Session.subscribe pass-through
- Session._dispatch (peer-incoming) reaches bus subscribers
- cross_session signals delegate to SessionManager.broadcast
- Session.cleanup() drops bus subscriptions
"""

from dataclasses import dataclass
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.signals import SignalBus
from haywire.core.session.session import Session
from haywire.core.session.signals import (
    Signal,
    GraphDataMutated,
)


# ----------------------------------------------------------------------
# Test fixtures: lightweight signal types
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _LocalSignalA(Signal):
    pass


@dataclass(frozen=True)
class _LocalSignalB(Signal):
    pass


@dataclass(frozen=True)
class _CrossSignal(Signal):
    cross_session: ClassVar[bool] = True


def _make_session(session_manager=None) -> Session:
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=session_manager or MagicMock(),
    )


# ----------------------------------------------------------------------
# SignalBus (unit)
# ----------------------------------------------------------------------


def test_bus_subscribe_and_publish_delivers():
    bus = SignalBus()
    seen: list[Signal] = []
    bus.subscribe(_LocalSignalA, seen.append)

    signal = _LocalSignalA()
    bus.publish(signal)

    assert seen == [signal]


def test_bus_publish_with_no_subscribers_is_noop():
    bus = SignalBus()
    # Should not raise.
    bus.publish(_LocalSignalA())


def test_bus_exact_class_match_not_isinstance():
    """A subscriber to a base class does NOT fire for a subclass.

    The design doc explicitly defers inherited-subscription behaviour until
    a real grouping use case appears. We enforce that here.
    """

    @dataclass(frozen=True)
    class _DerivedSignal(_LocalSignalA):
        pass

    bus = SignalBus()
    base_seen: list[Signal] = []
    derived_seen: list[Signal] = []
    bus.subscribe(_LocalSignalA, base_seen.append)
    bus.subscribe(_DerivedSignal, derived_seen.append)

    bus.publish(_DerivedSignal())
    assert base_seen == []
    assert len(derived_seen) == 1

    bus.publish(_LocalSignalA())
    assert len(base_seen) == 1
    assert len(derived_seen) == 1


def test_bus_only_matching_type_fires():
    bus = SignalBus()
    a_calls: list[Signal] = []
    b_calls: list[Signal] = []
    bus.subscribe(_LocalSignalA, a_calls.append)
    bus.subscribe(_LocalSignalB, b_calls.append)

    bus.publish(_LocalSignalA())
    assert len(a_calls) == 1
    assert b_calls == []


def test_bus_registration_order_is_preserved():
    bus = SignalBus()
    log: list[str] = []
    bus.subscribe(_LocalSignalA, lambda e: log.append("first"))
    bus.subscribe(_LocalSignalA, lambda e: log.append("second"))
    bus.subscribe(_LocalSignalA, lambda e: log.append("third"))

    bus.publish(_LocalSignalA())
    assert log == ["first", "second", "third"]


def test_bus_handler_exception_does_not_block_subsequent_handlers():
    bus = SignalBus()
    log: list[str] = []

    def boom(event):
        log.append("boom")
        raise RuntimeError("intentional")

    bus.subscribe(_LocalSignalA, boom)
    bus.subscribe(_LocalSignalA, lambda e: log.append("after"))

    # Should not raise.
    bus.publish(_LocalSignalA())
    assert log == ["boom", "after"]


def test_bus_unsubscribe_handle_removes_subscription():
    bus = SignalBus()
    calls: list[Signal] = []
    unsub = bus.subscribe(_LocalSignalA, calls.append)

    bus.publish(_LocalSignalA())
    assert len(calls) == 1

    unsub()
    bus.publish(_LocalSignalA())
    assert len(calls) == 1  # still 1; unsubscribed


def test_bus_double_unsubscribe_is_noop():
    bus = SignalBus()
    unsub = bus.subscribe(_LocalSignalA, lambda e: None)
    unsub()
    unsub()  # should not raise


def test_bus_subscribe_rejects_non_signal_type():
    bus = SignalBus()
    with pytest.raises(TypeError):
        bus.subscribe(str, lambda e: None)  # type: ignore[arg-type]


def test_bus_subscribe_rejects_instance_instead_of_class():
    bus = SignalBus()
    with pytest.raises(TypeError):
        bus.subscribe(_LocalSignalA(), lambda e: None)  # type: ignore[arg-type]


def test_bus_snapshot_iteration_isolates_mid_dispatch_subscribe():
    """A handler that subscribes during dispatch does not fire in the same publish.

    The bus iterates over a snapshot of handlers, so new subscriptions land
    in the next publish — matches the design doc's registration-order rule.
    """
    bus = SignalBus()
    second_fires = []

    def first(event):
        bus.subscribe(_LocalSignalA, lambda e: second_fires.append(e))

    bus.subscribe(_LocalSignalA, first)
    bus.publish(_LocalSignalA())
    assert second_fires == []  # not in this dispatch

    bus.publish(_LocalSignalA())
    assert len(second_fires) == 1  # picked up next time


def test_bus_snapshot_iteration_isolates_mid_dispatch_unsubscribe():
    """A handler that unsubscribes another during dispatch does not affect this pass."""
    bus = SignalBus()
    log: list[str] = []
    other_unsub = None

    def first(event):
        log.append("first")
        assert other_unsub is not None
        other_unsub()

    def other(event):
        log.append("other")

    bus.subscribe(_LocalSignalA, first)
    other_unsub = bus.subscribe(_LocalSignalA, other)

    bus.publish(_LocalSignalA())
    # "other" still fires this pass — snapshot was taken before dispatch.
    assert log == ["first", "other"]

    log.clear()
    bus.publish(_LocalSignalA())
    # Now "other" is gone.
    assert log == ["first"]


def test_bus_subscriber_count_and_subscribed_types():
    bus = SignalBus()
    assert bus.subscriber_count(_LocalSignalA) == 0
    assert bus.subscribed_types() == ()

    unsub = bus.subscribe(_LocalSignalA, lambda e: None)
    bus.subscribe(_LocalSignalA, lambda e: None)
    bus.subscribe(_LocalSignalB, lambda e: None)
    assert bus.subscriber_count(_LocalSignalA) == 2
    assert bus.subscriber_count(_LocalSignalB) == 1
    assert set(bus.subscribed_types()) == {_LocalSignalA, _LocalSignalB}

    unsub()
    assert bus.subscriber_count(_LocalSignalA) == 1


def test_bus_clear_drops_all_subscriptions():
    bus = SignalBus()
    calls: list[Signal] = []
    bus.subscribe(_LocalSignalA, calls.append)
    bus.subscribe(_LocalSignalB, calls.append)

    bus.clear()
    bus.publish(_LocalSignalA())
    bus.publish(_LocalSignalB())
    assert calls == []
    assert bus.subscribed_types() == ()


# ----------------------------------------------------------------------
# Session integration
# ----------------------------------------------------------------------


def test_session_subscribe_and_publish_pass_through():
    session = _make_session()
    received: list[Signal] = []
    session.subscribe(_LocalSignalA, received.append)

    signal = _LocalSignalA()
    session.publish(signal)
    assert received == [signal]


def test_session_publish_local_event_skips_session_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    session.publish(_LocalSignalA())
    sm.broadcast.assert_not_called()


def test_session_publish_cross_session_event_delegates_to_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    signal = _CrossSignal()

    session.publish(signal)

    sm.broadcast.assert_called_once_with(signal)


def test_session_publish_cross_session_skips_local_bus_directly():
    """For cross_session events, Session.publish delegates to the manager;
    local bus subscribers are reached via _dispatch on broadcast
    back, not via the direct publish path. This avoids double-delivery to
    the origin session.
    """
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    received: list[Signal] = []
    session.subscribe(_CrossSignal, received.append)

    session.publish(_CrossSignal())

    # Local bus not called directly; broadcast is responsible for
    # fanning back to origin via _dispatch.
    assert received == []
    sm.broadcast.assert_called_once()


def test_session_dispatch_reaches_bus_subscribers():
    """Peer-broadcast incoming signals fan out to bus subscribers."""
    session = _make_session()
    received: list[Signal] = []
    session.subscribe(GraphDataMutated, received.append)

    signal = GraphDataMutated()
    session._dispatch(signal)

    assert received == [signal]


def test_session_subscribe_returns_working_unsubscribe_handle():
    session = _make_session()
    received: list[Signal] = []
    unsub = session.subscribe(_LocalSignalA, received.append)

    session.publish(_LocalSignalA())
    assert len(received) == 1

    unsub()
    session.publish(_LocalSignalA())
    assert len(received) == 1


def test_session_cleanup_clears_bus_subscriptions():
    session = _make_session()
    received: list[Signal] = []
    session.subscribe(_LocalSignalA, received.append)

    session.cleanup()
    session.publish(_LocalSignalA())

    assert received == []
