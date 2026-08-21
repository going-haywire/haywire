"""SignalDispatcher fan-out and SignalPeer membership.

Exercised in isolation — no Session, no SessionManager, no DI, no container.
"""

from dataclasses import dataclass
from typing import ClassVar

import pytest

from haywire.core.signals import Signal, SignalDispatcher, SignalPeer


@dataclass(frozen=True, kw_only=True)
class LocalOnly(Signal):
    """cross_session defaults to False."""


@dataclass(frozen=True, kw_only=True)
class CrossPeer(Signal):
    cross_session: ClassVar[bool] = True


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------


def test_peer_registers_itself_on_construction():
    dispatcher = SignalDispatcher()
    assert dispatcher.peer_count == 0

    peer = SignalPeer(dispatcher)

    assert dispatcher.peer_count == 1
    assert dispatcher.peers[peer.peer_id] is peer


def test_cleanup_unregisters_the_peer():
    dispatcher = SignalDispatcher()
    peer = SignalPeer(dispatcher)

    peer.cleanup()

    assert dispatcher.peer_count == 0


def test_register_is_idempotent_per_peer_id():
    dispatcher = SignalDispatcher()
    peer = SignalPeer(dispatcher)

    dispatcher.register(peer)
    dispatcher.register(peer)

    assert dispatcher.peer_count == 1


def test_unregister_of_unknown_peer_is_a_noop():
    dispatcher = SignalDispatcher()
    stray = SignalPeer(SignalDispatcher())

    dispatcher.unregister(stray)  # must not raise

    assert dispatcher.peer_count == 0


def test_peers_property_is_a_copy():
    dispatcher = SignalDispatcher()
    SignalPeer(dispatcher)

    snapshot = dispatcher.peers
    snapshot.clear()

    assert dispatcher.peer_count == 1


def test_peer_ids_are_unique():
    dispatcher = SignalDispatcher()
    peers = [SignalPeer(dispatcher) for _ in range(5)]

    assert len({p.peer_id for p in peers}) == 5
    assert dispatcher.peer_count == 5


# ----------------------------------------------------------------------
# Routing
# ----------------------------------------------------------------------


def test_local_signal_stays_on_its_own_peer():
    dispatcher = SignalDispatcher()
    origin, other = SignalPeer(dispatcher), SignalPeer(dispatcher)

    seen_origin: list[Signal] = []
    seen_other: list[Signal] = []
    origin.subscribe(LocalOnly, seen_origin.append)
    other.subscribe(LocalOnly, seen_other.append)

    origin.publish(LocalOnly())

    assert len(seen_origin) == 1
    assert seen_other == []


def test_cross_peer_signal_reaches_every_peer_including_origin():
    dispatcher = SignalDispatcher()
    origin, peer_a, peer_b = (SignalPeer(dispatcher) for _ in range(3))

    received: dict[str, list] = {p.peer_id: [] for p in (origin, peer_a, peer_b)}
    for p in (origin, peer_a, peer_b):
        p.subscribe(CrossPeer, received[p.peer_id].append)

    signal = CrossPeer()
    origin.publish(signal)

    for p in (origin, peer_a, peer_b):
        assert received[p.peer_id] == [signal]


def test_broadcast_swallows_per_peer_exceptions():
    dispatcher = SignalDispatcher()
    origin, bad, good = (SignalPeer(dispatcher) for _ in range(3))

    def raiser(_signal):
        raise RuntimeError("peer is wedged")

    delivered = []
    origin.subscribe(CrossPeer, lambda s: delivered.append("origin"))
    bad.subscribe(CrossPeer, raiser)
    good.subscribe(CrossPeer, lambda s: delivered.append("good"))

    origin.publish(CrossPeer())  # must not raise

    assert "good" in delivered


def test_unregistered_peer_stops_receiving_broadcasts():
    """What eviction (ADR 0027) relies on, reached via cleanup()."""
    dispatcher = SignalDispatcher()
    stays, leaves = SignalPeer(dispatcher), SignalPeer(dispatcher)

    seen_stays: list[Signal] = []
    seen_leaves: list[Signal] = []
    stays.subscribe(CrossPeer, seen_stays.append)
    leaves.subscribe(CrossPeer, seen_leaves.append)

    leaves.cleanup()
    stays.publish(CrossPeer())

    assert len(seen_stays) == 1
    assert seen_leaves == []


def test_cleanup_drops_local_subscriptions_too():
    dispatcher = SignalDispatcher()
    peer = SignalPeer(dispatcher)
    seen: list[Signal] = []
    peer.subscribe(LocalOnly, seen.append)

    peer.cleanup()
    peer.publish(LocalOnly())

    assert seen == []


def test_unsubscribe_handle_works():
    dispatcher = SignalDispatcher()
    peer = SignalPeer(dispatcher)
    seen: list[Signal] = []
    unsubscribe = peer.subscribe(LocalOnly, seen.append)

    unsubscribe()
    peer.publish(LocalOnly())

    assert seen == []


def test_subscribe_rejects_non_signal_types():
    peer = SignalPeer(SignalDispatcher())

    with pytest.raises(TypeError):
        peer.subscribe(str, lambda s: None)  # type: ignore[type-var]


def test_broadcast_with_no_peers_is_a_noop():
    SignalDispatcher().broadcast(CrossPeer())  # must not raise


def test_dispatcher_broadcast_reaches_peers_directly():
    """AppState / FarmhandContext own no peer and emit through the dispatcher."""
    dispatcher = SignalDispatcher()
    peer = SignalPeer(dispatcher)
    seen: list[Signal] = []
    peer.subscribe(CrossPeer, seen.append)

    dispatcher.broadcast(CrossPeer())

    assert len(seen) == 1


# ----------------------------------------------------------------------
# The point of the split
# ----------------------------------------------------------------------


def test_non_session_peer_receives_a_browser_sessions_signal():
    """A bare peer — no WorkspaceManager, no SessionContext, no SessionState —
    sits in the same fan-out as a browser Session.

    Written against ``SignalPeer`` so it holds for any non-browser peer.
    """
    from unittest.mock import MagicMock

    from haywire.core.session.session import Session

    dispatcher = SignalDispatcher()
    session = Session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
        dispatcher=dispatcher,
    )
    observer = SignalPeer(dispatcher)

    seen: list[Signal] = []
    observer.subscribe(CrossPeer, seen.append)

    session.publish(CrossPeer())

    assert len(seen) == 1


def test_browser_session_receives_a_non_session_peers_signal():
    """The other direction: a non-browser peer's signal reaches open tabs."""
    from unittest.mock import MagicMock

    from haywire.core.session.session import Session

    dispatcher = SignalDispatcher()
    session = Session(
        app_state=MagicMock(),
        workspace_manager=MagicMock(),
        dispatcher=dispatcher,
    )
    agent = SignalPeer(dispatcher)

    seen: list[Signal] = []
    session.subscribe(CrossPeer, seen.append)

    agent.publish(CrossPeer())

    assert len(seen) == 1
