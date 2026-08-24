"""Tests for toolbar wiring: SelectionToolbarHandlers in GraphCanvasManager
and toolbar panel registration via register_components().

Two test groups:
1. Unit tests — import SelectionToolbarHandlers and check the event keys it
   registers via build_event_handler_map. No app bootstrap required.
2. Unit tests — directly call register_components() on a Library stub and
   confirm CopyToolbarPanel / DeleteToolbarPanel / SelectionOverflowPanel land
   in a fresh PanelRegistry.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Handler-map coverage
# ---------------------------------------------------------------------------


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


def test_toolbar_handlers_wired_into_gcm_source():
    """GraphCanvasManager imports SelectionToolbarHandlers and wires it into
    build_event_handler_map. We verify this by inspecting the module source —
    if the class is not imported/referenced, the wiring is absent.
    """
    import inspect
    from haybale_graph_editor.editors.graph_canvas import graph_canvas_manager

    source = inspect.getsource(graph_canvas_manager)

    assert "SelectionToolbarHandlers" in source, (
        "SelectionToolbarHandlers not referenced in graph_canvas_manager — "
        "toolbar handlers are not wired into GraphCanvasManager"
    )
    assert "SelectionToolbarProvider" in source, (
        "SelectionToolbarProvider not referenced in graph_canvas_manager — "
        "toolbar provider is not created in GraphCanvasManager"
    )
    assert "toolbar_handlers" in source, (
        "toolbar_handlers attribute not present in graph_canvas_manager — "
        "handler object is not added to build_event_handler_map"
    )


# ---------------------------------------------------------------------------
# 2. Panel registration
# ---------------------------------------------------------------------------


def test_toolbar_panels_registered_in_panel_registry(tmp_path):
    """After calling register_components() on the graph-editor Library,
    CopyToolbarPanel, DeleteToolbarPanel, and SelectionOverflowPanel are
    present in the PanelRegistry, all on the one SelectionToolbar surface.
    """

    from haywire.ui.panel.registry import PanelRegistry
    from haywire.core.library.identity import LibraryIdentity
    from haybale_graph_editor.panels.graph.toolbar.selection import (
        CopyToolbarPanel,
        DeleteToolbarPanel,
        SelectionOverflowPanel,
    )

    # Build a minimal LibraryIdentity so the registry can tag classes
    identity = LibraryIdentity(
        label="Graph Editor Test",
        version="0.0.1",
        folder_path=str(tmp_path),
        module_name="haybale_graph_editor",
        name="graph_editor",
    )

    registry = PanelRegistry()

    # Register the three panel classes directly (mimicking what folder scan does)
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, SelectionOverflowPanel):
        registry._register_class(cls, identity)

    from haybale_graph_editor.surfaces import SelectionToolbar

    # One query now — the two-protocol loop and its dedup existed only because
    # SelectionContextActions and ToolbarActions both routed against ToolbarFocus.
    panels = registry.get_panels(SelectionToolbar)

    assert CopyToolbarPanel in panels, "CopyToolbarPanel not registered"
    assert DeleteToolbarPanel in panels, "DeleteToolbarPanel not registered"
    assert SelectionOverflowPanel in panels, "SelectionOverflowPanel not registered"


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
        CopyToolbarPanel,
        DeleteToolbarPanel,
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
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, SelectionOverflowPanel):
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
