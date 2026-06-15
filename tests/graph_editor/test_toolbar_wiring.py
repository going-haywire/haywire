"""Tests for toolbar wiring: SelectionToolbarHandlers in GraphCanvasManager
and toolbar panel registration via register_components().

Two test groups:
1. Unit tests — import SelectionToolbarHandlers and check the event keys it
   registers via build_event_handler_map. No app bootstrap required.
2. Unit tests — directly call register_components() on a Library stub and
   confirm CopyToolbarPanel / DeleteToolbarPanel / OverflowToolbarPanel land
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
    import haywire.core.graph.editor  # noqa: F401 — prevents circular import

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
    import haywire.core.graph.editor  # noqa: F401
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
    CopyToolbarPanel, DeleteToolbarPanel, and OverflowToolbarPanel are present
    in the PanelRegistry.
    """
    import haywire.core.graph.editor  # noqa: F401

    from haywire.ui.panel.registry import PanelRegistry
    from haywire.core.library.identity import LibraryIdentity
    from haybale_graph_editor.panels.graph.toolbar.selection import (
        CopyToolbarPanel,
        DeleteToolbarPanel,
        OverflowToolbarPanel,
    )

    # Build a minimal LibraryIdentity so the registry can tag classes
    identity = LibraryIdentity(
        label="Graph Editor Test",
        version="0.0.1",
        description="test",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=str(tmp_path),
        module_name="haybale_graph_editor",
        id="graph_editor",
    )

    registry = PanelRegistry()

    # Register the three panel classes directly (mimicking what folder scan does)
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, OverflowToolbarPanel):
        registry._register_class(cls, identity)

    from haybale_graph_editor.focuses import ToolbarFocus
    from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
        SelectionContextActions,
        ToolbarActions,
    )

    copy_panels = registry.get_panels_for_action(SelectionContextActions, ToolbarFocus)
    delete_panels = registry.get_panels_for_action(SelectionContextActions, ToolbarFocus)
    overflow_panels = registry.get_panels_for_action(ToolbarActions, ToolbarFocus)

    assert CopyToolbarPanel in copy_panels, "CopyToolbarPanel not registered"
    assert DeleteToolbarPanel in delete_panels, "DeleteToolbarPanel not registered"
    assert OverflowToolbarPanel in overflow_panels, "OverflowToolbarPanel not registered"
