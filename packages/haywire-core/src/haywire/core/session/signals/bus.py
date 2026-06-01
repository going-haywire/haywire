from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Dict, List, Tuple, Type, TypeVar

from .signal import Signal

logger = logging.getLogger(__name__)


# Handler signature: ``(signal) -> None``. The ``ctx`` parameter described in
# the design doc is bound at subscribe-time on the ``Session`` layer (so the
# bus itself stays signal-only and reusable). See ``Session.subscribe``.
SignalHandler = Callable[[Signal], None]

# Used by ``subscribe`` so a ``Callable[[SelectionMoved], None]`` is accepted
# for ``signal_type=SelectionMoved`` without a downcast cast at every site.
S = TypeVar("S", bound=Signal)


class SignalBus:
    """A typed pub/sub bus, session-scoped.

    One instance lives on each :class:`~haywire.core.session.session.Session`.
    Subscribers register a handler for an exact signal class; publishes fan
    out only to handlers registered for ``type(signal)``.

    Not thread-safe by design — all session work runs on the NiceGUI event
    loop's main thread.
    """

    def __init__(self) -> None:
        # ``list`` (not ``set``) to preserve registration order on dispatch.
        # ``subscribe`` does not dedupe: passing the same handler for the
        # same signal type twice registers two subscriptions and produces
        # two unsubscribe handles. The framework's auto-wiring paths never
        # do this — every closure built by ``EditorWrapper`` is a fresh
        # function object, even when two methods share a name across a
        # subclass override — so duplicates would only arise from direct
        # misuse of ``bus.subscribe``.
        self._handlers: Dict[Type[Signal], List[SignalHandler]] = defaultdict(list)

    def subscribe(
        self,
        signal_type: Type[S],
        handler: Callable[[S], None],
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to signals of exactly ``signal_type``.

        Args:
            signal_type: A :class:`Signal` subclass. Exact-class match
                on publish — subclasses do not inherit subscriptions.
            handler:    A sync callable taking the signal instance.

        Returns:
            An unsubscribe handle. Calling it removes this subscription;
            calling it twice is a no-op. The framework holds these handles
            to tear down subscriptions at editor cleanup / hot-reload.
        """
        if not isinstance(signal_type, type) or not issubclass(signal_type, Signal):
            raise TypeError(
                f"SignalBus.subscribe: signal_type must be a Signal subclass; got {signal_type!r}"
            )
        # Stored as a ``SignalHandler`` (``Callable[[Signal], None]``) — the
        # generic on the signature is only for caller ergonomics. Dispatch
        # narrows by exact ``type(signal)`` match, so the runtime always passes
        # the right subclass into the handler.
        self._handlers[signal_type].append(handler)  # type: ignore[arg-type]

        def _unsubscribe() -> None:
            handlers = self._handlers.get(signal_type)
            if handlers is None:
                return
            try:
                handlers.remove(handler)  # type: ignore[arg-type]
            except ValueError:
                # Already removed — double-unsubscribe is a no-op.
                return
            if not handlers:
                # Tidy up: drop empty buckets so introspection stays clean.
                self._handlers.pop(signal_type, None)

        return _unsubscribe

    def publish(self, signal: Signal) -> None:
        """Dispatch ``signal`` to every handler subscribed to its exact class.

        Handlers fire in registration order. Each handler runs in its own
        ``try/except``: a raising handler is logged and the next handler
        still fires. Multiple raisers in one publish do not short-circuit.

        Args:
            signal: An instance of a :class:`Signal` subclass.
        """
        # Iterate over a snapshot so a handler that subscribes/unsubscribes
        # during dispatch does not mutate the list we're iterating over.
        # New subscriptions made mid-dispatch land in the next publish, not
        # this one — matches the registration-order rule.
        handlers = tuple(self._handlers.get(type(signal), ()))
        for handler in handlers:
            try:
                # Sync call only; coroutines are not awaited. Awaiting here would
                # hit the NiceGUI async slot-stack footgun (.insights/feedback_nicegui_async.md).
                handler(signal)
            except Exception:
                logger.exception(
                    "SignalBus: handler %r raised during publish of %s; continuing",
                    handler,
                    type(signal).__name__,
                )

    # ------------------------------------------------------------------
    # Introspection helpers — framework-internal; not part of the public
    # author surface.
    # ------------------------------------------------------------------

    def subscriber_count(self, signal_type: Type[Signal]) -> int:
        """Return the number of handlers currently subscribed to ``signal_type``.

        Used by tests and diagnostics. Not part of the author API.
        """
        return len(self._handlers.get(signal_type, ()))

    def subscribed_types(self) -> Tuple[Type[Signal], ...]:
        """Return every signal class that currently has at least one handler.

        Used by tests and diagnostics. Not part of the author API.
        """
        return tuple(self._handlers.keys())

    def clear(self) -> None:
        """Drop every subscription. Used by ``Session.cleanup()``."""
        self._handlers.clear()


__all__ = ["SignalBus", "SignalHandler"]
