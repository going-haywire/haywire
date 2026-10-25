"""The graph editor reads a stand-in node like any other: the toolbar gates and the canvas.

Each test runs for both causes of a stand-in: a node whose library is missing, and a
node whose constructor raises (see tests/core/test_node/test_stand_in.py).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.panels._gating import is_reroute_node
from haybale_graph_editor.panels._selection_forms import node_appearance_subject
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.graph.types import ChangeReason, ValidationResult

from tests.conftest import edit_route

pytestmark = pytest.mark.integration

_UNKNOWN = "haybale-testing:node:NoSuchNode"


@pytest.fixture(params=["unknown_key", "constructor_raises"])
def stand_in(request, graph_with_library_system, construction_fails):
    if request.param == "unknown_key":
        key = _UNKNOWN
    else:
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        key = TestPrintNode.class_identity.registry_key
        construction_fails(1)
    wrapper = graph_with_library_system.create_node_wrapper(key, position=(10.0, 20.0))
    assert wrapper is not None
    assert wrapper.is_stand_in
    if request.param == "constructor_raises":
        assert wrapper.state.error_instantiate is not None
    return graph_with_library_system, wrapper


def _selected(graph, wrapper) -> Any:
    edit = SimpleNamespace(
        active_node=wrapper,
        active_graph=graph,
        active_route=edit_route(MagicMock()),
        selected_nodes={wrapper.node_id},
        selected_edges=set(),
    )
    return SimpleNamespace(data={EditState: edit})


def test_the_selection_toolbar_gates_read_a_stand_in(stand_in):
    graph, wrapper = stand_in
    ctx = _selected(graph, wrapper)

    assert is_reroute_node(ctx) is False
    assert node_appearance_subject(ctx).status != "hidden"


def test_the_canvas_redraws_a_stand_in(stand_in):
    graph, wrapper = stand_in
    handler = VisualLayerHandlers(
        graph=graph, route=edit_route(MagicMock()), skin_factory=MagicMock(), canvas_vue=MagicMock()
    )
    card = MagicMock(position=(10.0, 20.0))
    handler.node_panels[wrapper.node_id] = card

    handler.on_validated(
        ValidationResult(nodes={wrapper.node_id: ChangeReason.NODE_HOT_RELOADED}, validation_time_ms=0.0)
    )

    card.refresh.assert_called_once_with(ChangeReason.NODE_HOT_RELOADED)
