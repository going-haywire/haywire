"""A torn-down canvas manager stops following its graph's props.

The graph outlives every canvas drawn for it (``GraphEditor.draw()`` rebuilds
canvases, Group canvases close), so a manager that leaves its props
subscriptions behind pushes values to a deleted element on the next edit.
"""

from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haywire.core.di.context import get_settings_registry
from haywire.core.edge.settings import EdgeDefaultSettings
from haywire.core.graph.base import BaseGraph
from haywire.core.skin.settings import NodeDefaultSkinSettings

pytestmark = pytest.mark.integration


@pytest.fixture
def props_graph(graph_with_library_system: BaseGraph) -> BaseGraph:
    """A graph whose props shadows resolve, whichever registry was built first in this process."""
    registry = get_settings_registry()
    for schema in (EdgeDefaultSettings, NodeDefaultSkinSettings):
        assert registry.has(schema.class_identity.registry_key)
    return graph_with_library_system


def _manager(graph: BaseGraph) -> tuple[GraphCanvasManager, MagicMock, MagicMock]:
    """A manager with __init__ bypassed, holding only what the props wiring touches.

    Returns the manager, its canvas mock and its node-theme-apply mock.
    """
    mgr = object.__new__(GraphCanvasManager)
    mgr.graph = graph
    mgr.session_id = "test"
    mgr._sync_task = None
    canvas = MagicMock()
    apply_theme = MagicMock()
    mgr.canvas_vue = canvas
    mgr.visual_layer = MagicMock()
    mgr._apply_graph_node_theme = apply_theme  # type: ignore[method-assign]
    return mgr, canvas, apply_theme


def test_edge_defaults_reach_the_canvas_while_the_manager_lives(props_graph: BaseGraph):
    graph = props_graph
    mgr, canvas, apply_theme = _manager(graph)
    mgr._follow_graph_props()
    canvas.set_edge_defaults.reset_mock()

    graph.props.edge_width = 3.0

    canvas.set_edge_defaults.assert_called_once()
    mgr.cleanup()


def test_cleanup_stops_every_props_push(props_graph: BaseGraph):
    graph = props_graph
    mgr, canvas, apply_theme = _manager(graph)
    mgr._follow_graph_props()
    mgr.cleanup()
    canvas.reset_mock()
    apply_theme.reset_mock()

    graph.props.edge_arrow = "filled"
    graph.props.edge_width = 4.0
    graph.props.node_theme = "somewhere-else"

    canvas.set_edge_defaults.assert_not_called()
    apply_theme.assert_not_called()
