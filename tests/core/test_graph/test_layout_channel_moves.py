"""Moves and the canvas-size check lay a node out through a layout channel."""

from __future__ import annotations

import pytest

from haywire.core.graph.base import _CANVAS_MIN_SIZE
from haywire.core.graph.editor import Editor
from haywire.core.node.layout import PATCH, LayoutChannel
from haywire.core.undo.actions.graph_actions import MoveNodesAction

pytestmark = pytest.mark.integration

SWAPPED = LayoutChannel(
    "swapped", x="posY", y="posX", width="height", height="width", size_adapt="size_adapt"
)


def _key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def test_move_node_writes_the_channel_fields(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(1.0, 2.0))

    assert graph.move_node(wrapper.node_id, 10, 20, SWAPPED)

    assert wrapper.node.props.posY == 10
    assert wrapper.node.props.posX == 20


def test_move_nodes_to_undo_restores_the_channel_fields(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    wrapper = graph.create_node_wrapper(_key(), position=(1.0, 2.0))

    assert editor.move_nodes_to({wrapper.node_id: {"x": 10.0, "y": 20.0}}, SWAPPED)
    assert (wrapper.node.props.posY, wrapper.node.props.posX) == (10.0, 20.0)

    assert editor.history_manager.undo()

    assert (wrapper.node.props.posX, wrapper.node.props.posY) == (1.0, 2.0)


def test_move_nodes_by_delta_uses_the_channel(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    wrapper = graph.create_node_wrapper(_key(), position=(1.0, 2.0))

    assert editor.move_nodes([wrapper.node_id], 10.0, 20.0, SWAPPED)

    assert (wrapper.node.props.posX, wrapper.node.props.posY) == (21.0, 12.0)


def test_move_nodes_actions_do_not_merge_across_channels(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(1.0, 2.0))
    ids = [wrapper.node_id]

    patch_move = MoveNodesAction(graph, ids, 1.0, 1.0)
    assert patch_move.can_merge(MoveNodesAction(graph, ids, 1.0, 1.0, PATCH))
    assert not patch_move.can_merge(MoveNodesAction(graph, ids, 1.0, 1.0, SWAPPED))


def test_canvas_size_reads_the_channel(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(0.0, 0.0))
    wrapper.node.props.posY = 9000.0
    wrapper.node.props.posX = 0.0

    graph._check_canvas_size(SWAPPED)
    assert graph.canvas_width > _CANVAS_MIN_SIZE
    assert graph.canvas_height == _CANVAS_MIN_SIZE

    graph._check_canvas_size(PATCH)
    assert graph.canvas_width == _CANVAS_MIN_SIZE
    assert graph.canvas_height > _CANVAS_MIN_SIZE
