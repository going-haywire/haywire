"""SignalDispatcher — cross-peer signal fan-out.

Answers one question: who receives a cross-peer signal? It does not create or
tear down peers. Its entire dependency surface is ``Signal``.

Callers never register a peer — :class:`~haywire.core.signals.peer.SignalPeer`
registers itself on construction and unregisters in ``cleanup()``.

Threading: fan-out is synchronous, straight into each peer's single-threaded
``SignalBus``. Callers on other threads (watchdog, ``ui.timer``) must marshal
onto the event loop first with ``loop.call_soon_threadsafe(...)``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict

from .signal import Signal

if TYPE_CHECKING:
    from .peer import SignalPeer

logger = logging.getLogger(__name__)


class SignalDispatcher:
    """Registry of :class:`SignalPeer` instances plus cross-peer fan-out::

    dispatcher = SignalDispatcher()
    # peers self-register; callers never touch register/unregister
    dispatcher.broadcast(GraphDataMutated())
    """

    def __init__(self) -> None:
        # Strong references: the peer's owner always calls cleanup(). A WeakSet
        # would silently drop a peer nobody else happened to hold.
        self._peers: Dict[str, "SignalPeer"] = {}

    # ------------------------------------------------------------------
    # Registration — called by SignalPeer, not by application code
    # ------------------------------------------------------------------

    def register(self, peer: "SignalPeer") -> None:
        """Add ``peer`` to the fan-out. Idempotent per ``peer_id``.

        Called from :meth:`SignalPeer.__init__`, so ``peer`` may be half-built.
        Safe: its bus has no subscriptions yet, so a broadcast arriving in that
        window fans out to nothing.
        """
        self._peers[peer.peer_id] = peer

    def unregister(self, peer: "SignalPeer") -> None:
        """Remove ``peer`` from the fan-out. No-op if it was never registered."""
        self._peers.pop(peer.peer_id, None)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def peer_count(self) -> int:
        """Number of currently registered peers."""
        return len(self._peers)

    @property
    def peers(self) -> Dict[str, "SignalPeer"]:
        """Snapshot of registered peers, keyed by ``peer_id``. A copy."""
        return dict(self._peers)

    # ------------------------------------------------------------------
    # Fan-out
    # ------------------------------------------------------------------

    def broadcast(self, signal: Signal) -> None:
        """Deliver ``signal`` to every registered peer, including the origin.

        Reached from :meth:`SignalPeer.publish` when ``cross_session`` is True,
        and directly by emitters owning no peer (``AppState._signal_emit``,
        ``FarmhandContext.broadcast``).

        Per-peer exceptions are swallowed and logged so one raising subscriber
        does not abort delivery to the rest.
        """
        failed = []
        for peer_id, peer in list(self._peers.items()):
            try:
                peer._dispatch(signal)
            except Exception as e:
                logger.warning(f"SignalDispatcher: broadcast failed for peer {peer_id[:8]}: {e}")
                failed.append(peer_id)
        if failed:
            logger.warning(f"SignalDispatcher: {len(failed)} peer(s) failed during broadcast")


__all__ = ["SignalDispatcher"]
