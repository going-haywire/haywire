"""Tests for SelectionToolbarProvider and SelectionToolbarHandlers."""

import haywire.core.graph.editor  # noqa: F401

from unittest.mock import MagicMock

from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
)
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
    SelectionToolbarProvider,
    SelectionToolbarHandlers,
)


def _provider(monkeypatch):
    ctx = MagicMock()
    session = MagicMock()
    registry = MagicMock()
    # No panels visible by default
    registry.get_panels_for_action.return_value = []
    prov = SelectionToolbarProvider(
        context=ctx,
        session=session,
        panel_registry=registry,
        on_emit_event=MagicMock(),
        on_emit_sync_event=MagicMock(),
    )
    return prov, registry


def test_show_no_visible_panels_opens_nothing(monkeypatch):
    prov, registry = _provider(monkeypatch)
    monkeypatch.setattr(
        "haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar.visible_panels",
        lambda classes, ctx: [],
    )
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._toolbar_popup is None


def test_handler_routes_bounds_to_show(monkeypatch):
    prov, _ = _provider(monkeypatch)
    prov.show_at = MagicMock()
    prov.hide = MagicMock()
    handlers = SelectionToolbarHandlers(provider=prov)

    handlers.process_selection_bounds(SelectionBoundsEvent(left=10.0, top=20.0, right=110.0, bottom=70.0))
    prov.show_at.assert_called_once_with((10.0, 20.0, 110.0, 70.0))


def test_handler_routes_hide(monkeypatch):
    prov, _ = _provider(monkeypatch)
    prov.show_at = MagicMock()
    prov.hide = MagicMock()
    handlers = SelectionToolbarHandlers(provider=prov)

    handlers.process_selection_bounds_hide(SelectionBoundsHideEvent())
    prov.hide.assert_called_once()


def test_open_overflow_emits_selection_context(monkeypatch):
    prov, _ = _provider(monkeypatch)
    from haywire.ui.components.graph.event_definitions import ContextMenuSelectedEvent

    prov._last_bounds = (10.0, 20.0, 110.0, 70.0)
    emitted = []
    prov._on_emit_event = lambda ev: emitted.append(ev)
    prov.open_overflow_menu()
    assert any(isinstance(ev, ContextMenuSelectedEvent) for ev in emitted)
