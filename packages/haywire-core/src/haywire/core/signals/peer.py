"""SignalPeer — anything that holds a signal bus and joins the fan-out.

One endpoint through which an outside entity — a browser tab, an agent over
MCP, a CLI — reaches the app's live state. Owns a private ``SignalBus`` and is
registered with a ``SignalDispatcher`` so cross-peer signals reach it.

Registration is by construction: ``__init__`` registers, ``cleanup()``
unregisters, so no call site can forget either. Subclasses MUST call
``super().__init__(dispatcher)``.
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
        """Create a peer and register it for cross-peer fan-out."""
        self.peer_id: str = str(uuid.uuid4())
        self._dispatcher: "SignalDispatcher" = dispatcher

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
          including this one, via :meth:`_dispatch`.
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

        Exact-class match — subclasses do not inherit subscriptions.

        Returns:
            An unsubscribe handle.
        """
        return self._bus.subscribe(signal_type, handler)

    def _dispatch(self, signal: Signal) -> None:
        """Deliver a signal originating elsewhere, without re-broadcasting.

        Called by :meth:`SignalDispatcher.broadcast` on each receiving peer;
        bypasses the ``cross_session`` check because the broadcast is already
        under way.
        """
        self._bus.publish(signal)

    def cleanup(self) -> None:
        """Leave the fan-out and drop every subscription.

        Unregisters FIRST: callers wrap ``cleanup()`` in a try/except that
        swallows failures, so a raising bus teardown would otherwise strand
        this peer in the fan-out permanently.

        Subclasses overriding this MUST call ``super().cleanup()``.
        """
        self._dispatcher.unregister(self)
        self._bus.clear()


__all__ = ["SignalPeer"]
