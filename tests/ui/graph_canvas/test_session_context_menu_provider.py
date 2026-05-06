"""Tests for SessionContextMenuProvider's _OpenMenuContext lifecycle and action methods."""

from unittest.mock import MagicMock

from haywire.ui.context import SessionContext
from haybale_studio.editors.graph_canvas.handlers.context_menu import (
    SessionContextMenuProvider,
    _OpenMenuContext,
)
from haywire.ui.panel.registry import PanelRegistry


def _make_provider(on_emit_event=None, on_emit_sync_event=None) -> SessionContextMenuProvider:
    """Construct a provider with mock dependencies."""
    ctx = SessionContext(session_id="t", app=MagicMock())
    session = MagicMock()
    session.context = ctx
    return SessionContextMenuProvider(
        context=ctx,
        session=session,
        panel_registry=PanelRegistry(),
        on_emit_event=on_emit_event,
        on_emit_sync_event=on_emit_sync_event,
    )


def test_open_menu_context_is_initially_none():
    provider = _make_provider()
    assert provider._open_ctx is None


def test_open_menu_context_holds_canvas_pos():
    """A handler that builds an _OpenMenuContext sets it correctly."""
    ctx = _OpenMenuContext(
        click_pos=(100.0, 200.0),
        canvas_pos=(50.0, 60.0),
    )
    assert ctx.click_pos == (100.0, 200.0)
    assert ctx.canvas_pos == (50.0, 60.0)
    assert ctx.pending_connection is None
    assert ctx.edge_state is None
    assert ctx.edge_reconnect_end is False


def test_provider_satisfies_node_context_actions():
    from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import NodeContextActions

    provider = _make_provider()
    assert isinstance(provider, NodeContextActions)


def test_provider_satisfies_edge_context_actions():
    from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import EdgeContextActions

    provider = _make_provider()
    assert isinstance(provider, EdgeContextActions)


def test_provider_satisfies_canvas_context_actions():
    from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import CanvasContextActions

    provider = _make_provider()
    assert isinstance(provider, CanvasContextActions)


def test_provider_satisfies_selection_context_actions():
    from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import SelectionContextActions

    provider = _make_provider()
    assert isinstance(provider, SelectionContextActions)


def test_delete_node_emits_user_remove_event():
    from haybale_studio.editors.graph_canvas.event_definitions import UserRemoveEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.delete_node("node-1")

    assert len(captured) == 1
    assert isinstance(captured[0], UserRemoveEvent)
    assert captured[0].nodes == ["node-1"]
    assert captured[0].edges == []


def test_delete_edge_emits_user_remove_event():
    from haybale_studio.editors.graph_canvas.event_definitions import UserRemoveEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.delete_edge("edge-1")

    assert len(captured) == 1
    assert isinstance(captured[0], UserRemoveEvent)
    assert captured[0].nodes == []
    assert captured[0].edges == ["edge-1"]


def test_copy_node_emits_user_copy_selected_event():
    from haybale_studio.editors.graph_canvas.event_definitions import UserCopySelectedEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.copy_node("node-1")

    assert len(captured) == 1
    assert isinstance(captured[0], UserCopySelectedEvent)
    assert captured[0].selectedNodes == ["node-1"]
    assert captured[0].selectedEdges == []


def test_redraw_node_emits_element_redraw_event():
    from haybale_studio.editors.graph_canvas.event_definitions import ElementRedrawEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.redraw_node("node-1")

    assert len(captured) == 1
    assert isinstance(captured[0], ElementRedrawEvent)
    assert captured[0].nodes == ["node-1"]


def test_revalidate_node_emits_element_revalidate_event():
    from haybale_studio.editors.graph_canvas.event_definitions import ElementRevalidateEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.revalidate_node("node-1")

    assert isinstance(captured[0], ElementRevalidateEvent)


def test_reset_node_emits_element_reset_event():
    from haybale_studio.editors.graph_canvas.event_definitions import ElementResetEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.reset_node("node-1")

    assert isinstance(captured[0], ElementResetEvent)


def test_copy_selection_uses_session_context_selection():
    """copy_selection reads ctx.selected_nodes/edges and emits UserCopySelectedEvent."""
    from haybale_studio.editors.graph_canvas.event_definitions import UserCopySelectedEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._context.selected_nodes.value = {"a", "b"}
    provider._context.selected_edges.value = {"e1"}

    provider.copy_selection()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, UserCopySelectedEvent)
    assert set(event.selectedNodes) == {"a", "b"}
    assert event.selectedEdges == ["e1"]


def test_paste_at_click_emits_paste_event_with_canvas_pos():
    """paste_at_click emits UserPasteClipboardEvent using _open_ctx.canvas_pos."""
    from haybale_studio.editors.graph_canvas.event_definitions import UserPasteClipboardEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        canvas_pos=(123.0, 456.0),
    )

    provider.paste_at_click()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, UserPasteClipboardEvent)
    assert event.canvasX == 123.0
    assert event.canvasY == 456.0


def test_paste_at_click_no_open_ctx_is_noop():
    """If no popup is open, paste_at_click does nothing."""
    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = None

    provider.paste_at_click()

    assert captured == []


def test_create_node_at_click_emits_node_create_request_event():
    from haybale_studio.editors.graph_canvas.event_definitions import NodeCreateRequestEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        canvas_pos=(50.0, 60.0),
    )

    provider.create_node_at_click("core:node:foo")

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, NodeCreateRequestEvent)
    assert event.registryKey == "core:node:foo"
    assert event.position == {"x": 50.0, "y": 60.0}


def test_reconnect_active_edge_uses_open_ctx_and_active_edge():
    """reconnect_active_edge reads ctx.active_edge.value AND _open_ctx.edge_reconnect_end."""
    from haybale_studio.editors.graph_canvas.event_definitions import SyncEdgeReconnectEvent

    captured = []
    provider = _make_provider(on_emit_event=captured.append)

    # Set up a fake edge in active_edge so reconnect_active_edge sees it.
    wrapper = MagicMock()
    wrapper._edge_id = "edge-1"
    wrapper.source_node_id = "src-node"
    wrapper.outlet_port_id = "out-pin"
    wrapper.sink_node_id = "snk-node"
    wrapper.inlet_port_id = "in-pin"

    provider._context.active_edge.value = wrapper
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        edge_reconnect_end=True,  # clicked near inlet → anchor on outlet (source) side
    )

    provider.reconnect_active_edge()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, SyncEdgeReconnectEvent)
    assert event.anchorNodeId == "src-node"
    assert event.anchorPinId == "out-pin"


def test_reconnect_active_edge_no_active_edge_is_noop():
    """If no active edge, reconnect_active_edge does nothing."""
    captured = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(click_pos=(0, 0))
    # active_edge is None by default

    provider.reconnect_active_edge()

    assert captured == []


def test_open_menu_creates_open_ctx_with_click_pos():
    """_open_menu records click_pos in _open_ctx."""
    from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import NodeContextActions
    from haybale_studio.focuses import NodeFocus

    provider = _make_provider()
    # _open_menu opens a Popup which requires NiceGUI runtime — patch it.
    provider._build_popup = MagicMock(return_value=MagicMock())  # see implementation below

    provider._open_menu(NodeContextActions, NodeFocus, (100.0, 200.0))

    assert provider._open_ctx is not None
    assert provider._open_ctx.click_pos == (100.0, 200.0)


def test_open_menu_clears_open_ctx_on_close(monkeypatch):
    """When the popup's on_close fires, _open_ctx is set to None."""
    from haybale_studio.editors.graph_canvas.handlers.context_menu_actions import NodeContextActions
    from haybale_studio.focuses import NodeFocus

    provider = _make_provider()
    popup = MagicMock()
    on_close_callback = []

    def capture_on_close(cb):
        on_close_callback.append(cb)

    popup.on_close = capture_on_close
    provider._build_popup = MagicMock(return_value=popup)

    provider._open_menu(NodeContextActions, NodeFocus, (0.0, 0.0))
    assert provider._open_ctx is not None

    # Trigger the close callback
    on_close_callback[0]()
    assert provider._open_ctx is None
