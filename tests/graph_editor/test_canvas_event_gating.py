"""The canvas lock gates canvas events, the context menu and the selection toolbar."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map, handles_event
from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import ContextMenuHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import SelectionToolbarHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.core.access import AccessTier
from haywire.ui.components.graph.event_definitions import (
    ContextMenuCanvasEvent,
    ContextMenuEdgeEvent,
    ContextMenuPortEvent,
    ContextMenuSelectedEvent,
    ContextMenuSurfaceEvent,
    SelectionBoundsEvent,
    SelectionChangedEvent,
    UserDragEndEvent,
    UserRemoveEvent,
    UserResizeEndEvent,
)

pytestmark = pytest.mark.unit


class _Stub:
    """Handler source recording what reached it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    @handles_event(UserRemoveEvent)
    def remove(self, event: Any) -> None:
        self.calls.append("remove")

    @handles_event(UserDragEndEvent)
    def drag_end(self, event: Any) -> None:
        self.calls.append("drag_end")

    @handles_event(UserResizeEndEvent)
    def resize_end(self, event: Any) -> None:
        self.calls.append("resize_end")

    @handles_event(SelectionChangedEvent, access=AccessTier.VIEW)
    def selection(self, event: Any) -> None:
        self.calls.append("selection")


def _manager(locked: bool, tier: AccessTier = AccessTier.ADMIN) -> tuple[Any, _Stub]:
    """A GraphCanvasManager with only what ``_handle_canvas_event`` and ``allows`` read."""
    manager: Any = object.__new__(GraphCanvasManager)
    manager._session = SimpleNamespace(context=SimpleNamespace(can_access=tier.satisfies))
    manager.locked = locked
    manager.visual_layer = MagicMock()
    stub = _Stub()
    manager._event_handlers = build_event_handler_map([stub])
    return manager, stub


def test_unmarked_handlers_need_edit():
    manager, stub = _manager(locked=True)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    assert stub.calls == []


def test_unmarked_handlers_run_while_unlocked():
    manager, stub = _manager(locked=False)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    assert stub.calls == ["remove"]


def test_view_handlers_run_while_locked():
    manager, stub = _manager(locked=True)
    manager._handle_canvas_event(SelectionChangedEvent(selectedNodes=["a"], selectedEdges=[]))
    assert stub.calls == ["selection"]


def test_real_tier_below_edit_refuses_without_a_lock():
    manager, stub = _manager(locked=False, tier=AccessTier.OPERATE)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    assert stub.calls == []


def test_refused_drag_end_resyncs_positions():
    manager, stub = _manager(locked=True)
    manager._handle_canvas_event(UserDragEndEvent(nodes=["a", "b"]))
    assert stub.calls == []
    manager.visual_layer.resync_positions.assert_called_once_with(["a", "b"])


def test_refused_resize_end_resyncs_positions():
    manager, stub = _manager(locked=True)
    manager._handle_canvas_event(
        UserResizeEndEvent(nodeId="a", width=200.0, height=100.0, size_adapt="manual")
    )
    assert stub.calls == []
    manager.visual_layer.resync_positions.assert_called_once_with(["a"])


def test_other_refusals_do_not_resync():
    manager, _ = _manager(locked=True)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    manager.visual_layer.resync_positions.assert_not_called()


def test_view_access_events():
    """Only the events that change nothing in the graph run at view access."""
    handler_classes = [
        VisualLayerHandlers,
        SelectionHandlers,
        InteractionHandlers,
        ContextMenuHandlers,
        SelectionToolbarHandlers,
    ]
    view_events: set[str] = set()
    for cls in handler_classes:
        for name in dir(cls):
            method = getattr(cls, name)
            if getattr(method, "_handles_event_access", None) == AccessTier.VIEW:
                view_events.update(e.event_type for e in method._handles_event_classes)
    assert view_events == {
        "selectionChanged",
        "userCopySelected",
        "edgeClicked",
        "contextMenuCanvas",
        "contextMenuEdge",
        "contextMenuSelected",
        "contextMenuSurface",
        "contextMenuPort",
        "selectionBounds",
        "selectionBoundsHide",
        "canvasMounted",
        "nodesMeasured",
        "enterGroup",
    }


@pytest.mark.parametrize(
    "event",
    [
        ContextMenuCanvasEvent(screenX=1, screenY=2, canvasX=3, canvasY=4),
        ContextMenuEdgeEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, edge_id="e"),
        ContextMenuSelectedEvent(
            screenX=1, screenY=2, canvasX=3, canvasY=4, selectedNodes=["a"], selectedEdges=[]
        ),
        ContextMenuSurfaceEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, nodeId="a", surfaceId="s"),
        ContextMenuPortEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, nodeId="a", portId="p"),
    ],
)
def test_no_menu_below_edit(event):
    manager, _ = _manager(locked=True)
    provider = MagicMock()
    handlers = ContextMenuHandlers(visual_layer=MagicMock(), provider=provider, allows=manager.allows)
    handlers.process_context_menu(event)
    for name in (
        "on_canvas_context",
        "on_edge_context",
        "on_selection_context",
        "on_surface_context",
        "on_port_context",
    ):
        getattr(provider, name).assert_not_called()


def test_menu_opens_when_unlocked():
    manager, _ = _manager(locked=False)
    provider = MagicMock()
    handlers = ContextMenuHandlers(visual_layer=MagicMock(), provider=provider, allows=manager.allows)
    handlers.process_context_menu(ContextMenuCanvasEvent(screenX=1, screenY=2, canvasX=3, canvasY=4))
    provider.on_canvas_context.assert_called_once()


def test_no_toolbar_below_edit():
    manager, _ = _manager(locked=True)
    provider = MagicMock()
    handlers = SelectionToolbarHandlers(provider=provider, allows=manager.allows)
    handlers.process_selection_bounds(SelectionBoundsEvent(left=0.0, top=0.0, right=10.0, bottom=10.0))
    provider.show_at.assert_not_called()
    provider.hide.assert_called_once()


def test_resync_positions_restores_model_positions():
    layer: Any = object.__new__(VisualLayerHandlers)
    wrapper = SimpleNamespace(node=SimpleNamespace(props=SimpleNamespace(posX=10.0, posY=20.0)))
    layer.graph = SimpleNamespace(get_node_wrapper={"a": wrapper}.get)
    layer.update_node_position = MagicMock()
    layer.resync_positions(["a", "gone"])
    layer.update_node_position.assert_called_once_with("a", (10.0, 20.0))
