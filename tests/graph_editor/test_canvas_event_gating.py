"""The level mode gates canvas events, the context menu and the selection toolbar."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.event_handlers import (
    build_event_handler_map,
    handler_requires,
    handles_event,
)
from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import ContextMenuHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers import selection as selection_module
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
    SelectionToolbarHandlers,
    SelectionToolbarProvider,
)
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute
from haywire.ui.components.graph.event_definitions import (
    ContextMenuCanvasEvent,
    ContextMenuEdgeEvent,
    ContextMenuPortEvent,
    ContextMenuSelectedEvent,
    ContextMenuSurfaceEvent,
    EnterGroupEvent,
    SelectionBoundsEvent,
    SelectionChangedEvent,
    SyncNodeSizeEvent,
    UserCopySelectedEvent,
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

    @handles_event(SelectionChangedEvent, requires=LevelMode.VIEW)
    def selection(self, event: Any) -> None:
        self.calls.append("selection")


def _manager(mode: LevelMode) -> tuple[Any, _Stub]:
    """A GraphCanvasManager with only what ``_handle_canvas_event`` reads."""
    manager: Any = object.__new__(GraphCanvasManager)
    manager.route = EditRoute(lambda: MagicMock(), lambda: mode)
    manager.visual_layer = MagicMock()
    stub = _Stub()
    manager._event_handlers = build_event_handler_map([stub])
    return manager, stub


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_unmarked_handlers_need_edit(mode):
    manager, stub = _manager(mode)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    assert stub.calls == []


def test_unmarked_handlers_run_in_edit():
    manager, stub = _manager(LevelMode.EDIT)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    assert stub.calls == ["remove"]


@pytest.mark.parametrize("mode", list(LevelMode))
def test_view_handlers_run_in_every_mode(mode):
    manager, stub = _manager(mode)
    manager._handle_canvas_event(SelectionChangedEvent(selectedNodes=["a"], selectedEdges=[]))
    assert stub.calls == ["selection"]


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_refused_drag_end_resyncs_positions(mode):
    manager, stub = _manager(mode)
    manager._handle_canvas_event(UserDragEndEvent(nodes=["a", "b"]))
    assert stub.calls == []
    manager.visual_layer.resync_positions.assert_called_once_with(["a", "b"])


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_refused_resize_end_resyncs_position_and_size(mode):
    manager, stub = _manager(mode)
    manager._handle_canvas_event(
        UserResizeEndEvent(nodeId="a", width=200.0, height=100.0, size_adapt="manual")
    )
    assert stub.calls == []
    manager.visual_layer.resync_positions.assert_called_once_with(["a"])
    manager.visual_layer.resync_size.assert_called_once_with("a")


def test_resync_size_restores_the_model_size_in_the_browser():
    layer: Any = object.__new__(VisualLayerHandlers)
    props = SimpleNamespace(size_adapt="manual_width", width=140.0, height=80.0)
    ui_node = MagicMock()
    ui_node.wrapper = SimpleNamespace(node=SimpleNamespace(props=props))
    layer.node_panels = {"a": ui_node}
    layer.canvas_vue = MagicMock()

    layer.resync_size("a")
    layer.resync_size("gone")

    ui_node._apply_slot_style.assert_called_once_with()
    (event,), _ = layer.canvas_vue.emit_sync_event.call_args
    assert event == SyncNodeSizeEvent(nodeId="a", size_adapt="manual_width", width=140.0, height=80.0)
    layer.canvas_vue.emit_sync_event.assert_called_once()


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_other_refusals_do_not_resync(mode):
    manager, _ = _manager(mode)
    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
    manager.visual_layer.resync_positions.assert_not_called()


def test_view_mode_events():
    """Only the events that change nothing in the graph run at view access; selecting is one."""
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
            if getattr(method, "_handles_event_requires", None) == LevelMode.VIEW:
                view_events.update(e.event_type for e in method._handles_event_classes)
    assert view_events == {
        "edgeClicked",
        "selectionBounds",
        "selectionBoundsHide",
        "selectionChanged",
        "selectConnected",
        "canvasMounted",
        "nodesMeasured",
    }


def test_enter_group_declares_operate():
    assert handler_requires(VisualLayerHandlers.process_enter_group) is LevelMode.OPERATE


_MENU_EVENTS = [
    ContextMenuCanvasEvent(screenX=1, screenY=2, canvasX=3, canvasY=4),
    ContextMenuEdgeEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, edge_id="e"),
    ContextMenuSelectedEvent(
        screenX=1, screenY=2, canvasX=3, canvasY=4, selectedNodes=["a"], selectedEdges=[]
    ),
    ContextMenuSurfaceEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, nodeId="a", surfaceId="s"),
    ContextMenuPortEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, nodeId="a", portId="p"),
]
_MENU_INTENTS = (
    "on_canvas_context",
    "on_edge_context",
    "on_selection_context",
    "on_surface_context",
    "on_port_context",
)


def _menu_manager(mode: LevelMode) -> tuple[Any, MagicMock]:
    """A manager whose handler map holds the real ``process_context_menu`` over a mock provider."""
    manager, _ = _manager(mode)
    provider = MagicMock()
    handlers = ContextMenuHandlers(visual_layer=MagicMock(), provider=provider)
    manager._event_handlers = build_event_handler_map([handlers])
    return manager, provider


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
@pytest.mark.parametrize("event", _MENU_EVENTS)
def test_no_menu_below_edit(mode, event):
    manager, provider = _menu_manager(mode)
    manager._handle_canvas_event(event)
    for name in _MENU_INTENTS:
        getattr(provider, name).assert_not_called()


def test_menu_opens_in_edit():
    manager, provider = _menu_manager(LevelMode.EDIT)
    manager._handle_canvas_event(_MENU_EVENTS[0])
    provider.on_canvas_context.assert_called_once()


def test_context_menu_events_need_edit():
    assert handler_requires(ContextMenuHandlers.process_context_menu) is LevelMode.EDIT


def test_a_handler_without_requires_needs_edit():
    @handles_event(UserRemoveEvent)
    def remove(event: Any) -> None: ...

    assert handler_requires(remove) is LevelMode.EDIT


@pytest.mark.parametrize(("mode", "runs"), [(LevelMode.OPERATE, False), (LevelMode.EDIT, True)])
def test_a_handler_without_the_marker_needs_edit(mode, runs):
    called: list[str] = []

    class _Unmarked:
        def remove(self, event: Any) -> None:
            called.append("remove")

    source = _Unmarked()
    # Classes marked, no mode marker: the dispatcher treats it as EDIT.
    setattr(_Unmarked.remove, "_handles_event_classes", (UserRemoveEvent,))  # noqa: B010
    manager, _ = _manager(mode)
    manager._event_handlers = build_event_handler_map([source])
    assert handler_requires(manager._event_handlers["userRemove"]) is LevelMode.EDIT

    manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))

    assert called == (["remove"] if runs else [])


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_no_toolbar_below_edit(mode):
    manager, _ = _manager(mode)
    provider = SelectionToolbarProvider(
        context=MagicMock(),
        session=MagicMock(),
        panel_registry=MagicMock(),
        menu_provider=MagicMock(),
        allows=manager.route.allows,
    )
    provider.hide = MagicMock()  # type: ignore[method-assign]
    handlers = SelectionToolbarHandlers(provider=provider)
    handlers.process_selection_bounds(SelectionBoundsEvent(left=0.0, top=0.0, right=10.0, bottom=10.0))
    provider.hide.assert_called_once()
    assert provider._toolbar_popup is None


def test_resync_positions_restores_model_positions():
    layer: Any = object.__new__(VisualLayerHandlers)
    props = SimpleNamespace(posX=10.0, posY=20.0, get_position=lambda channel: (10.0, 20.0))
    wrapper = SimpleNamespace(node=SimpleNamespace(props=props))
    layer.graph = SimpleNamespace(get_node_wrapper={"a": wrapper}.get)
    layer.update_node_position = MagicMock()
    layer.resync_positions(["a", "gone"])
    layer.update_node_position.assert_called_once_with("a", (10.0, 20.0))


def _lockable_manager(mode: LevelMode) -> Any:
    manager: Any = object.__new__(GraphCanvasManager)
    manager.selection = MagicMock()
    manager.visual_layer = MagicMock()
    manager.route = EditRoute(lambda: MagicMock(), lambda: mode)
    manager.canvas_vue = MagicMock()
    manager._toolbar_provider = MagicMock()
    manager.context_menu_handlers = SimpleNamespace(provider=MagicMock())
    return manager


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_refresh_mode_below_edit_hides_toolbar_and_closes_menu(mode):
    manager = _lockable_manager(mode)
    manager.refresh_mode()
    manager.canvas_vue.set_level_mode.assert_called_once_with(mode)
    manager._toolbar_provider.hide.assert_called_once()
    manager.context_menu_handlers.provider.close_open_menu.assert_called_once()


def test_refresh_mode_in_edit_reopens_nothing():
    manager = _lockable_manager(LevelMode.EDIT)
    manager.refresh_mode()
    manager.canvas_vue.set_level_mode.assert_called_once_with(LevelMode.EDIT)
    manager._toolbar_provider.hide.assert_not_called()
    manager._toolbar_provider.show_at.assert_not_called()
    manager.context_menu_handlers.provider.close_open_menu.assert_not_called()


def test_refresh_mode_follows_the_route_mode_now():
    mode = [LevelMode.EDIT]
    manager = _lockable_manager(LevelMode.EDIT)
    manager.route = EditRoute(lambda: MagicMock(), lambda: mode[0])
    manager.refresh_mode()
    mode[0] = LevelMode.OPERATE
    manager.refresh_mode()
    assert [c.args for c in manager.canvas_vue.set_level_mode.call_args_list] == [
        (LevelMode.EDIT,),
        (LevelMode.OPERATE,),
    ]


@pytest.mark.parametrize("mode", list(LevelMode))
def test_refresh_mode_pushes_the_route_mode(mode):
    manager = _lockable_manager(mode)
    manager.refresh_mode()
    manager.canvas_vue.set_level_mode.assert_called_once_with(mode)


def test_a_canvas_pushes_its_mode_when_built(monkeypatch):
    """A canvas built on an operate level starts in operate in the browser, with no refresh call."""
    from haybale_graph_editor.editors.graph_canvas import graph_canvas_manager as manager_module

    for name in (
        "VisualLayerHandlers",
        "SelectionHandlers",
        "InteractionHandlers",
        "SessionContextMenuProvider",
        "ContextMenuHandlers",
        "SelectionToolbarProvider",
        "SelectionToolbarHandlers",
    ):
        monkeypatch.setattr(manager_module, name, MagicMock())
    monkeypatch.setattr(manager_module, "build_event_handler_map", lambda sources: {})
    canvas_vue = MagicMock()
    monkeypatch.setattr(GraphCanvasManager, "_setup_canvas", lambda self: (MagicMock(), canvas_vue))
    monkeypatch.setattr(GraphCanvasManager, "_follow_graph_props", lambda self: None)
    route = EditRoute(lambda: MagicMock(), lambda: LevelMode.OPERATE)

    GraphCanvasManager(
        route=route,
        skin_factory=MagicMock(),
        node_factory=MagicMock(),
        panel_registry=MagicMock(),
        session=MagicMock(session_id="session-1"),
    )

    canvas_vue.set_level_mode.assert_called_once_with(LevelMode.OPERATE)


@pytest.mark.parametrize("mode", list(LevelMode))
def test_refresh_mode_keeps_the_canvas_selection(mode):
    """Selection is looking, so a mode change leaves it alone."""
    manager = _lockable_manager(mode)
    manager.selection.selected_nodes = {"a"}
    manager.refresh_mode()
    assert manager.selection.selected_nodes == {"a"}
    manager.visual_layer.sync_selections.assert_not_called()


def _selection_manager(mode: LevelMode) -> tuple[Any, SimpleNamespace, MagicMock]:
    """A canvas manager over a real ``SelectionHandlers``, plus the session's EditState and session."""
    edit_state = SimpleNamespace(
        active_node=None, active_edge=None, selected_nodes=set(), selected_edges=set(), clipboard=None
    )
    session = MagicMock()
    session.context.data = {EditState: edit_state}
    session.context.active_component = None
    graph = MagicMock()
    graph.get_node_wrapper.side_effect = lambda node_id: SimpleNamespace(
        node_id=node_id, registry_key="lib:node:Blur"
    )
    manager: Any = object.__new__(GraphCanvasManager)
    manager.route = EditRoute(lambda: MagicMock(), lambda: mode)
    manager.visual_layer = MagicMock()
    selection = SelectionHandlers(graph=graph, route=manager.route, session_id="s1", session=session)
    manager._event_handlers = build_event_handler_map([selection])
    return manager, SimpleNamespace(state=edit_state, selection=selection), session


@pytest.mark.parametrize("mode", list(LevelMode))
def test_a_selection_change_is_taken_in_every_mode(mode):
    """A view or operate session selects, so Component Docs follows the clicked node."""
    manager, parts, session = _selection_manager(mode)
    manager._handle_canvas_event(
        SelectionChangedEvent(selectedNodes=["n1"], selectedEdges=[], activeNodeId="n1")
    )
    assert parts.state.selected_nodes == {"n1"}
    assert parts.state.active_node is not None
    assert session.context.active_component == "lib:node:Blur"


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_copy_is_refused_below_edit(mode, monkeypatch):
    manager, parts, _ = _selection_manager(mode)
    monkeypatch.setattr(selection_module, "build_clipboard_payload", MagicMock())
    manager._handle_canvas_event(UserCopySelectedEvent(selectedNodes=["n1"], selectedEdges=[]))
    assert parts.state.clipboard is None
    selection_module.build_clipboard_payload.assert_not_called()  # type: ignore[attr-defined]


def _enter_group_manager(mode: LevelMode) -> tuple[Any, Any]:
    """A manager whose handler map holds the real ``process_enter_group``."""
    manager, _ = _manager(mode)
    layer: Any = object.__new__(VisualLayerHandlers)
    layer.context = MagicMock()
    layer.graph = SimpleNamespace(graph_id="doc_graph")
    manager._event_handlers = build_event_handler_map([layer])
    return manager, layer


def test_enter_group_needs_operate():
    from haywire.core.signals import SubgraphNavigation

    view, view_layer = _enter_group_manager(LevelMode.VIEW)
    view._handle_canvas_event(EnterGroupEvent(node_id="GraphNode_1"))
    view_layer.context.session.publish.assert_not_called()

    operate, operate_layer = _enter_group_manager(LevelMode.OPERATE)
    operate._handle_canvas_event(EnterGroupEvent(node_id="GraphNode_1"))
    (signal,), _ = operate_layer.context.session.publish.call_args
    assert isinstance(signal, SubgraphNavigation)
    assert signal.node_id == "GraphNode_1"
