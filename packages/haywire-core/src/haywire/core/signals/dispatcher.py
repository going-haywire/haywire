"""SignalDispatcher — cross-peer signal fan-out.

Owns the answer to one question: *who receives a cross-peer signal?* It does
not create peers, does not tear them down, and knows nothing about browsers,
NiceGUI, workspaces or library state. Its entire dependency surface is
:class:`~haywire.core.signals.signal.Signal`.

This used to be ``SessionManager.broadcast``, which conflated two jobs. Of the
five call paths that reached it, only one — ``Session.publish`` — had anything
to do with session lifecycle; ``AppState._signal_emit``,
``FarmhandContext.broadcast`` and the studio's error/activity/presence bridges
all wanted a fan-out channel and were handed a session registry. Splitting the
two means a non-browser participant (the Farmhand MCP host, a CLI, a headless
embedding) can join the fan-out without acquiring a ``WorkspaceManager``, a
``SessionContext``, or per-session ``SessionState`` bags it has no meaning for.

Registration is not performed by callers: :class:`~haywire.core.signals.peer.SignalPeer`
registers itself on construction and unregisters in ``cleanup()``. That makes
the invariant structural rather than remembered — notably, ``evict_principal``
(ADR 0027) tears a session down through ``SessionManager.remove_session`` →
``Session.cleanup()``, so an evicted principal stops receiving broadcasts with
no eviction-side code at all. A design where registration lived at the call
sites would leave that peer subscribed.

Threading: fan-out is synchronous, straight into each peer's single-threaded
:class:`~haywire.core.signals.bus.SignalBus`. Callers on other threads (the
watchdog file-watcher, ``ui.timer`` callbacks) must marshal onto the event loop
first — ``loop.call_soon_threadsafe(...)`` — exactly as they did when this was
``SessionManager.broadcast``. Nothing about the split changes that rule.
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
        # Keyed by peer_id so registration is idempotent and unregistration is
        # O(1). Strong references: a peer's lifetime is owned by whoever
        # created it (SessionManager for sessions, the app for the Farmhand
        # host), and that owner always calls cleanup(). A WeakSet here would
        # silently drop a peer nobody else happened to hold.
        self._peers: Dict[str, "SignalPeer"] = {}

    # ------------------------------------------------------------------
    # Registration — called by SignalPeer, not by application code
    # ------------------------------------------------------------------

    def register(self, peer: "SignalPeer") -> None:
        """Add ``peer`` to the fan-out. Idempotent per ``peer_id``.

        Called from :meth:`SignalPeer.__init__`. Registering a half-built peer
        is safe: a brand-new peer's bus has no subscriptions, so a broadcast
        arriving before the subclass constructor finishes fans out to nothing.
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
        """Read-only snapshot of registered peers, keyed by ``peer_id``.

        A copy: callers must not mutate the live registry, and iterating the
        snapshot is safe while a handler registers or drops a peer.
        """
        return dict(self._peers)

    # ------------------------------------------------------------------
    # Fan-out
    # ------------------------------------------------------------------

    def broadcast(self, signal: Signal) -> None:
        """Deliver ``signal`` to every registered peer, including the origin.

        Reached from :meth:`SignalPeer.publish` when
        ``type(signal).cross_session`` is True, and directly by emitters that
        have no peer of their own (``AppState._signal_emit``,
        ``FarmhandContext.broadcast``, the studio bridges).

        Per-peer exceptions are swallowed and logged: a subscriber raising in
        one peer must not abort delivery to the others. Delivery order is
        registration order (dict insertion order) but nothing should depend on
        it — peers are independent.
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
