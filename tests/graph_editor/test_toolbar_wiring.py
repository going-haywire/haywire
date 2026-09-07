"""Tests for the toolbar's two real mechanisms, not their wiring call sites.

1. `build_event_handler_map` actually resolves `@handles_event` methods on a
   real handler class into a dispatchable map.
2. `get_redraw_signals` actually returns empty across the real panel tree
   reachable from `SelectionToolbar` — the tripwire for a `redraw_on` added
   anywhere under it, since that surface is event-driven (ADR-0029) and must
   subscribe to nothing.

Deliberately NOT here: a test that registers panel classes into a throwaway
registry and asserts they come back out (proves dict insertion, not the
architecture), or one that greps `graph_canvas_manager`'s source text for
identifier names (passes on a broken wiring, only catches a fully absent
one). Either would need a real GraphCanvasManager/UI integration test to say
anything an implementation-detail unit test can't already fake.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_toolbar_handler_keys_present():
    """SelectionToolbarHandlers contributes selectionBounds + selectionBoundsHide
    when wired via build_event_handler_map.
    """

    from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
        SelectionToolbarHandlers,
        SelectionToolbarProvider,
    )
    from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map
    from unittest.mock import MagicMock

    # Minimal stub for SelectionToolbarProvider — we only need a valid instance
    provider = MagicMock(spec=SelectionToolbarProvider)
    handlers = SelectionToolbarHandlers(provider=provider)

    handler_map = build_event_handler_map([handlers])

    assert "selectionBounds" in handler_map, "selectionBounds event not wired"
    assert "selectionBoundsHide" in handler_map, "selectionBoundsHide event not wired"


def test_get_redraw_signals_on_selection_toolbar_is_empty(tmp_path):
    """SelectionToolbar is event-driven (ADR-0029, Redraw) and subscribes to
    nothing — this walks into SelectionMenu via the overflow panel's own
    hosts=(SelectionMenu,), so a redraw_on anywhere in that whole tree would
    be inert and this is the tripwire that makes it loud. Registers every
    real panel reachable from SelectionToolbar's root (the three toolbar
    panels plus whatever sits on SelectionMenu) so the union is computed over
    the actual production tree, not a synthetic stand-in.
    """
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.core.library.identity import LibraryIdentity
    from haybale_graph_editor.panels.graph.toolbar.selection import (
        CollapseToolbarPanel,
        LockToolbarPanel,
        SelectionOverflowPanel,
    )
    from haybale_graph_editor.panels.graph.menu.selection import selection as selection_menu_module
    from haybale_graph_editor.surfaces import SelectionToolbar

    identity = LibraryIdentity(
        label="Graph Editor Test",
        version="0.0.1",
        folder_path=str(tmp_path),
        module_name="haybale_graph_editor",
        name="graph_editor",
    )

    registry = PanelRegistry()
    for cls in (CollapseToolbarPanel, LockToolbarPanel, SelectionOverflowPanel):
        registry._register_class(cls, identity)

    # SelectionMenu's own panels, reached one hop below the overflow panel —
    # registering them is what makes this walk the whole real tree instead of
    # stopping at the toolbar's own three panels (which declare no redraw_on
    # and would pass trivially either way).
    import inspect

    for _, obj in inspect.getmembers(selection_menu_module, inspect.isclass):
        if getattr(obj, "class_identity", None) is not None:
            registry._register_class(obj, identity)

    assert registry.get_redraw_signals(SelectionToolbar) == set()
