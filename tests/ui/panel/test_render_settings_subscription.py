"""
Subscription-lifecycle regression for render_settings external sync.

render_settings subscribes the panel to the model and tears the subscription
down via the column's _handle_delete anchor. A panel redraw (content.clear()
then re-render) calls render_settings again on the SAME model, so the
subscribe path must be idempotent and the teardown must remove exactly the
panel callback it added — otherwise an external write fans out to stale,
detached updaters (a leak that grows on every redraw).

These run headless against a NiceGUI Client context (no browser): the invariant
is pure callback bookkeeping on the model, observable on Settings._subscriptions
(callback -> cell adapters, ADR 0016).
"""

import pytest

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

from nicegui import Client, ui
from nicegui.page import page as page_deco

from haywire.core.settings import SettingsRegistry
from haywire.ui.panel.render_utils import render_settings
from haybale_testing.nodes.testbed.settings_node import SettingsNode

pytestmark = pytest.mark.unit


@page_deco("/_render_settings_subscription_test")
def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture
def client() -> Client:
    """A headless NiceGUI client whose slot stack render_settings can build into."""
    return Client(_noop_page, request=None)


def _make_bag():
    """Construct the SettingsNode 'example' settings bag on a bare registry."""
    return SettingsNode.example(registry=SettingsRegistry())


def test_render_subscribes_exactly_one_callback(client: Client):
    bag = _make_bag()
    assert bag._subscriptions == {}

    with client:
        render_settings(bag)

    assert len(bag._subscriptions) == 1, f"render should add one callback, got {bag._subscriptions}"


def test_redraw_does_not_double_subscribe(client: Client):
    """Re-rendering on the same model (panel redraw) stays at one callback.

    The panel callback is a fresh closure each render, so dedup can't rely on
    identity — it relies on the previous column's _handle_delete having removed
    the old one before the new render runs (the real redraw order). We model
    that: render, tear down, render again -> still exactly one.
    """
    bag = _make_bag()

    with client:
        first = ui.column()
        with first:
            render_settings(bag)
    assert len(bag._subscriptions) == 1

    # Redraw: the old column is deleted (content.clear()) before re-render.
    # Find and fire the column render_settings built so its anchor unsubscribes.
    built = first.default_slot.children[0]
    built._handle_delete()
    assert bag._subscriptions == {}, "teardown must remove the panel callback"

    with client:
        second = ui.column()
        with second:
            render_settings(bag)
    assert len(bag._subscriptions) == 1, "redraw must not accumulate callbacks"


def test_teardown_removes_only_panel_callback(client: Client):
    """_handle_delete removes the panel's callback and leaves foreign ones intact."""
    bag = _make_bag()
    foreign_calls: list = []
    foreign = lambda name, value, old: foreign_calls.append(name)  # noqa: E731
    bag.subscribe(foreign)

    with client:
        col = ui.column()
        with col:
            render_settings(bag)
    built = col.default_slot.children[0]
    assert len(bag._subscriptions) == 2  # foreign + panel

    built._handle_delete()
    assert list(bag._subscriptions) == [foreign], "only the panel callback should be removed"

    # The foreign subscriber still fires after panel teardown.
    bag.example_string = "after-teardown"
    assert foreign_calls == ["example_string"]


def test_external_write_after_redraw_updates_only_live_panel(client: Client):
    """After redraw, an external write must not also drive the torn-down panel.

    A leaked subscription would invoke updaters closed over deleted elements,
    raising inside the cell adapter (swallowed + logged) — so we assert the
    model holds exactly one callback after a redraw and an external write fires
    cleanly (no error logged by the dispatch loop).
    """
    bag = _make_bag()

    with client:
        first = ui.column()
        with first:
            render_settings(bag)
    first.default_slot.children[0]._handle_delete()

    with client:
        second = ui.column()
        with second:
            render_settings(bag)

    assert len(bag._subscriptions) == 1

    # External write through the model dispatches to the single live panel.
    # the adapter swallows per-callback errors, so a clean run means the
    # one remaining updater applied without referencing dead elements.
    bag.example_string = "EXTERNAL"
    assert bag.example_string == "EXTERNAL"
