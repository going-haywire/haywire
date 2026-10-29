"""The "Trim Canvas" shortcut on the canvas menu's toolbar, its provider verb, and its handler."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import SessionContextMenuProvider
from haybale_graph_editor.editors.graph_canvas.handlers.selection import SelectionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.panels.graph.menu.graph.context import FocusGraphPanel, TrimCanvasPanel
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import GraphToolBar
from haywire.core.node.layout import PATCH, STAGE
from haywire.ui.components.graph.event_definitions import TrimCanvasEvent

from tests.conftest import edit_route


def _ctx(graph: Any) -> Any:
    data = MagicMock()
    data.__getitem__.side_effect = lambda key: (
        SimpleNamespace(active_graph=graph) if key is EditState else MagicMock()
    )
    return SimpleNamespace(data=data)


def _handlers(editor: Any, positions: dict, channel=PATCH) -> tuple[SelectionHandlers, MagicMock, MagicMock]:
    graph = MagicMock()
    graph.trimmed_positions.return_value = positions
    visual_layer = MagicMock()
    handlers = SelectionHandlers(
        graph=graph,
        route=edit_route(editor),
        session_id="t",
        visual_layer=visual_layer,
        channel=channel,
    )
    return handlers, graph, visual_layer


def test_the_panel_sits_next_to_focus_on_the_toolbar() -> None:
    assert TrimCanvasPanel.class_identity.surface is GraphToolBar
    assert FocusGraphPanel.class_identity.order < TrimCanvasPanel.class_identity.order < 30


def test_the_panel_shows_only_for_a_graph_with_nodes() -> None:
    assert TrimCanvasPanel.poll(_ctx(None)) is False
    assert TrimCanvasPanel.poll(_ctx(SimpleNamespace(node_wrappers={}))) is False
    assert TrimCanvasPanel.poll(_ctx(SimpleNamespace(node_wrappers={"a": object()}))) is True


def test_the_provider_emits_a_trim_event() -> None:
    provider: Any = object.__new__(SessionContextMenuProvider)
    provider._emit = MagicMock()
    provider.trim_canvas()
    provider._emit.assert_called_once_with(TrimCanvasEvent())


def test_a_trim_moves_the_trimmed_positions_then_fits_after_validation() -> None:
    editor = MagicMock()
    positions = {"a": {"x": 1.0, "y": 2.0}}
    handlers, graph, visual_layer = _handlers(editor, positions)
    handlers.process_trim(TrimCanvasEvent())
    graph.trimmed_positions.assert_called_once_with(PATCH)
    editor.move_nodes_to.assert_called_once_with(positions, PATCH)
    visual_layer.fit_view_after_validation.assert_called_once_with()
    visual_layer.fit_view.assert_not_called()


def test_an_already_trimmed_canvas_only_fits_the_view() -> None:
    editor = MagicMock()
    handlers, graph, visual_layer = _handlers(editor, {})
    handlers.process_trim(TrimCanvasEvent())
    editor.move_nodes_to.assert_not_called()
    visual_layer.fit_view.assert_called_once_with()


def test_a_stage_canvas_declines_to_trim() -> None:
    editor = MagicMock()
    handlers, graph, visual_layer = _handlers(editor, {"a": {"x": 1.0, "y": 2.0}}, channel=STAGE)
    with patch("haybale_graph_editor.editors.graph_canvas.handlers.selection.ui.notify") as notify:
        handlers.process_trim(TrimCanvasEvent())
    editor.move_nodes_to.assert_not_called()
    visual_layer.fit_view.assert_not_called()
    notify.assert_called_once()


def test_a_pending_fit_runs_once_at_the_end_of_the_next_validation() -> None:
    layer: Any = object.__new__(VisualLayerHandlers)
    layer._fit_pending = False
    layer.canvas_vue = MagicMock()
    layer.channel = PATCH
    result = SimpleNamespace(total_changes=0, validation_time_ms=0.0, canvas_sizes={}, nodes={}, edges={})

    layer.fit_view_after_validation()
    layer.on_validated(result)
    layer.on_validated(result)

    layer.canvas_vue.zoom_container.center_on_content.assert_called_once_with()
