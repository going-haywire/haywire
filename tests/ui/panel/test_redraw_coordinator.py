"""Unit tests for PanelRedrawCoordinator.

The coordinator owns an editor's panel-driven redraw subscriptions:
per-signal bus subscriptions (one per redraw_on signal type declared by
display panels of the editor's focuses) plus the panel registry's batch
lifecycle channel used to reconcile that set on catalog change.

These tests exercise the coordinator directly with fakes — no
EditorWrapper, no real Session — which is the whole point of the
extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, cast


from haywire.core.signals import Signal
from haywire.ui.panel.redraw_coordinator import PanelRedrawCoordinator


# --- Fakes -----------------------------------------------------------------


@dataclass(frozen=True)
class _SigA(Signal):
    pass


@dataclass(frozen=True)
class _SigB(Signal):
    pass


class _FakeFocus:
    """Stand-in Focus class. The coordinator only uses identity / passes it
    straight to registry.get_redraw_signals_for_focus, so any object works."""

    id = "fake-focus"


class _FakeSession:
    """Records subscribe() calls and lets tests fire a signal type."""

    def __init__(self) -> None:
        self.handlers: dict[type, list[Callable]] = {}
        self.unsub_calls = 0

    def subscribe(self, signal_type, handler):
        self.handlers.setdefault(signal_type, []).append(handler)

        def _unsub():
            self.unsub_calls += 1
            lst = self.handlers.get(signal_type, [])
            lst.remove(handler)
            if not lst:
                self.handlers.pop(signal_type, None)

        return _unsub

    def fire(self, signal_type) -> None:
        for h in list(self.handlers.get(signal_type, [])):
            h(signal_type())


class _FakeRegistry:
    """Records batch-subscriber wiring and returns a fixed signal union."""

    def __init__(self, signals_by_focus: dict | None = None) -> None:
        self._signals_by_focus = signals_by_focus or {}
        self.batch_subscribers: list[Callable] = []

    def get_redraw_signals_for_focus(self, focus):
        return set(self._signals_by_focus.get(focus, set()))

    def add_batch_event_subscriber(self, cb) -> None:
        if cb not in self.batch_subscribers:
            self.batch_subscribers.append(cb)

    def remove_batch_event_subscriber(self, cb) -> None:
        if cb in self.batch_subscribers:
            self.batch_subscribers.remove(cb)

    def notify(self) -> None:
        for cb in list(self.batch_subscribers):
            cb([])


def _make_coordinator(registry, session):
    redraws: list[int] = []
    focus = _FakeFocus()
    coord = PanelRedrawCoordinator(
        registry=registry,
        session=session,
        on_redraw=lambda: redraws.append(1),
        focus_provider=lambda: cast(Any, [focus]),
    )
    return coord, redraws, focus


# --- Tests -----------------------------------------------------------------


def test_construction_is_inert():
    """Constructing the coordinator must not subscribe to anything."""
    registry = _FakeRegistry({})
    session = _FakeSession()
    coord, _redraws, _focus = _make_coordinator(registry, session)

    assert session.handlers == {}
    assert registry.batch_subscribers == []
    del coord


def test_start_subscribes_to_union_of_redraw_signals():
    """start() subscribes one handler per signal type in the union."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA, _SigB}}

    coord.start()

    assert set(session.handlers.keys()) == {_SigA, _SigB}
    # The coordinator attached exactly one bound-method callback to the
    # registry lifecycle channel.
    assert len(registry.batch_subscribers) == 1
    assert getattr(registry.batch_subscribers[0], "__self__", None) is coord


def test_subscribed_signal_fires_on_redraw():
    """Publishing a subscribed signal type invokes on_redraw."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA}}

    coord.start()
    session.fire(_SigA)

    assert redraws == [1]


def test_unsubscribed_signal_does_not_fire_redraw():
    """A signal type nobody declared must not be subscribed."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA}}

    coord.start()
    session.fire(_SigB)

    assert redraws == []


def test_start_with_empty_union_makes_no_subscriptions():
    """No redraw_on signals → no per-signal subs (but still attaches the
    lifecycle channel, so a later catalog change can add some)."""
    registry = _FakeRegistry({})
    session = _FakeSession()
    coord, _redraws, _focus = _make_coordinator(registry, session)

    coord.start()

    assert session.handlers == {}
    assert len(registry.batch_subscribers) == 1


def test_cleanup_drops_subs_and_detaches():
    """cleanup() unsubscribes every per-signal handle and detaches the
    lifecycle channel."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, _redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA, _SigB}}

    coord.start()
    assert session.unsub_calls == 0

    coord.cleanup()

    assert session.unsub_calls == 2
    assert session.handlers == {}
    assert registry.batch_subscribers == []


def test_cleanup_is_idempotent():
    """Calling cleanup twice must not raise or double-unsubscribe."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, _redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA}}

    coord.start()
    coord.cleanup()
    coord.cleanup()  # must be a no-op

    assert session.unsub_calls == 1
    assert registry.batch_subscribers == []


def test_catalog_change_rebuilds_subscriptions_and_redraws():
    """Firing the registry lifecycle channel recomputes the union and
    redraws once. Start with an empty union, then 'install' a panel that
    declares _SigA."""
    registry = _FakeRegistry({})
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)

    coord.start()
    assert session.handlers == {}
    session.fire(_SigA)
    assert redraws == []

    # 'Install': the union now includes _SigA. Fire the lifecycle channel.
    registry._signals_by_focus = {focus: {_SigA}}
    registry.notify()

    assert redraws == [1]  # the reconciliation itself redrew once
    redraws.clear()

    # Now _SigA publishes reach the coordinator.
    session.fire(_SigA)
    assert redraws == [1]


def test_rebuild_drops_stale_subscriptions():
    """A catalog change that removes a signal from the union must
    unsubscribe the stale per-signal handle."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, _redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA, _SigB}}

    coord.start()
    assert set(session.handlers.keys()) == {_SigA, _SigB}

    # 'Uninstall' the panel that declared _SigB.
    registry._signals_by_focus = {focus: {_SigA}}
    registry.notify()

    assert set(session.handlers.keys()) == {_SigA}


def test_registry_query_raising_degrades_gracefully():
    """If get_redraw_signals_for_focus raises, the coordinator logs and
    leaves zero subscriptions rather than propagating."""

    class _RaisingRegistry(_FakeRegistry):
        def get_redraw_signals_for_focus(self, focus):
            raise RuntimeError("intentional bad query")

    registry = _RaisingRegistry()
    session = _FakeSession()
    coord, _redraws, _focus = _make_coordinator(registry, session)

    coord.start()  # must not raise

    assert session.handlers == {}


def test_coordinator_is_exported_from_panel_package():
    """PanelRedrawCoordinator is importable from the package root, like
    PanelRegistry and Focus."""
    from haywire.ui.panel import PanelRedrawCoordinator as Exported

    assert Exported is PanelRedrawCoordinator
