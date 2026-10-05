"""The edge menu's propagation row applies only to an edge that has propagation."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels.graph.menu.edge.edge import EdgePropagationMenuPanel
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import Propagation

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def graph_with_library_system(library_system) -> BaseGraph:
    return BaseGraph(filestem="Poll Test Graph", validation_scheduler=SyncScheduler())


def _ctx(edge):
    return SimpleNamespace(data={EditState: SimpleNamespace(active_edge=edge)})


def test_a_data_edge_polls_true():
    assert EdgePropagationMenuPanel.poll(_ctx(SimpleNamespace(propagation=Propagation.EAGER)))


def test_a_callback_edge_polls_false():
    assert not EdgePropagationMenuPanel.poll(_ctx(SimpleNamespace(propagation=None)))


def test_no_edge_polls_false():
    assert not EdgePropagationMenuPanel.poll(_ctx(None))


def test_a_visual_edge_polls_false(graph_with_library_system):
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    graph = graph_with_library_system
    key = VisualProbeNode.class_identity.registry_key
    source = make_node(graph, key, position=(0, 0))
    sink = make_node(graph, key, position=(300, 0))
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert edge.propagation is None
    assert not EdgePropagationMenuPanel.poll(_ctx(edge))
