"""Tests for the session-scoped typed event bus.

Covers Step 4 of the event-bus redesign:
- EventBus.subscribe / publish / unsubscribe semantics
- Exact-class match on dispatch (no isinstance, no inheritance)
- Registration-order dispatch
- Error isolation per handler
- Snapshot iteration (mid-dispatch subscribe/unsubscribe is safe)
- Session.publish / Session.subscribe pass-through
- Session.signal() bridges to the bus during the migration window
- Session._dispatch (peer-incoming) reaches bus subscribers
- cross_session events delegate to SessionManager.broadcast
- Session.cleanup() drops bus subscriptions
"""

from dataclasses import dataclass
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.session.bus import EventBus
from haywire.core.session.session import Session
from haywire.core.session.events import (
    ContextSignal,
    GraphDataMutated,
    SelectionMoved,
)


# ----------------------------------------------------------------------
# Test fixtures: lightweight event types
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _LocalEventA(ContextSignal):
    pass


@dataclass(frozen=True)
class _LocalEventB(ContextSignal):
    pass


@dataclass(frozen=True)
class _CrossEvent(ContextSignal):
    cross_session: ClassVar[bool] = True


def _make_session(session_manager=None) -> Session:
    return Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=session_manager or MagicMock(),
    )


# ----------------------------------------------------------------------
# EventBus (unit)
# ----------------------------------------------------------------------


def test_bus_subscribe_and_publish_delivers():
    bus = EventBus()
    seen: list[ContextSignal] = []
    bus.subscribe(_LocalEventA, seen.append)

    event = _LocalEventA()
    bus.publish(event)

    assert seen == [event]


def test_bus_publish_with_no_subscribers_is_noop():
    bus = EventBus()
    # Should not raise.
    bus.publish(_LocalEventA())


def test_bus_exact_class_match_not_isinstance():
    """A subscriber to a base class does NOT fire for a subclass.

    The design doc explicitly defers inherited-subscription behaviour until
    a real grouping use case appears. We enforce that here.
    """

    @dataclass(frozen=True)
    class _DerivedEvent(_LocalEventA):
        pass

    bus = EventBus()
    base_seen: list[ContextSignal] = []
    derived_seen: list[ContextSignal] = []
    bus.subscribe(_LocalEventA, base_seen.append)
    bus.subscribe(_DerivedEvent, derived_seen.append)

    bus.publish(_DerivedEvent())
    assert base_seen == []
    assert len(derived_seen) == 1

    bus.publish(_LocalEventA())
    assert len(base_seen) == 1
    assert len(derived_seen) == 1


def test_bus_only_matching_type_fires():
    bus = EventBus()
    a_calls: list[ContextSignal] = []
    b_calls: list[ContextSignal] = []
    bus.subscribe(_LocalEventA, a_calls.append)
    bus.subscribe(_LocalEventB, b_calls.append)

    bus.publish(_LocalEventA())
    assert len(a_calls) == 1
    assert b_calls == []


def test_bus_registration_order_is_preserved():
    bus = EventBus()
    log: list[str] = []
    bus.subscribe(_LocalEventA, lambda e: log.append("first"))
    bus.subscribe(_LocalEventA, lambda e: log.append("second"))
    bus.subscribe(_LocalEventA, lambda e: log.append("third"))

    bus.publish(_LocalEventA())
    assert log == ["first", "second", "third"]


def test_bus_handler_exception_does_not_block_subsequent_handlers():
    bus = EventBus()
    log: list[str] = []

    def boom(event):
        log.append("boom")
        raise RuntimeError("intentional")

    bus.subscribe(_LocalEventA, boom)
    bus.subscribe(_LocalEventA, lambda e: log.append("after"))

    # Should not raise.
    bus.publish(_LocalEventA())
    assert log == ["boom", "after"]


def test_bus_unsubscribe_handle_removes_subscription():
    bus = EventBus()
    calls: list[ContextSignal] = []
    unsub = bus.subscribe(_LocalEventA, calls.append)

    bus.publish(_LocalEventA())
    assert len(calls) == 1

    unsub()
    bus.publish(_LocalEventA())
    assert len(calls) == 1  # still 1; unsubscribed


def test_bus_double_unsubscribe_is_noop():
    bus = EventBus()
    unsub = bus.subscribe(_LocalEventA, lambda e: None)
    unsub()
    unsub()  # should not raise


def test_bus_subscribe_rejects_non_signal_type():
    bus = EventBus()
    with pytest.raises(TypeError):
        bus.subscribe(str, lambda e: None)  # type: ignore[arg-type]


def test_bus_subscribe_rejects_instance_instead_of_class():
    bus = EventBus()
    with pytest.raises(TypeError):
        bus.subscribe(_LocalEventA(), lambda e: None)  # type: ignore[arg-type]


def test_bus_snapshot_iteration_isolates_mid_dispatch_subscribe():
    """A handler that subscribes during dispatch does not fire in the same publish.

    The bus iterates over a snapshot of handlers, so new subscriptions land
    in the next publish — matches the design doc's registration-order rule.
    """
    bus = EventBus()
    second_fires = []

    def first(event):
        bus.subscribe(_LocalEventA, lambda e: second_fires.append(e))

    bus.subscribe(_LocalEventA, first)
    bus.publish(_LocalEventA())
    assert second_fires == []  # not in this dispatch

    bus.publish(_LocalEventA())
    assert len(second_fires) == 1  # picked up next time


def test_bus_snapshot_iteration_isolates_mid_dispatch_unsubscribe():
    """A handler that unsubscribes another during dispatch does not affect this pass."""
    bus = EventBus()
    log: list[str] = []
    other_unsub = None

    def first(event):
        log.append("first")
        assert other_unsub is not None
        other_unsub()

    def other(event):
        log.append("other")

    bus.subscribe(_LocalEventA, first)
    other_unsub = bus.subscribe(_LocalEventA, other)

    bus.publish(_LocalEventA())
    # "other" still fires this pass — snapshot was taken before dispatch.
    assert log == ["first", "other"]

    log.clear()
    bus.publish(_LocalEventA())
    # Now "other" is gone.
    assert log == ["first"]


def test_bus_subscriber_count_and_subscribed_types():
    bus = EventBus()
    assert bus.subscriber_count(_LocalEventA) == 0
    assert bus.subscribed_types() == ()

    unsub = bus.subscribe(_LocalEventA, lambda e: None)
    bus.subscribe(_LocalEventA, lambda e: None)
    bus.subscribe(_LocalEventB, lambda e: None)
    assert bus.subscriber_count(_LocalEventA) == 2
    assert bus.subscriber_count(_LocalEventB) == 1
    assert set(bus.subscribed_types()) == {_LocalEventA, _LocalEventB}

    unsub()
    assert bus.subscriber_count(_LocalEventA) == 1


def test_bus_clear_drops_all_subscriptions():
    bus = EventBus()
    calls: list[ContextSignal] = []
    bus.subscribe(_LocalEventA, calls.append)
    bus.subscribe(_LocalEventB, calls.append)

    bus.clear()
    bus.publish(_LocalEventA())
    bus.publish(_LocalEventB())
    assert calls == []
    assert bus.subscribed_types() == ()


# ----------------------------------------------------------------------
# Session integration
# ----------------------------------------------------------------------


def test_session_subscribe_and_publish_pass_through():
    session = _make_session()
    received: list[ContextSignal] = []
    session.subscribe(_LocalEventA, received.append)

    event = _LocalEventA()
    session.publish(event)
    assert received == [event]


def test_session_publish_local_event_skips_session_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    session.publish(_LocalEventA())
    sm.broadcast.assert_not_called()


def test_session_publish_cross_session_event_delegates_to_manager():
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    event = _CrossEvent()

    session.publish(event)

    sm.broadcast.assert_called_once_with(event)


def test_session_publish_cross_session_skips_local_bus_directly():
    """For cross_session events, Session.publish delegates to the manager;
    local bus subscribers are reached via _dispatch on broadcast
    back, not via the direct publish path. This avoids double-delivery to
    the origin session.
    """
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    received: list[ContextSignal] = []
    session.subscribe(_CrossEvent, received.append)

    session.publish(_CrossEvent())

    # Local bus not called directly; broadcast is responsible for
    # fanning back to origin via _dispatch.
    assert received == []
    sm.broadcast.assert_called_once()


def test_session_signal_is_alias_for_publish():
    """``Session.signal`` is kept as a thin alias for ``Session.publish``
    so legacy emit-site call shapes stay valid post-migration."""
    session = _make_session()
    received: list[ContextSignal] = []
    session.subscribe(SelectionMoved, received.append)

    event = SelectionMoved()
    session.signal(event)

    assert received == [event]
    assert Session.signal is Session.publish


def test_session_signal_cross_session_does_not_double_dispatch_to_bus():
    """For cross_session signals, Session.signal() only delegates to the
    manager — the manager will call _dispatch on every session
    (origin included), which is where the bus fan-out happens."""
    sm = MagicMock()
    session = _make_session(session_manager=sm)
    received: list[ContextSignal] = []
    session.subscribe(GraphDataMutated, received.append)

    session.signal(GraphDataMutated())

    sm.broadcast.assert_called_once()
    # Bus not yet touched; the manager's broadcast loop will call
    # _dispatch which feeds the bus.
    assert received == []


def test_session_dispatch_reaches_bus_subscribers():
    """Peer-broadcast incoming signals fan out to bus subscribers."""
    session = _make_session()
    received: list[ContextSignal] = []
    session.subscribe(GraphDataMutated, received.append)

    event = GraphDataMutated()
    session._dispatch(event)

    assert received == [event]


def test_session_subscribe_returns_working_unsubscribe_handle():
    session = _make_session()
    received: list[ContextSignal] = []
    unsub = session.subscribe(_LocalEventA, received.append)

    session.publish(_LocalEventA())
    assert len(received) == 1

    unsub()
    session.publish(_LocalEventA())
    assert len(received) == 1


def test_session_cleanup_clears_bus_subscriptions():
    session = _make_session()
    received: list[ContextSignal] = []
    session.subscribe(_LocalEventA, received.append)

    session.cleanup()
    session.publish(_LocalEventA())

    assert received == []
