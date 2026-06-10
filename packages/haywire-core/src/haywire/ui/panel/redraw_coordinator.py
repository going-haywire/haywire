from __future__ import annotations

import logging
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.session.session import Session
    from haywire.core.session.signals import Signal
    from haywire.ui.panel.focus import Focus
    from haywire.ui.panel.registry import PanelRegistry

logger = logging.getLogger(__name__)


class PanelRedrawCoordinator:
    """Owns one editor instance's panel-driven redraw subscriptions.

    A Focus-driven panel host (today only PropertiesEditor) wants to
    redraw whenever any display panel of its current focuses declares,
    via ``@panel(..., redraw_on=(...))``, that it cares about a signal —
    and to keep that subscription set correct as the panel catalog
    changes (install / uninstall / hot-reload).

    This coordinator owns BOTH surfaces of that machine:

    1. Per-signal bus subscriptions: one ``session.subscribe`` per signal
       type in the union of ``redraw_on`` across the host's focuses. Each
       fires ``on_redraw`` (the host re-mounts its panels).
    2. The panel registry's batch lifecycle channel: reconciles surface
       (1) whenever the catalog changes.

    Construction is inert. Call :meth:`start` to wire everything and
    :meth:`cleanup` to tear it down. Owned by the host editor; not shared.
    """

    def __init__(
        self,
        registry: "PanelRegistry",
        session: "Session",
        on_redraw: Callable[[], None],
        focus_provider: Callable[[], list[type["Focus"]]],
    ) -> None:
        """Construct (inert — no subscriptions until ``start``).

        Args:
            registry: PanelRegistry to query for ``redraw_on`` unions and
                to attach to for catalog-change reconciliation.
            session: Session whose signal bus carries the redraw signals.
            on_redraw: Called (no args) when a subscribed signal fires.
            focus_provider: Returns the host's current focus list. Called
                on every (re)build so the host stays the single source of
                truth for "which focuses do I show".
        """
        self._registry = registry
        self._session = session
        self._on_redraw = on_redraw
        self._focus_provider = focus_provider
        self._unsubscribes: list[Callable[[], None]] = []
        self._attached = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Attach to the registry lifecycle channel and build the
        per-signal subscription set. Idempotent attach; safe to call once
        per coordinator instance."""
        if not self._attached:
            try:
                self._registry.add_batch_event_subscriber(self._on_registry_event)
                self._attached = True
            except Exception as exc:
                logger.warning(f"PanelRedrawCoordinator: registry attach raised: {exc}")
        self._rebuild()

    def cleanup(self) -> None:
        """Drop all per-signal subscriptions and detach from the registry
        lifecycle channel. Safe to call multiple times."""
        self._unsubscribe_all()
        if self._attached:
            try:
                self._registry.remove_batch_event_subscriber(self._on_registry_event)
            except Exception as exc:
                logger.warning(f"PanelRedrawCoordinator: registry detach raised: {exc}")
            self._attached = False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Drop current per-signal subs and re-subscribe to the union of
        ``redraw_on`` signals across the host's current focuses."""
        self._unsubscribe_all()
        signal_types: set[type["Signal"]] = set()
        try:
            for focus in self._focus_provider():
                signal_types |= self._registry.get_redraw_signals_for_focus(focus)
        except Exception as exc:
            logger.warning(f"PanelRedrawCoordinator: get_redraw_signals_for_focus raised: {exc}")
            return
        if not signal_types:
            return
        handler = self._make_redraw_handler()
        for signal_type in signal_types:
            self._unsubscribes.append(self._session.subscribe(signal_type, handler))

    def _make_redraw_handler(self) -> Callable[["Signal"], None]:
        """Closure subscribed to every redraw signal. The panel author
        already declared the intent via ``redraw_on=``; the handler just
        asks the host to redraw."""

        def _on_signal(signal: "Signal") -> None:
            del signal  # forwarded, not inspected
            self._on_redraw()

        return _on_signal

    def _unsubscribe_all(self) -> None:
        """Call every held unsubscribe handle, then clear. Idempotent."""
        for unsub in self._unsubscribes:
            try:
                unsub()
            except Exception as exc:
                logger.warning(f"PanelRedrawCoordinator: unsubscribe raised: {exc}")
        self._unsubscribes.clear()

    def _on_registry_event(self, events: list) -> None:
        """Reconcile on any catalog change, then ask the host to redraw.

        We don't inspect the event list: any event might change the union
        (a panel registers / unregisters / reloads with a different
        ``redraw_on=``). Drop all subs and recompute. The catalog change
        can mean new signal types appeared, so the current rendered state
        may be stale — ask for a redraw too."""
        del events  # consumed by the LifeCycleBatchCallback interface
        self._rebuild()
        self._on_redraw()
