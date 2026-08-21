"""SignalPeer — anything that can hold a signal bus and join the fan-out.

A peer is one endpoint through which an outside entity — a person at a browser
tab, an agent over MCP, a CLI, a test harness — reaches the app's live state.
It owns a private :class:`~haywire.core.signals.bus.SignalBus` for signals
addressed to itself, and it is registered with a
:class:`~haywire.core.signals.dispatcher.SignalDispatcher` so that cross-peer
signals reach it too.

Why "peer" and not "session": the bus was never browser-specific. ``SignalBus``
imports nothing but ``Signal``, and nothing under this package touches NiceGUI.
It lived on ``Session`` only because ``Session`` was its sole participant. The
word is the one this code already used for the role — ``SessionManager``'s
broadcast docs spoke of "peer sessions" and "per-peer exceptions" long before
this class existed.

**Registration is by construction.** ``__init__`` registers; ``cleanup()``
unregisters. No call site registers a peer, so no call site can forget to.
That matters most on the teardown path: ``evict_principal`` (ADR 0027) reaches
``Session.cleanup()`` via ``SessionManager.remove_session``, so an evicted
principal stops receiving broadcasts without eviction knowing peers exist.

Subclasses MUST call ``super().__init__(dispatcher)``. Registering before the
subclass constructor finishes is safe — a fresh bus has no subscriptions, so a
broadcast arriving in that window fans out to nothing.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Callable, Type, TypeVar

from .bus import SignalBus
from .signal import Signal

if TYPE_CHECKING:
    from .dispatcher import SignalDispatcher

S = TypeVar("S", bound=Signal)

logger = logging.getLogger(__name__)


class SignalPeer:
    """One endpoint on the signal fabric: a private bus plus dispatcher membership."""

    def __init__(self, dispatcher: "SignalDispatcher") -> None:
        """Create a peer and register it for cross-peer fan-out.

        Args:
            dispatcher: The process-wide :class:`SignalDispatcher`. Held as a
                strong reference — the dispatcher outlives every peer, and a
                peer with a dead dispatcher could not publish at all.
        """
        self.peer_id: str = str(uuid.uuid4())
        self._dispatcher: "SignalDispatcher" = dispatcher

        # The only intra-peer dispatch channel. Editors auto-subscribe their
        # ``@redraw_on`` / ``@react_on`` decorated methods at instantiation;
        # panels contribute signal types via ``redraw_on=`` on ``@panel(...)``;
        # AppShell subscribes its workspace-mutation handlers directly.
        self._bus: SignalBus = SignalBus()

        dispatcher.register(self)

    def publish(self, signal: Signal) -> None:
        """Publish a typed signal.

        Routing depends on ``type(signal).cross_session``:

        - ``False`` (local-only): fans out to every handler subscribed via
          :meth:`subscribe` for ``type(signal)``. Registration-order,
          error-isolated per handler.
        - ``True`` (cross-peer): delegates to
          :meth:`SignalDispatcher.broadcast`, which dispatches to every peer
          (including this one). The bus fan-out happens inside
          :meth:`_dispatch` on each receiving peer.

        Args:
            signal: A :class:`Signal` instance — either an observation
                (plain ``Signal`` subclass) or an imperative
                (``CommandSignal`` subclass).
        """
        if type(signal).cross_session:
            self._dispatcher.broadcast(signal)
            return

        self._bus.publish(signal)

    def subscribe(
        self,
        signal_type: Type[S],
        handler: Callable[[S], None],
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to signals of exactly ``signal_type``.

        Thin pass-through to this peer's :class:`SignalBus`. Exact-class match
        (subclasses do not inherit subscriptions); registration-order dispatch;
        error-isolated per handler.

        Returns:
            An unsubscribe handle. The framework holds these handles to tear
            down editor / panel / shell subscriptions at cleanup / hot-reload.
        """
        return self._bus.subscribe(signal_type, handler)

    def _dispatch(self, signal: Signal) -> None:
        """Internal: deliver a signal originating elsewhere (e.g. a peer
        broadcast) without re-triggering broadcast.

        Called by :meth:`SignalDispatcher.broadcast` on each receiving peer.
        Bypasses the ``cross_session`` check on purpose — the broadcast is
        already happening.
        """
        self._bus.publish(signal)

    def cleanup(self) -> None:
        """Leave the fan-out and drop every subscription.

        Unregistering happens FIRST, deliberately. ``SessionManager.remove_session``
        wraps ``cleanup()`` in a try/except that swallows failures, so if the
        bus teardown below ever raised while this peer were still registered,
        it would stay in the fan-out permanently. Unregister-first makes that
        unreachable.

        Subclasses overriding this MUST call ``super().cleanup()``.
        """
        self._dispatcher.unregister(self)
        self._bus.clear()


__all__ = ["SignalPeer"]
