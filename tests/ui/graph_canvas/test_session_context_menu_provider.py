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


class TestMenuSupersedesTheOpenOne:
    """Right-clicking a second node replaces the open menu in one gesture.

    Two halves make that work and both are easy to regress:

    - browser side, ``HwPopup.onOverlayContextMenu`` re-dispatches the click
      that its own overlay swallowed (otherwise the NATIVE menu appears);
    - Python side, the dispatcher closes the open menu before routing the new
      intent.

    Only the Python half is testable here. The ORDERING is the substance: the
    previous menu's ``on_close`` resets ``EditState`` and ``_OpenMenuContext``,
    and the intent handlers seed both before opening anything — so closing any
    later than the dispatcher would have the old gesture's cleanup wipe the new
    gesture's state.
    """

    def _handlers(self, provider):
        from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import (
            ContextMenuHandlers,
        )

        return ContextMenuHandlers(visual_layer=MagicMock(), provider=provider)

    def test_close_open_menu_is_a_noop_without_a_menu(self):
        provider = _make_provider()
        provider.close_open_menu()  # must not raise
        assert provider._open_popup is None

    def test_close_open_menu_closes_and_lets_on_close_clear_the_handle(self):
        """It must NOT clear _open_popup itself — Popup.close() fires on_close
        synchronously, and that is what owns the attribute."""
        provider = _make_provider()
        popup = MagicMock()
        provider._open_popup = popup

        provider.close_open_menu()

        popup.close.assert_called_once()

    def test_a_dead_popup_does_not_take_the_next_menu_down(self):
        """Page closed under a pending gesture: closing raises, and the next
        menu must still open."""
        provider = _make_provider()
        popup = MagicMock()
        popup.close.side_effect = RuntimeError("client is gone")
        provider._open_popup = popup

        provider.close_open_menu()

        assert provider._open_popup is None

    def test_dispatcher_closes_before_routing_the_intent(self):
        """The ordering guarantee, asserted as an ordering rather than by
        outcome — an intent that ran first would see the previous gesture's
        cleanup land on top of the state it had just written."""
        from haywire.ui.components.graph.event_definitions import ContextMenuSelectedEvent

        provider = _make_provider()
        calls: list[str] = []
        cast(Any, provider).close_open_menu = lambda: calls.append("close")
        cast(Any, provider).on_selection_context = lambda *a, **k: calls.append("intent")

        self._handlers(provider).process_context_menu(
            ContextMenuSelectedEvent(
                screenX=1.0,
                screenY=2.0,
                canvasX=3.0,
                canvasY=4.0,
                selectedNodes=["n1"],
                selectedEdges=[],
            )
        )

        assert calls == ["close", "intent"]


def test_no_interface_stub_shadows_a_real_implementation():
    """Every verb declared on IContextMenuProvider must be re-declared on the
    concrete provider.

    ``SessionContextMenuProvider(IContextMenuProvider, BaseContextMenuProvider)``
    lists the interface FIRST, so a `...` stub there wins the MRO over the
    mixin's working implementation — and loses silently, because a stub returns
    None instead of raising. `close_open_menu` shipped broken this way for
    exactly as long as it took to write a test for it.
    """
    from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import (
        IContextMenuProvider,
    )

    declared = {
        name
        for name, attr in vars(IContextMenuProvider).items()
        if callable(attr) and not name.startswith("__")
    }
    shadowed = [
        name
        for name in sorted(declared)
        if getattr(SessionContextMenuProvider, name).__qualname__.startswith("IContextMenuProvider.")
    ]
    assert not shadowed, (
        f"{shadowed} resolve to IContextMenuProvider's empty stub on "
        f"SessionContextMenuProvider — calling them does nothing, silently. "
        f"Re-declare each on the concrete provider (delegating to "
        f"BaseContextMenuProvider where that is the real implementation)."
    )


class TestCollapseToggle:
    """The collapse row toggles on EVERY click, not just the first.

    ``hui.menu_row`` does not dismiss its popup, so the menu stays on screen
    after a command. The first version of this row read the fold state when it
    DREW and closed over it, which meant every subsequent click re-sent the
    same value: it folded, and then would not unfold. The decision lives on the
    provider now, evaluated per click.
    """

    def _provider_with_node(self, collapsed: bool = False):
        provider = _make_provider()
        props = SimpleNamespace(collapsed=collapsed)
        wrapper = SimpleNamespace(node=SimpleNamespace(props=props))
        graph = MagicMock()
        graph.get_node_wrapper.return_value = wrapper
        stub = cast(Any, provider)._test_edit_stub
        stub.active_graph = graph
        stub.selected_nodes = {"n1"}
        return provider, props

    def test_repeated_toggles_alternate(self):
        provider, props = self._provider_with_node(collapsed=False)

        assert provider.toggle_selection_collapsed() is True
        assert props.collapsed is True
        assert provider.toggle_selection_collapsed() is False
        assert props.collapsed is False
        assert provider.toggle_selection_collapsed() is True
        assert props.collapsed is True

    def test_toggle_returns_the_new_state_for_the_row_to_relabel_with(self):
        provider, _props = self._provider_with_node(collapsed=True)
        assert provider.toggle_selection_collapsed() is False

    def test_a_mixed_selection_reads_as_not_collapsed(self):
        """So the first press folds everything, rather than unfolding the
        already-folded half of the selection."""
        provider = _make_provider()
        folded = SimpleNamespace(node=SimpleNamespace(props=SimpleNamespace(collapsed=True)))
        loose = SimpleNamespace(node=SimpleNamespace(props=SimpleNamespace(collapsed=False)))
        graph = MagicMock()
        graph.get_node_wrapper.side_effect = lambda nid: {"a": folded, "b": loose}[nid]
        stub = cast(Any, provider)._test_edit_stub
        stub.active_graph = graph
        stub.selected_nodes = {"a", "b"}

        assert provider.selection_is_collapsed() is False
        assert provider.toggle_selection_collapsed() is True
        assert folded.node.props.collapsed is True
        assert loose.node.props.collapsed is True

    def test_empty_selection_is_not_collapsed_and_toggling_is_harmless(self):
        provider = _make_provider()
        assert provider.selection_is_collapsed() is False
        provider.toggle_selection_collapsed()  # must not raise

    def test_a_vanished_node_is_skipped_not_fatal(self):
        """A selection can name a node deleted under an already-open menu."""
        provider = _make_provider()
        graph = MagicMock()
        graph.get_node_wrapper.return_value = None
        stub = cast(Any, provider)._test_edit_stub
        stub.active_graph = graph
        stub.selected_nodes = {"gone"}

        assert provider._selected_props() == []
        assert provider.selection_is_collapsed() is False
        provider.toggle_selection_collapsed()  # must not raise


class TestGraphWideCardReset:
    """`clear_node_card_overrides` is what keeps the graph tier usable.

    Mirrors are "unset tracks, set ignores" per hop, so every node folded by
    hand permanently stops listening to the graph. Without a way back, a
    graph-wide collapse covers fewer and fewer nodes over time, with nothing
    saying why.
    """

    def _graph_of(self, provider, *locally_set: bool):
        wrappers = {}
        for i, is_set in enumerate(locally_set):
            props = MagicMock()
            props.is_locally_set.side_effect = lambda field, s=is_set: s
            wrappers[f"n{i}"] = SimpleNamespace(node=SimpleNamespace(props=props))
        graph = SimpleNamespace(node_wrappers=wrappers)
        cast(Any, provider)._test_edit_stub.active_graph = graph
        return wrappers

    def test_it_resets_both_axes_on_every_node_that_has_an_opinion(self):
        provider = _make_provider()
        wrappers = self._graph_of(provider, True, True)

        assert provider.clear_node_card_overrides() == 2
        for wrapper in wrappers.values():
            reset_fields = {c.args[0] for c in wrapper.node.props.reset.call_args_list}
            assert reset_fields == {"detail", "collapsed"}

    def test_it_leaves_tracking_nodes_alone(self):
        """Resetting a field that is not locally set would be a no-op anyway,
        but counting it would overstate what the command did."""
        provider = _make_provider()
        wrappers = self._graph_of(provider, False, False)

        assert provider.clear_node_card_overrides() == 0
        for wrapper in wrappers.values():
            wrapper.node.props.reset.assert_not_called()

    def test_the_count_is_nodes_touched_not_fields_reset(self):
        """The caller reports it to the user, so it has to mean "nodes"."""
        provider = _make_provider()
        self._graph_of(provider, True, False, True)

        assert provider.clear_node_card_overrides() == 2

    def test_no_graph_is_zero_not_a_crash(self):
        provider = _make_provider()
        cast(Any, provider)._test_edit_stub.active_graph = None
        assert provider.clear_node_card_overrides() == 0

    def test_one_exploding_node_does_not_abort_the_rest(self):
        """A stale wrapper must not leave the graph half-reset."""
        provider = _make_provider()
        bad = MagicMock()
        bad.is_locally_set.return_value = True
        bad.reset.side_effect = RuntimeError("stale bag")
        good = MagicMock()
        good.is_locally_set.return_value = True
        cast(Any, provider)._test_edit_stub.active_graph = SimpleNamespace(
            node_wrappers={
                "bad": SimpleNamespace(node=SimpleNamespace(props=bad)),
                "good": SimpleNamespace(node=SimpleNamespace(props=good)),
            }
        )

        provider.clear_node_card_overrides()  # must not raise
        assert good.reset.call_count == 2
