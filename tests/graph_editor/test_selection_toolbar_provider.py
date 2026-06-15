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


def test_reposition_same_panels_skips_rerender(monkeypatch):
    """Panning keeps the same panel set, so the DOM must not be rebuilt —
    only the popup is repositioned. Rebuilding every frame caused jerky pans.
    """
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    monkeypatch.setattr(
        "haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar.visible_panels",
        lambda classes, ctx: [PanelA],
    )
    prov._build_popup = MagicMock(return_value=MagicMock())
    prov._render_into_popup = MagicMock()

    # First show: builds popup and renders once.
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._render_into_popup.call_count == 1

    # Reposition (pan) with the identical panel set: no re-render.
    prov.show_at((40.0, 40.0, 140.0, 90.0))
    assert prov._render_into_popup.call_count == 1
    prov._toolbar_popup.run_method.assert_called_with("setPosition", 90.0, 0.0)


def test_changed_panels_triggers_rerender(monkeypatch):
    """A different visible panel set (e.g. new selection) must rebuild the DOM."""
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    class PanelB:
        pass

    sets = [[PanelA], [PanelA, PanelB]]
    monkeypatch.setattr(
        "haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar.visible_panels",
        lambda classes, ctx: sets.pop(0),
    )
    prov._build_popup = MagicMock(return_value=MagicMock())
    prov._render_into_popup = MagicMock()

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._render_into_popup.call_count == 2


def test_hide_preserves_dom_and_skips_rerender_on_reshow(monkeypatch):
    """hide() must NOT tear the popup down: it closes via Vue (v-show) and keeps
    the rendered DOM, so a same-selection re-show re-opens without re-rendering.
    Tearing down + rebuilding every pan frame is what made panning jerky.
    """
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    monkeypatch.setattr(
        "haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar.visible_panels",
        lambda classes, ctx: [PanelA],
    )
    popup = MagicMock()
    popup.is_open = True
    prov._build_popup = MagicMock(return_value=popup)
    prov._render_into_popup = MagicMock()

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._render_into_popup.call_count == 1

    # Gesture hide: Vue-side close only, popup object and DOM survive.
    prov.hide()
    popup.close.assert_called_once()
    popup.delete.assert_not_called()
    assert prov._toolbar_popup is popup

    # Re-show with the same selection: re-open, no re-render.
    popup.is_open = False
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    popup.open.assert_called_once()
    assert prov._render_into_popup.call_count == 1


def test_destroy_tears_down_and_forces_rerender(monkeypatch):
    """destroy() is the real lifecycle teardown: it deletes the popup and forces
    the next show to rebuild.
    """
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    monkeypatch.setattr(
        "haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar.visible_panels",
        lambda classes, ctx: [PanelA],
    )
    popup = MagicMock()
    popup.is_open = True
    prov._build_popup = MagicMock(return_value=popup)
    prov._render_into_popup = MagicMock()

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    prov.destroy()
    popup.delete.assert_called_once()
    assert prov._toolbar_popup is None
    assert prov._rendered_panels is None

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._render_into_popup.call_count == 2


def test_open_overflow_emits_selection_context(monkeypatch):
    prov, _ = _provider(monkeypatch)
    from haywire.ui.components.graph.event_definitions import ContextMenuSelectedEvent

    prov._last_bounds = (10.0, 20.0, 110.0, 70.0)
    emitted = []
    prov._on_emit_event = lambda ev: emitted.append(ev)
    prov.open_overflow_menu()
    assert any(isinstance(ev, ContextMenuSelectedEvent) for ev in emitted)
