"""Tests for SelectionToolbarProvider and SelectionToolbarHandlers."""

from unittest.mock import MagicMock

import pytest

from haywire.ui.components.graph.event_definitions import (
    SelectionBoundsEvent,
    SelectionBoundsHideEvent,
)
from haybale_graph_editor.editors.graph_canvas.handlers import selection_toolbar as selection_toolbar_module
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
    SelectionToolbarHandlers,
    SelectionToolbarProvider,
)
from haybale_graph_editor.surfaces import SelectionActions


def _provider(monkeypatch, *, menu_provider=None):
    ctx = MagicMock()
    session = MagicMock()
    registry = MagicMock()
    # No panels on the surface by default
    registry.get_panels.return_value = []
    prov = SelectionToolbarProvider(
        context=ctx,
        session=session,
        panel_registry=registry,
        on_emit_event=MagicMock(),
        on_emit_sync_event=MagicMock(),
        menu_provider=menu_provider,
    )
    # The surface gate runs first; default it open so the panel path is reached.
    monkeypatch.setattr(selection_toolbar_module, "_poll_surface", lambda surface, ctx: True)
    return prov, registry


def test_show_with_no_panels_opens_nothing(monkeypatch):
    prov, _ = _provider(monkeypatch)
    monkeypatch.setattr(selection_toolbar_module, "partition_panels", lambda classes, ctx: ([], []))
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._toolbar_popup is None


def test_show_hides_when_the_surface_does_not_apply(monkeypatch):
    """The surface gate runs before anything is queried or built."""
    prov, registry = _provider(monkeypatch)
    monkeypatch.setattr(selection_toolbar_module, "_poll_surface", lambda surface, ctx: False)
    prov.hide = MagicMock()
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    prov.hide.assert_called_once()
    registry.get_panels.assert_not_called()


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


def test_reposition_renders_unconditionally(monkeypatch):
    """The old ``visible != self._rendered_panels`` guard is gone.

    It held only the *root* surface's panels, so once the ⋯ hosts a surface it
    could not see anything nested: a poll flip inside the flyout with an
    unchanged root set would render stale and never correct. A rebuild now
    costs one row per gesture end, and every selectionBounds emission is
    edge-triggered rather than per pan frame.
    """
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    monkeypatch.setattr(selection_toolbar_module, "partition_panels", lambda classes, ctx: ([PanelA], []))
    prov._build_popup = MagicMock(return_value=MagicMock())
    prov._render_into_popup = MagicMock(return_value=True)

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._render_into_popup.call_count == 1

    prov.show_at((40.0, 40.0, 140.0, 90.0))
    assert prov._render_into_popup.call_count == 2
    prov._toolbar_popup.run_method.assert_called_with("setPosition", 90.0, 0.0)


def test_toolbar_hides_when_nothing_drew(monkeypatch):
    """A toolbar holding only the ⋯, whose flyout body came up empty, is not
    worth showing — the same emptiness rule the context-menu host uses."""
    prov, _ = _provider(monkeypatch)

    class HostingPanel:
        pass

    monkeypatch.setattr(
        selection_toolbar_module, "partition_panels", lambda classes, ctx: ([HostingPanel], [])
    )
    popup = MagicMock()
    popup.is_open = True
    prov._build_popup = MagicMock(return_value=popup)
    prov._render_into_popup = MagicMock(return_value=False)

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    popup.close.assert_called_once()


def test_hide_preserves_dom(monkeypatch):
    """hide() must NOT tear the popup down: it closes via Vue (v-show) and keeps
    the rendered DOM across one gesture's hide/show round trip.
    """
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    monkeypatch.setattr(selection_toolbar_module, "partition_panels", lambda classes, ctx: ([PanelA], []))
    popup = MagicMock()
    popup.is_open = True
    prov._build_popup = MagicMock(return_value=popup)
    prov._render_into_popup = MagicMock(return_value=True)

    prov.show_at((0.0, 0.0, 100.0, 50.0))

    # Gesture hide: Vue-side close only, popup object and DOM survive.
    prov.hide()
    popup.close.assert_called_once()
    popup.delete.assert_not_called()
    assert prov._toolbar_popup is popup

    # Re-show: re-opened, and re-rendered (no guard any more).
    popup.is_open = False
    prov.show_at((0.0, 0.0, 100.0, 50.0))
    popup.open.assert_called_once()
    assert prov._render_into_popup.call_count == 2


def test_destroy_tears_down(monkeypatch):
    """destroy() is the real lifecycle teardown: it deletes the popup and
    forces the next show to rebuild it.
    """
    prov, _ = _provider(monkeypatch)

    class PanelA:
        pass

    monkeypatch.setattr(selection_toolbar_module, "partition_panels", lambda classes, ctx: ([PanelA], []))
    popup = MagicMock()
    popup.is_open = True
    prov._build_popup = MagicMock(return_value=popup)
    prov._render_into_popup = MagicMock(return_value=True)

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    prov.destroy()
    popup.delete.assert_called_once()
    assert prov._toolbar_popup is None

    prov.show_at((0.0, 0.0, 100.0, 50.0))
    assert prov._build_popup.call_count == 2


# ---------------------------------------------------------------------------
# The host contract — the latent bug the surface model's isinstance catches
# ---------------------------------------------------------------------------


def test_provider_satisfies_selection_actions(monkeypatch):
    """SelectionToolbar.provides is SelectionActions, and render_surface checks
    the chosen host against it with isinstance().

    Before the surface model there was no structural check anywhere in the
    panel system, so this class claimed both ToolbarActions and
    SelectionContextActions while implementing 3 of the latter's 7 verbs.
    """
    prov, _ = _provider(monkeypatch)
    assert isinstance(prov, SelectionActions)


@pytest.mark.parametrize(
    ("verb", "args"),
    [
        ("paste_at_click", ()),
        ("redraw_selection", ()),
        ("revalidate_selection", ()),
        ("reset_selection", ()),
        ("dissolve_reroute", ("n1",)),
    ],
)
def test_missing_verbs_delegate_to_the_menu_provider(monkeypatch, verb, args):
    """Fixed by delegation, not by duplication: SessionContextMenuProvider
    already implements all seven against the same canvas."""
    menu_provider = MagicMock()
    prov, _ = _provider(monkeypatch, menu_provider=menu_provider)
    getattr(prov, verb)(*args)
    getattr(menu_provider, verb).assert_called_once_with(*args)


def test_delegation_without_a_menu_provider_is_a_no_op(monkeypatch):
    """Raising from a click handler would take down the popup for a case the
    canvas never produces."""
    prov, _ = _provider(monkeypatch)
    prov.reset_selection()  # must not raise


def test_copy_and_delete_are_emitted_directly(monkeypatch):
    from haywire.ui.components.graph.event_definitions import (
        UserCopySelectedEvent,
        UserRemoveEvent,
    )

    prov, _ = _provider(monkeypatch)
    emitted = []
    prov._on_emit_event = lambda ev: emitted.append(ev)
    prov._context.data.__getitem__.return_value = MagicMock(selected_nodes={"n1"}, selected_edges=set())

    prov.copy_selection()
    prov.delete_selection()
    assert any(isinstance(ev, UserCopySelectedEvent) for ev in emitted)
    assert any(isinstance(ev, UserRemoveEvent) for ev in emitted)
