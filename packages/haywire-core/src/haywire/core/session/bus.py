# packages/haywire-core/src/haywire/core/session/bus.py
"""
Session-scoped typed event bus.

Step 4 of the event-bus redesign (see
``internals/speculatives/event_bus_redesign.md``). The bus is the primary
dispatch channel within a session: editors and panels declare which
:class:`~haywire.core.session.signals.ContextSignal` subclasses they care
about (via :func:`~haywire.core.session.handlers.redraw_on` /
:func:`~haywire.core.session.handlers.react_on` on editors, or the
``redraw_on=`` kwarg on ``@panel(...)``), and the framework dispatches
matching events only to those subscribers.

The bus itself is intentionally small: a ``defaultdict[type, list]`` of
handlers, an exact-class match on publish, error isolation per handler.
Cross-session routing, decorator-driven auto-subscription, and bridging
with the legacy ``Session.signal()`` path all live on ``Session`` (see
:mod:`haywire.core.session.session`) — the bus does not know they exist.

Design choices worth keeping in mind:

- **Exact-class match, not isinstance.** A subscriber to ``SelectionMoved``
  does not fire for a hypothetical ``CanvasSelectionMoved(SelectionMoved)``.
  The design doc's §"Event Identity" allows shallow hierarchies only when a
  real grouping subscription appears; we'd add it explicitly then.
- **Registration order.** Handlers fire in subscribe order. The design
  doc's §"Bus Scope and Mechanics" explicitly states this and pushes back
  on any ordering primitives.
- **Error isolation per handler.** A raising handler is logged and the
  next one runs. Authors should not rely on cross-handler ordering for
  correctness.
- **Sync only.** Handlers are plain callables; coroutines are not awaited.
  Aligns with today's sync signal-callback semantics and avoids the
  NiceGUI async slot-stack footgun.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Dict, List, Tuple, Type

from .signals import ContextSignal

logger = logging.getLogger(__name__)


# Handler signature: ``(event) -> None``. The ``ctx`` parameter described in
# the design doc is bound at subscribe-time on the ``Session`` layer (so the
# bus itself stays event-only and reusable). See ``Session.subscribe``.
EventHandler = Callable[[ContextSignal], None]


class EventBus:
    """A typed pub/sub bus, session-scoped.

    One instance lives on each :class:`~haywire.core.session.session.Session`.
    Subscribers register a handler for an exact event class; publishes fan
    out only to handlers registered for ``type(event)``.

    Not thread-safe by design — all session work runs on the NiceGUI event
    loop's main thread. If cross-thread emission becomes a requirement,
    revisit at that point (and probably wrap with ``call_soon_threadsafe``
    on the ``Session`` layer rather than complicating the bus itself).
    """

    def __init__(self) -> None:
        # ``list`` (not ``set``) to preserve registration order on dispatch.
        # Duplicate subscriptions of the same handler to the same event type
        # are allowed and fire once per subscription — matches the natural
        # decorator semantics where stacking is intentional.
        self._handlers: Dict[Type[ContextSignal], List[EventHandler]] = defaultdict(list)

    def subscribe(
        self,
        event_type: Type[ContextSignal],
        handler: EventHandler,
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to events of exactly ``event_type``.

        Args:
            event_type: A :class:`ContextSignal` subclass. Exact-class match
                on publish — subclasses do not inherit subscriptions.
            handler:    A sync callable taking the event instance.

        Returns:
            An unsubscribe handle. Calling it removes this subscription;
            calling it twice is a no-op. The framework holds these handles
            to tear down subscriptions at editor cleanup / hot-reload.
        """
        if not isinstance(event_type, type) or not issubclass(event_type, ContextSignal):
            raise TypeError(
                f"EventBus.subscribe: event_type must be a ContextSignal subclass; got {event_type!r}"
            )
        self._handlers[event_type].append(handler)

        def _unsubscribe() -> None:
            handlers = self._handlers.get(event_type)
            if handlers is None:
                return
            try:
                handlers.remove(handler)
            except ValueError:
                # Already removed — double-unsubscribe is a no-op.
                return
            if not handlers:
                # Tidy up: drop empty buckets so introspection stays clean.
                self._handlers.pop(event_type, None)

        return _unsubscribe

    def publish(self, event: ContextSignal) -> None:
        """Dispatch ``event`` to every handler subscribed to its exact class.

        Handlers fire in registration order. Each handler runs in its own
        ``try/except``: a raising handler is logged and the next handler
        still fires. Multiple raisers in one publish do not short-circuit.

        Args:
            event: An instance of a :class:`ContextSignal` subclass.
        """
        # Iterate over a snapshot so a handler that subscribes/unsubscribes
        # during dispatch does not mutate the list we're iterating over.
        # New subscriptions made mid-dispatch land in the next publish, not
        # this one — matches the design doc's registration-order rule.
        handlers = tuple(self._handlers.get(type(event), ()))
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "EventBus: handler %r raised during publish of %s; continuing",
                    handler,
                    type(event).__name__,
                )

    # ------------------------------------------------------------------
    # Introspection helpers — framework-internal; not part of the public
    # author surface.
    # ------------------------------------------------------------------

    def subscriber_count(self, event_type: Type[ContextSignal]) -> int:
        """Return the number of handlers currently subscribed to ``event_type``.

        Used by tests and diagnostics. Not part of the author API.
        """
        return len(self._handlers.get(event_type, ()))

    def subscribed_types(self) -> Tuple[Type[ContextSignal], ...]:
        """Return every event class that currently has at least one handler.

        Used by tests and diagnostics. Not part of the author API.
        """
        return tuple(self._handlers.keys())

    def clear(self) -> None:
        """Drop every subscription. Used by ``Session.cleanup()``."""
        self._handlers.clear()


__all__ = ["EventBus", "EventHandler"]
