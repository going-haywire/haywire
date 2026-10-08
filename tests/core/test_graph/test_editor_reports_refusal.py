"""An Editor operation the graph refuses reports failure and leaves no undo step."""

import pytest

from haywire.core.graph.editor import Editor

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _two_notes(graph):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletVisualProbeNode

    key = SwingletVisualProbeNode.class_identity.registry_key
    return make_node(graph, key), make_node(graph, key)


def test_create_edge_reports_a_new_edge(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    v1, v2 = _two_notes(graph)

    assert editor.create_edge(v1.node_id, "note", v2.node_id, "note") is True
    assert len(graph.edge_wrappers) == 1


@pytest.mark.parametrize("reverse", [False, True], ids=["duplicate", "reverse"])
def test_create_edge_reports_an_edge_the_graph_refuses(graph_with_library_system, library_system, reverse):
    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    v1, v2 = _two_notes(graph)
    editor.create_edge(v1.node_id, "note", v2.node_id, "note")
    source, sink = (v2, v1) if reverse else (v1, v2)

    assert editor.create_edge(source.node_id, "note", sink.node_id, "note") is False
    assert len(graph.edge_wrappers) == 1
    assert editor.undo() is True
    assert graph.edge_wrappers == {}
    assert editor.can_undo() is False
