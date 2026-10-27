"""Subscriber failures reach the error ledger; delivery continues."""

from unittest.mock import MagicMock

import pytest

from haywire.core.errors import Refusal
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.signals.bus import SignalBus
from haywire.core.signals.dispatcher import SignalDispatcher
from haywire.core.signals.signal import Signal

pytestmark = pytest.mark.unit


class _Ping(Signal):
    pass


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def _boom(signal):
    raise KeyError("boom")


def test_a_raising_handler_is_recorded_and_the_next_still_runs(ledger):
    bus = SignalBus()
    seen: list[Signal] = []
    bus.subscribe(_Ping, _boom)
    bus.subscribe(_Ping, seen.append)
    ping = _Ping()
    bus.publish(ping)
    assert seen == [ping]
    result = ledger.query()
    assert result.total == 1
    entry = result.entries[0]
    assert entry.operation == "Signal handler"
    assert entry.details["signal"] == "_Ping"
    assert entry.details["handler"].endswith("_boom")


def test_a_refusal_in_a_handler_is_recorded(ledger):
    bus = SignalBus()

    def refuse(signal):
        raise Refusal("nope")

    bus.subscribe(_Ping, refuse)
    bus.publish(_Ping())
    result = ledger.query()
    assert result.total == 1
    assert result.entries[0].operation == "Signal handler"
    assert result.entries[0].details["signal"] == "_Ping"


def test_a_handler_failing_on_every_publish_merges_into_one_entry(ledger):
    bus = SignalBus()
    bus.subscribe(_Ping, _boom)
    for _ in range(100):
        bus.publish(_Ping())
    result = ledger.query()
    assert result.total == 1
    assert result.entries[0].count == 100


def test_a_failing_peer_is_recorded_and_the_next_peer_still_runs(ledger):
    dispatcher = SignalDispatcher()
    bad, good = MagicMock(), MagicMock()
    bad._dispatch.side_effect = RuntimeError("peer down")
    dispatcher._peers = {"a" * 12: bad, "b" * 12: good}
    dispatcher.broadcast(_Ping())
    good._dispatch.assert_called_once()
    result = ledger.query()
    assert result.total == 1
    entry = result.entries[0]
    assert entry.operation == "Signal broadcast"
    assert entry.details["signal"] == "_Ping"
    assert entry.details["peer"] == "a" * 8


def test_a_refusal_in_a_broadcast_is_recorded(ledger):
    dispatcher = SignalDispatcher()
    bad = MagicMock()
    bad._dispatch.side_effect = Refusal("nope")
    dispatcher._peers = {"a" * 12: bad}
    dispatcher.broadcast(_Ping())
    result = ledger.query()
    assert result.total == 1
    assert result.entries[0].operation == "Signal broadcast"
    assert result.entries[0].details["peer"] == "a" * 8


def test_a_listener_republishing_on_a_failing_bus_does_not_loop(ledger):
    bus = SignalBus()
    bus.subscribe(_Ping, _boom)
    fired: list[int] = []

    def bridge():
        fired.append(1)
        if len(fired) < 20:  # loop guard: a regression fails instead of hanging
            bus.publish(_Ping())

    ledger.add_listener(bridge)
    bus.publish(_Ping())
    assert len(fired) == 1
    assert ledger.query().total == 1
