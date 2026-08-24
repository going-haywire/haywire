"""Tests for SessionContextMenuProvider's _OpenMenuContext lifecycle and action methods."""

from typing import Any, cast

from types import SimpleNamespace
from unittest.mock import MagicMock

from haywire.core.session.context import SessionContext
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import (
    SessionContextMenuProvider,
    _OpenMenuContext,
)
from haywire.ui.panel.registry import PanelRegistry


def _make_provider(
    on_emit_event=None, on_emit_sync_event=None, canvas_vue=None
) -> SessionContextMenuProvider:
    """Construct a provider with mock dependencies.

    Builds a real ``SessionContext`` whose ``data[EditState]`` lookup
    resolves to a stub with bare field values matching the post-migration
    signal_field API (production reads ``edit.active_graph``, not
    ``edit.active_graph.value``). Bypasses container class-identity
    coupling (the production ``EditState`` reference may differ from a
    freshly-imported one after library hot-reload).
    """
    edit_stub = SimpleNamespace(
        active_graph=None,
        active_graph_path=None,
        active_node=None,
        active_edge=None,
        active_port=None,
        selected_nodes=set(),
        selected_edges=set(),
        clipboard=None,
    )
    fake_data = MagicMock()
    fake_data.__getitem__.return_value = edit_stub

    app = MagicMock()
    ctx = SessionContext(session_id="t", app=app)
    # Replace the SessionDataNamespace with our stub so EditState lookups
    # go to ``edit_stub`` regardless of class identity.
    ctx.data = fake_data
    session = MagicMock()
    session.context = ctx
    provider = SessionContextMenuProvider(
        context=ctx,
        session=session,
        panel_registry=PanelRegistry(),
        on_emit_event=on_emit_event,
        on_emit_sync_event=on_emit_sync_event,
        canvas_vue=canvas_vue,
    )
    # Expose the stub for tests that need to seed selection/edge values.
    cast(Any, provider)._test_edit_stub = edit_stub  # type: ignore[attr-defined]
    return provider


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


def test_provider_satisfies_every_surface_it_opens():
    """render_surface validates the host against the target surface's
    ``provides`` — so a provider claiming a Protocol it satisfies only in part
    now fails at the point of nesting instead of silently handing its panels a
    broken ``self.actions``."""
    from haybale_graph_editor.surfaces import (
        EdgeMenu,
        GraphContext,
        PinMenu,
        SelectionMenu,
    )

    provider = _make_provider()
    for surface in (GraphContext, EdgeMenu, SelectionMenu, PinMenu):
        assert isinstance(provider, surface.provides), surface.id


def test_delete_edge_emits_user_remove_event():
    from haywire.ui.components.graph.event_definitions import UserRemoveEvent

    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    provider.delete_edge("edge-1")

    assert len(captured) == 1
    assert isinstance(captured[0], UserRemoveEvent)
    assert captured[0].nodes == []
    assert captured[0].edges == ["edge-1"]


def test_copy_selection_uses_session_context_selection():
    """copy_selection reads ctx.data[EditState].selected_* and emits UserCopySelectedEvent."""
    from haywire.ui.components.graph.event_definitions import UserCopySelectedEvent

    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    edit = cast(Any, provider)._test_edit_stub
    edit.selected_nodes = {"a", "b"}
    edit.selected_edges = {"e1"}

    provider.copy_selection()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, UserCopySelectedEvent)
    assert set(event.selectedNodes) == {"a", "b"}
    assert event.selectedEdges == ["e1"]


def test_paste_at_click_emits_clipboard_paste_request_via_sync_channel():
    """paste_at_click asks Vue to read the OS clipboard via the sync channel.

    The OS clipboard can only be read async in the browser, so the menu click
    emits SyncRequestClipboardPasteEvent (Python→Vue); Vue reads the clipboard
    and emits the actual UserPasteClipboardEvent back.
    """
    from haywire.ui.components.graph.event_definitions import SyncRequestClipboardPasteEvent

    captured: list = []
    sync_captured: list = []
    provider = _make_provider(
        on_emit_event=captured.append,
        on_emit_sync_event=sync_captured.append,
    )
    provider._open_ctx = _OpenMenuContext(
        click_pos=(0.0, 0.0),
        canvas_pos=(123.0, 456.0),
    )

    provider.paste_at_click()

    assert captured == []
    assert len(sync_captured) == 1
    event = sync_captured[0]
    assert isinstance(event, SyncRequestClipboardPasteEvent)
    assert event.canvasX == 123.0
    assert event.canvasY == 456.0


def test_paste_at_click_no_open_ctx_is_noop():
    """If no popup is open, paste_at_click does nothing."""
    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = None

    provider.paste_at_click()

    assert captured == []


def test_focus_on_graph_fits_the_viewport_and_closes_the_popup():
    """focus_on_graph fits the zoom container to content and dismisses the menu.

    Pure client-side viewport op: no event is emitted, unlike paste/create-node.
    """
    canvas_vue = SimpleNamespace(zoom_container=MagicMock())
    provider = _make_provider(canvas_vue=canvas_vue)
    popup = MagicMock()
    provider._open_popup = popup

    provider.focus_on_graph()

    canvas_vue.zoom_container.center_on_content.assert_called_once()
    popup.close.assert_called_once()


def test_focus_on_graph_with_no_canvas_vue_is_noop_but_still_closes_popup():
    """No canvas_vue wired (e.g. a stub provider) — don't crash, still dismiss."""
    provider = _make_provider(canvas_vue=None)
    popup = MagicMock()
    provider._open_popup = popup

    provider.focus_on_graph()

    popup.close.assert_called_once()


def test_create_node_at_click_emits_node_create_request_event():
    from haywire.ui.components.graph.event_definitions import NodeCreateRequestEvent

    captured: list = []
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
    """reconnect_active_edge reads ctx.data[EditState].active_edge AND _open_ctx.edge_reconnect_end."""
    from haywire.ui.components.graph.event_definitions import SyncEdgeReconnectEvent

    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)

    # Set up a fake edge in active_edge so reconnect_active_edge sees it.
    wrapper = MagicMock()
    wrapper._edge_id = "edge-1"
    wrapper.source_node_id = "src-node"
    wrapper.outlet_port_id = "out-pin"
    wrapper.sink_node_id = "snk-node"
    wrapper.inlet_port_id = "in-pin"

    cast(Any, provider)._test_edit_stub.active_edge = wrapper
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
    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    provider._open_ctx = _OpenMenuContext(click_pos=(0, 0))
    # active_edge is None by default

    provider.reconnect_active_edge()

    assert captured == []


def _register_visible_panel(provider, surface, registry_id):
    """Register a leaf panel that draws, so _open_menu keeps its popup.

    With nothing drawing, _open_menu deletes the popup, runs its close cleanup
    and returns; these tests exercise the open path, so they need a leaf.
    """
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel

    @panel(surface=surface, label="Visible", registry_id=registry_id)
    class _Panel(BasePanel):
        @classmethod
        def poll(cls, context):
            return True

        def draw(self, ctx, layout):
            pass

    provider._panel_registry._register_class(_Panel)


def _patched_popup():
    """A Popup double whose ``content`` works as a context manager."""
    content = MagicMock()
    content.__enter__ = MagicMock(return_value=content)
    content.__exit__ = MagicMock(return_value=False)
    popup = MagicMock()
    popup.content = content
    return popup


def test_open_menu_creates_open_ctx_with_click_pos():
    """_open_menu records click_pos in _open_ctx."""
    from haybale_graph_editor.surfaces import GraphContext

    provider = _make_provider()
    cast(Any, provider)._test_edit_stub.active_graph = MagicMock()
    _register_visible_panel(provider, GraphContext, "open_ctx_test_panel")
    # _open_menu builds a Popup which requires NiceGUI runtime — patch it.
    provider._build_popup = MagicMock(return_value=_patched_popup())  # type: ignore[method-assign]

    provider._open_menu(GraphContext, (100.0, 200.0))

    assert provider._open_ctx is not None
    assert provider._open_ctx.click_pos == (100.0, 200.0)


def test_open_menu_clears_open_ctx_on_close(monkeypatch):
    """When the popup's on_close fires, _open_ctx is set to None."""
    from haybale_graph_editor.surfaces import GraphContext

    provider = _make_provider()
    cast(Any, provider)._test_edit_stub.active_graph = MagicMock()
    _register_visible_panel(provider, GraphContext, "open_ctx_close_test_panel")
    popup = _patched_popup()
    on_close_callback = []

    popup.on_close = lambda cb: on_close_callback.append(cb)
    provider._build_popup = MagicMock(return_value=popup)  # type: ignore[method-assign]
    provider._open_menu(GraphContext, (0.0, 0.0))
    assert provider._open_ctx is not None

    # Trigger the close callback
    on_close_callback[0]()
    assert provider._open_ctx is None


def test_open_menu_no_visible_panels_runs_cleanup_without_opening():
    """Nothing drew → _open_ctx cleared immediately, popup never opened."""
    from haybale_graph_editor.surfaces import GraphContext

    provider = _make_provider()  # empty registry → no panels at all
    cast(Any, provider)._test_edit_stub.active_graph = MagicMock()
    popup = _patched_popup()
    provider._build_popup = MagicMock(return_value=popup)  # type: ignore[method-assign]
    provider._open_menu(GraphContext, (0.0, 0.0))

    popup.open.assert_not_called()
    assert provider._open_ctx is None


def test_redraw_selection_emits_element_redraw_for_whole_selection():
    from haywire.ui.components.graph.event_definitions import ElementRedrawEvent

    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    edit = cast(Any, provider)._test_edit_stub
    edit.selected_nodes = {"a", "b"}
    edit.selected_edges = set()

    provider.redraw_selection()

    assert len(captured) == 1
    event = captured[0]
    assert isinstance(event, ElementRedrawEvent)
    assert set(event.nodes) == {"a", "b"}
    assert event.edges == []


def test_revalidate_selection_emits_element_revalidate_for_whole_selection():
    from haywire.ui.components.graph.event_definitions import ElementRevalidateEvent

    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    edit = cast(Any, provider)._test_edit_stub
    edit.selected_nodes = {"a"}
    edit.selected_edges = set()

    provider.revalidate_selection()

    assert isinstance(captured[0], ElementRevalidateEvent)
    assert set(captured[0].nodes) == {"a"}


def test_reset_selection_emits_element_reset_for_whole_selection():
    from haywire.ui.components.graph.event_definitions import ElementResetEvent

    captured: list = []
    provider = _make_provider(on_emit_event=captured.append)
    edit = cast(Any, provider)._test_edit_stub
    edit.selected_nodes = {"a"}
    edit.selected_edges = set()

    provider.reset_selection()

    assert isinstance(captured[0], ElementResetEvent)
    assert set(captured[0].nodes) == {"a"}


def test_provider_satisfies_selection_actions_with_batch_verbs():
    from haybale_graph_editor.surfaces import SelectionActions

    provider = _make_provider()
    # SelectionActions requires the batch verbs; the provider must implement
    # them or this isinstance check fails — and it is the same check
    # render_surface makes before injecting the host.
    assert isinstance(provider, SelectionActions)


def test_on_selection_context_writes_selection_from_payload(monkeypatch):
    """on_selection_context seeds EditState.selected_* from the event payload
    before opening the menu, so menu panels poll against fresh state."""
    provider = _make_provider()
    edit = cast(Any, provider)._test_edit_stub
    # Prevent the real popup/registry machinery from running.
    monkeypatch.setattr(provider, "_open_menu", lambda *a, **k: None)

    provider.on_selection_context((0.0, 0.0), ["n1", "n2"], ["e1"])

    assert edit.selected_nodes == {"n1", "n2"}
    assert edit.selected_edges == {"e1"}
