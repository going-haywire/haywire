"""The style panels show for an edge with a style bag, and only for one."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels.graph.menu.edge.edge import EdgeStyleMenuPanel
from haybale_graph_editor.panels.properties.introspect.edge import EdgeStylePanel
from haybale_graph_editor.state.edit_state import EditState

pytestmark = pytest.mark.unit


def _ctx(edge, route=True):
    state = SimpleNamespace(active_edge=edge, active_route=object() if route else None)
    return SimpleNamespace(data={EditState: state})


@pytest.mark.parametrize("panel", [EdgeStylePanel, EdgeStyleMenuPanel])
def test_an_edge_with_a_bag_polls_true(panel):
    assert panel.poll(_ctx(SimpleNamespace(style=object())))


@pytest.mark.parametrize("panel", [EdgeStylePanel, EdgeStyleMenuPanel])
def test_an_edge_without_a_bag_polls_false(panel):
    assert not panel.poll(_ctx(SimpleNamespace(style=None)))


@pytest.mark.parametrize("panel", [EdgeStylePanel, EdgeStyleMenuPanel])
def test_no_edge_polls_false(panel):
    assert not panel.poll(_ctx(None))


def test_the_style_panel_polls_false_with_no_level_open():
    assert not EdgeStylePanel.poll(_ctx(SimpleNamespace(style=object()), route=False))
