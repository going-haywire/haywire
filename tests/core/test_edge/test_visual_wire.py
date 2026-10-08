"""A VISUAL edge is drawn and saved but never executed: no adapter chain, no pipe, no propagation."""

import pytest

from haywire.core.types import WireRole

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def _probes(graph, count: int = 2):
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    key = VisualProbeNode.class_identity.registry_key
    return [make_node(graph, key, position=(300 * i, 0)) for i in range(count)]


def test_a_visual_edge_validates_without_an_adapter_chain(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert edge.state.is_valid()
    assert edge.wire_type is not None and edge.wire_type.role is WireRole.VISUAL  # noqa: PT018
    assert edge.first_adapter is None
    assert edge.edge.chain_adapter_keys == []
    assert edge.propagation is None


def test_the_data_types_at_its_ends_need_not_match(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "count_in")
    graph.force_validation()

    assert edge.state.is_valid()


def test_nothing_travels_and_the_inlet_keeps_its_own_value(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    inlet = sink.node.ports["note_in"]

    source.node.ports["note_out"].set_value("hello")

    assert not inlet.data.has_linked_value()
    inlet.set_value("own")
    assert inlet.get_value() == "own"


def test_a_visual_inlet_takes_many_edges(graph_with_library_system):
    graph = graph_with_library_system
    first, second, sink = _probes(graph, 3)
    make_edge(graph, first.node_id, "note_out", sink.node_id, "note_in")
    make_edge(graph, second.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert len(sink.node.ports["note_in"].incoming.linked) == 2


def test_visual_pins_never_make_a_data_node_invalid(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert source.is_valid()
    assert sink.is_valid()


def test_a_visual_edge_survives_save_and_reload(graph_with_library_system):
    graph = graph_with_library_system
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()
    data = graph.to_dict()
    assert "propagation" not in data["edges"][edge.edge_id]

    graph.clear()
    graph.load_from_dict(data)
    graph.force_validation()

    reloaded = graph.get_edge_wrapper(edge.edge_id)
    assert reloaded is not None
    assert reloaded.state.is_valid()


def test_deleting_a_visual_edge_is_undoable(graph_with_library_system, library_system):
    from haywire.core.graph.editor import Editor

    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    assert editor.remove_elements([], [edge.edge_id])
    assert graph.get_edge_wrapper(edge.edge_id) is None

    assert editor.undo()
    graph.force_validation()
    restored = graph.get_edge_wrapper(edge.edge_id)
    assert restored is not None and restored.state.is_valid()  # noqa: PT018


def test_a_reroute_splits_a_visual_edge(graph_with_library_system, library_system):
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.graph.editor import Editor

    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    source, sink = _probes(graph)
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in")
    graph.force_validation()

    reroute_id = editor.split_edge_with_reroute(
        edge.edge_id, (150.0, 0.0), RerouteNode.class_identity.registry_key
    )
    graph.force_validation()

    assert reroute_id is not None
    reroute = graph.get_node_wrapper(reroute_id)
    assert reroute is not None and reroute.is_valid()  # noqa: PT018
    assert isinstance(reroute.node, RerouteNode)
    assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
