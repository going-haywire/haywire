"""Stage view edits like patch view: canvas events, menus, toolbar polls and the stage rows."""

from __future__ import annotations

import functools
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import MagicMock, patch

import pytest

from haybale_graph_editor.access import level_mode
from haybale_graph_editor.editors.graph_canvas.event_handlers import build_event_handler_map
from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import (
    ContextMenuHandlers,
    SessionContextMenuProvider,
)
from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
    SelectionToolbarHandlers,
    SelectionToolbarProvider,
)
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.panels.graph.menu.selection.stage import (
    AddToStageMenuPanel,
    RemoveFromStageMenuPanel,
)
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import SelectionMenu
from haywire.core.access import AccessTier
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.editor import Editor
from haywire.core.node.layout import PATCH, STAGE
from haywire.ui.components.graph.event_definitions import (
    AddToStageEvent,
    ContextMenuCanvasEvent,
    ContextMenuEdgeEvent,
    EdgeCreatedEvent,
    NodeCreateRequestEvent,
    RemoveFromStageEvent,
    SelectionChangedEvent,
    SyncEdgeReconnectEvent,
    UserDragEndEvent,
    UserDragStartEvent,
    UserDragUpdateEvent,
    UserPasteClipboardEvent,
    UserRemoveEvent,
    UserResizeEndEvent,
)

from tests.conftest import edit_route

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Dispatch on a stage canvas
# ---------------------------------------------------------------------------

_SOURCES = (
    VisualLayerHandlers,
    SelectionHandlers,
    InteractionHandlers,
    ContextMenuHandlers,
    SelectionToolbarHandlers,
)


def _recording_map(calls: list[str]) -> dict[str, Callable]:
    """The real handler map, each handler replaced by one that records its event type."""
    sources = [object.__new__(cls) for cls in _SOURCES]
    real = build_event_handler_map(sources)
    recorded: dict[str, Callable] = {}
    for event_type, handler in real.items():

        def record(event, _t=event_type):
            calls.append(_t)

        # Keeps the _handles_event_* markers the dispatcher reads.
        recorded[event_type] = functools.wraps(handler)(record)
    return recorded


def _manager(channel, tier: AccessTier = AccessTier.EDIT) -> tuple[Any, list[str]]:
    calls: list[str] = []
    manager: Any = object.__new__(GraphCanvasManager)
    manager.route = EditRoute(lambda: MagicMock(), lambda: level_mode(tier.satisfies, False))
    manager.channel = channel
    manager.visual_layer = MagicMock()
    manager._event_handlers = _recording_map(calls)
    return manager, calls


_EDIT_EVENTS = [
    UserDragStartEvent(nodes=["a"]),
    UserDragUpdateEvent(positions={"a": {"x": 1.0, "y": 2.0}}),
    UserDragEndEvent(nodes=["a"]),
    UserResizeEndEvent(nodeId="a", width=200.0, height=100.0, size_adapt="manual"),
    SelectionChangedEvent(selectedNodes=["a"], selectedEdges=[]),
    UserRemoveEvent(nodes=["a"], edges=[]),
    RemoveFromStageEvent(node_ids=["a"]),
    AddToStageEvent(node_ids=["a"]),
    UserPasteClipboardEvent(canvasX=0.0, canvasY=0.0, clipboardText=""),
    NodeCreateRequestEvent(registryKey="k", position={"x": 0.0, "y": 0.0}),
    EdgeCreatedEvent(sourceNodeId="a", outletPinId="o", sinkNodeId="b", inletPinId="i"),
    SyncEdgeReconnectEvent(edge_id="e", anchorNodeId="a", anchorPinId="o", anchorEnd="outlet"),
]


@pytest.mark.parametrize("event", _EDIT_EVENTS, ids=lambda e: type(e).__name__)
def test_stage_canvas_runs_every_edit_gesture_at_edit(event):
    manager, calls = _manager(STAGE)
    manager._handle_canvas_event(event)
    assert calls == [event.event_type]


def test_stage_and_patch_canvases_dispatch_the_same_events_at_every_tier():
    for tier in (AccessTier.VIEW, AccessTier.OPERATE, AccessTier.EDIT, AccessTier.ADMIN):
        stage, stage_calls = _manager(STAGE, tier)
        patch_, patch_calls = _manager(PATCH, tier)
        for event in _EDIT_EVENTS:
            stage._handle_canvas_event(event)
            patch_._handle_canvas_event(event)
        assert stage_calls == patch_calls, tier


def test_a_locked_stage_canvas_is_capped_at_operate_as_in_patch_view():
    for channel in (STAGE, PATCH):
        manager, calls = _manager(channel, tier=AccessTier.OPERATE)
        manager._handle_canvas_event(UserRemoveEvent(nodes=["a"], edges=[]))
        assert calls == [], channel
        manager._handle_canvas_event(SelectionChangedEvent(selectedNodes=["a"], selectedEdges=[]))
        assert calls == ["selectionChanged"], channel  # selecting is looking


def test_a_refused_stage_drag_snaps_back():
    manager, calls = _manager(STAGE, tier=AccessTier.OPERATE)
    manager._handle_canvas_event(UserDragEndEvent(nodes=["a", "b"]))
    manager.visual_layer.resync_positions.assert_called_once_with(["a", "b"])


def test_stage_canvas_duplicates_and_cuts():
    manager, _ = _manager(STAGE)
    manager.selection = MagicMock()
    manager.copy_selection = MagicMock()
    manager.delete_selection = MagicMock()
    manager._own_selection = MagicMock(return_value=(["a"], []))
    manager.duplicate_selection()
    manager.cut_selection()
    manager.selection.duplicate_selection.assert_called_once_with(["a"], [])
    manager.copy_selection.assert_called_once_with()
    manager.delete_selection.assert_called_once_with()


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------


def _handlers() -> tuple[ContextMenuHandlers, MagicMock]:
    provider = MagicMock()
    handlers = ContextMenuHandlers(visual_layer=MagicMock(), provider=provider, allows=lambda _t: True)
    return handlers, provider


def test_the_background_menu_opens():
    handlers, provider = _handlers()
    handlers.process_context_menu(ContextMenuCanvasEvent(screenX=1, screenY=2, canvasX=3, canvasY=4))
    provider.on_canvas_context.assert_called_once()


def test_the_edge_menu_opens():
    handlers, provider = _handlers()
    handlers.process_context_menu(
        ContextMenuEdgeEvent(screenX=1, screenY=2, canvasX=3, canvasY=4, edge_id="e")
    )
    provider.on_edge_context.assert_called_once()


def test_the_selection_menu_is_the_selection_menu():
    provider: Any = object.__new__(SessionContextMenuProvider)
    provider._context = MagicMock()
    provider._open_menu = MagicMock()
    provider.on_selection_context((1, 2), ["a"], [])
    provider._open_menu.assert_called_once_with(SelectionMenu, (1, 2))


def test_the_toolbar_provider_forwards_the_stage_verbs():
    menu_provider = MagicMock()
    toolbar: Any = object.__new__(SelectionToolbarProvider)
    toolbar._menu_provider = menu_provider
    toolbar.add_to_stage()
    toolbar.remove_from_stage()
    menu_provider.add_to_stage.assert_called_once_with()
    menu_provider.remove_from_stage.assert_called_once_with()


def test_both_hosts_satisfy_the_stage_verbs():
    for host in (SessionContextMenuProvider, SelectionToolbarProvider):
        for verb in ("add_to_stage", "remove_from_stage"):
            assert hasattr(host, verb), f"{host.__name__} lacks {verb}"


def _ctx(flags: dict[str, bool]):
    """A context whose selection is every node in ``flags``, each on or off stage."""
    wrappers = {
        nid: SimpleNamespace(node=SimpleNamespace(props=SimpleNamespace(on_stage=on)))
        for nid, on in flags.items()
    }
    graph = SimpleNamespace(get_node_wrapper=wrappers.get)
    edit = SimpleNamespace(selected_nodes=set(flags), selected_edges=set(), active_graph=graph)
    data = MagicMock()
    data.__getitem__.side_effect = lambda key: edit if key is EditState else MagicMock()
    return SimpleNamespace(data=data)


def test_add_to_stage_row_shows_for_off_stage_nodes_in_either_view():
    assert AddToStageMenuPanel.poll(_ctx({"a": False})) is True
    assert AddToStageMenuPanel.poll(_ctx({"a": False, "b": True})) is True
    assert AddToStageMenuPanel.poll(_ctx({"a": True})) is False
    assert AddToStageMenuPanel.poll(_ctx({})) is False
    assert AddToStageMenuPanel.class_identity.surface is SelectionMenu


def test_remove_from_stage_row_shows_for_on_stage_nodes_in_either_view():
    assert RemoveFromStageMenuPanel.poll(_ctx({"a": True})) is True
    assert RemoveFromStageMenuPanel.poll(_ctx({"a": False, "b": True})) is True
    assert RemoveFromStageMenuPanel.poll(_ctx({"a": False})) is False
    assert RemoveFromStageMenuPanel.class_identity.surface is SelectionMenu


@pytest.mark.parametrize("cls", [AddToStageMenuPanel, RemoveFromStageMenuPanel])
def test_the_stage_verbs_need_edit(cls):
    assert cls.class_identity.access is AccessTier.EDIT


def test_the_provider_emits_the_stage_events_for_the_selection():
    provider: Any = object.__new__(SessionContextMenuProvider)
    provider._context = _ctx({"a": False, "b": False})
    provider._emit = MagicMock()
    provider.add_to_stage()
    provider.remove_from_stage()
    added, removed = (c.args[0] for c in provider._emit.call_args_list)
    assert isinstance(added, AddToStageEvent)
    assert isinstance(removed, RemoveFromStageEvent)
    assert sorted(added.node_ids) == ["a", "b"]
    assert sorted(removed.node_ids) == ["a", "b"]


# ---------------------------------------------------------------------------
# Delete in stage view is the ordinary delete
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_delete_in_stage_view_deletes_the_node(graph_with_library_system, library_system):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    key = TestPrintNode.class_identity.registry_key
    wrapper = graph.create_node_wrapper(key, position=(0.0, 0.0))
    node_id = wrapper.node_id
    editor.add_to_stage([node_id])

    layer: Any = object.__new__(VisualLayerHandlers)
    layer.route = edit_route(editor)
    layer.graph = graph
    layer.channel = STAGE
    layer.node_panels = {}
    layer.is_locked = lambda _nid: False

    manager, _ = _manager(STAGE)
    manager._event_handlers = build_event_handler_map([layer])

    with patch("haybale_graph_editor.editors.graph_canvas.handlers.visual_layer.ui.notify"):
        manager._handle_canvas_event(UserRemoveEvent(nodes=[node_id], edges=[]))
        assert graph.get_node_wrapper(node_id) is None
        assert editor.undo()
        assert graph.get_node_wrapper(node_id) is not None


# --- the selection toolbar polls as in patch view ---------------------------


def _toolbar_ctx():
    """A context with one unlocked node selected."""
    node = SimpleNamespace(props=SimpleNamespace(on_stage=True, locked=False))
    wrapper = SimpleNamespace(node=node)
    graph = SimpleNamespace(get_node_wrapper=lambda _nid: wrapper)
    edit = SimpleNamespace(
        selected_nodes={"a"}, selected_edges=set(), active_graph=graph, active_node=wrapper
    )
    data = MagicMock()
    data.__getitem__.side_effect = lambda key: edit if key is EditState else MagicMock()
    return SimpleNamespace(data=data)


def test_the_toolbar_panels_poll_in_a_stage_view_as_in_patch_view():
    from haybale_graph_editor.panels.graph.toolbar.appearance import AppearanceToolbarPanel
    from haybale_graph_editor.panels.graph.toolbar.selection import (
        CollapseToolbarPanel,
        LockToolbarPanel,
    )
    from haybale_graph_editor.panels.graph.toolbar.style import EdgeStyleToolbarPanel

    ctx = _toolbar_ctx()
    with (
        patch("haybale_graph_editor.panels.graph.toolbar.selection.is_reroute_node", return_value=False),
        patch(
            "haybale_graph_editor.panels.graph.toolbar.selection.selection_has_locked", return_value=False
        ),
        patch("haybale_graph_editor.panels.graph.toolbar.selection.locked_bag", return_value=object()),
        patch(
            "haybale_graph_editor.panels.graph.toolbar.appearance.node_appearance_subject",
            return_value=SimpleNamespace(editable=True),
        ),
        patch(
            "haybale_graph_editor.panels.graph.toolbar.style.edge_style_subject",
            return_value=SimpleNamespace(editable=True),
        ),
    ):
        polls = {
            "collapse": CollapseToolbarPanel.poll(ctx),
            "appearance": AppearanceToolbarPanel.poll(ctx),
            "lock": LockToolbarPanel.poll(ctx),
            "style": EdgeStyleToolbarPanel.poll(ctx),
        }
    assert polls == {"collapse": True, "appearance": True, "lock": True, "style": True}


# --- a node leaving the stage leaves the stage canvas's selection ---------


def test_a_node_unmounted_from_the_stage_canvas_is_reported_for_selection_pruning():
    layer: Any = object.__new__(VisualLayerHandlers)
    layer.channel = STAGE
    layer.node_panels = {"n1": MagicMock()}
    layer.on_node_unmounted = MagicMock()
    layer.remove_node_visual = MagicMock()
    wrapper = SimpleNamespace(node=SimpleNamespace(props=SimpleNamespace(on_stage=False)))
    layer.graph = SimpleNamespace(get_node_wrapper=lambda _nid: wrapper)

    layer._follow_membership("n1", [])

    layer.remove_node_visual.assert_called_once_with("n1")
    layer.on_node_unmounted.assert_called_once_with("n1")
