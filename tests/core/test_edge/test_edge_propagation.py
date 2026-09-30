"""An edge's propagation: the user's lazy/eager choice, and the modes a flow or outlet locks.

A ``Pipe`` copies its mode at construction, so a change has to rebuild it. The
pin menu and the edge properties panel both write the property directly, which
is the path these cover.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types import Propagation

from tests.conftest import make_node

_ADD = "haybale-testing:node:TestAddFloatNode"

pytestmark = [pytest.mark.integration]


def _pipe_modes(outlet) -> list[bool]:
    """``is_lazy`` of every live pipe on ``outlet``."""
    if outlet._pipes is None:
        return []
    return [pipe.is_lazy for pipe in outlet._pipes._pipes.values()]


@pytest.fixture
def linked_pair(graph_with_library_system: BaseGraph):
    """Two Adds joined by one eager data edge, validated."""
    graph = graph_with_library_system
    source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
    edge = graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None
    graph.force_validation()
    return graph, source, sink, edge


@pytest.fixture
def callback_edge(graph_with_library_system):
    """An event node joined to an emit node by a callback edge."""
    from haybale_testing.nodes.testbed.custom_callback_node import TestCustomCallbackNode
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    graph = graph_with_library_system
    event = graph.create_node_wrapper(TestCustomCallbackNode.class_identity.registry_key, position=(0, 0))
    emit = graph.create_node_wrapper(TestEmitCallbackNode.class_identity.registry_key, position=(300, 0))
    edge = graph.create_edge_wrapper(event.node_id, "listen_callback", emit.node_id, "edge_callback")
    assert edge is not None
    return event, edge


@pytest.fixture
def promoted_outlet_edge(graph_with_library_system):
    """An edge out of a promoted setting outlet into an Add."""
    from haybale_testing.nodes.testbed.settings_node import SettingsNode
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    src = graph.create_node_wrapper(SettingsNode.class_identity.registry_key, position=(0, 0))
    sink = make_node(graph, _ADD)
    promote_setting(src.node, "example", "example_float", direction=PortType.OUTLET)
    pid = type(src.node.example).__dict__["example_float"].storage_key
    edge = graph.create_edge_wrapper(src.node_id, pid, sink.node_id, "value_a")
    assert edge is not None
    return src, pid, edge


class TestChoosingLazyOrEager:
    def test_a_fresh_edge_is_eager(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        assert edge.propagation is Propagation.EAGER
        assert edge.locked_propagation is None
        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_choosing_lazy_reaches_the_pipe(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        edge.propagation = Propagation.LAZY

        assert _pipe_modes(source.node.ports["result"]) == [True]

    def test_choosing_eager_again_reaches_the_pipe(self, linked_pair):
        _graph, source, _sink, edge = linked_pair

        edge.propagation = Propagation.LAZY
        edge.propagation = Propagation.EAGER

        assert _pipe_modes(source.node.ports["result"]) == [False]

    def test_a_lazy_edge_defers_the_write_instead_of_pushing(self, linked_pair):
        _graph, source, sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        sink_port = sink.node.ports["value_a"]
        sink_port.set_value(0.0)

        source.node.ports["result"].set_value(42.0)

        assert sink_port.get_value() == pytest.approx(0.0)
        assert len(sink_port._pending_lazy_pipes) == 1

    def test_resolving_the_sink_then_pulls_it(self, linked_pair):
        _graph, source, sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        sink_port = sink.node.ports["value_a"]
        sink_port.set_value(0.0)
        source.node.ports["result"].set_value(42.0)

        sink_port.resolve_dirty_data()

        assert sink_port.get_value() == pytest.approx(42.0)

    def test_an_eager_edge_still_pushes_immediately(self, linked_pair):
        _graph, source, sink, _edge = linked_pair
        sink_port = sink.node.ports["value_a"]

        source.node.ports["result"].set_value(42.0)

        assert sink_port.get_value() == pytest.approx(42.0)

    def test_setting_the_same_mode_is_a_no_op(self, linked_pair):
        """Re-asserting the current mode must not disturb the live pipe."""
        _graph, source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        pipe_before = next(iter(source.node.ports["result"]._pipes._pipes.values()))

        edge.propagation = Propagation.LAZY

        pipe_after = next(iter(source.node.ports["result"]._pipes._pipes.values()))
        assert pipe_after is pipe_before

    def test_the_other_edges_on_the_outlet_keep_their_own_mode(self, linked_pair):
        """A rebuild re-reads every edge, so a sibling must not be flipped too."""
        graph, source, _sink, edge = linked_pair
        third = make_node(graph, _ADD)
        graph.create_edge_wrapper(source.node_id, "result", third.node_id, "value_a")
        graph.force_validation()

        edge.propagation = Propagation.LAZY

        assert sorted(_pipe_modes(source.node.ports["result"])) == [False, True]

    def test_immediate_cannot_be_chosen(self, linked_pair):
        _graph, _source, _sink, edge = linked_pair

        with pytest.raises(ValueError, match="cannot be chosen"):
            edge.propagation = Propagation.IMMEDIATE

    def test_immediate_cannot_be_passed_at_creation(self, graph_with_library_system):
        graph = graph_with_library_system
        source, sink = make_node(graph, _ADD), make_node(graph, _ADD)

        with pytest.raises(ValueError, match="cannot be chosen"):
            graph.create_edge_wrapper(
                source.node_id, "result", sink.node_id, "value_a", propagation=Propagation.IMMEDIATE
            )


class TestLockedModes:
    def test_a_callback_edge_is_locked_immediate(self, callback_edge):
        event, edge = callback_edge

        assert edge.locked_propagation is Propagation.IMMEDIATE
        assert edge.propagation is Propagation.IMMEDIATE
        assert _pipe_modes(event.node.ports["listen_callback"]) == [False]

    def test_a_locked_edge_refuses_a_choice(self, callback_edge):
        _event, edge = callback_edge

        with pytest.raises(ValueError, match="locked"):
            edge.propagation = Propagation.LAZY

    def test_an_edge_out_of_a_promoted_outlet_is_locked_lazy(self, promoted_outlet_edge):
        src, pid, edge = promoted_outlet_edge

        assert edge.locked_propagation is Propagation.LAZY
        assert edge.propagation is Propagation.LAZY
        assert _pipe_modes(src.node.ports[pid]) == [True]
        with pytest.raises(ValueError, match="locked"):
            edge.propagation = Propagation.EAGER


class TestSaving:
    def test_the_edge_saves_the_chosen_mode(self, linked_pair):
        _graph, _source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY

        saved = edge.edge.to_dict()

        assert saved["propagation"] == "lazy"
        assert "is_lazy" not in saved

    def test_a_locked_mode_is_not_saved(self, callback_edge):
        _event, edge = callback_edge

        assert edge.edge.to_dict()["propagation"] == "eager"

    def test_loading_restores_the_chosen_mode(self, linked_pair):
        graph, _source, _sink, edge = linked_pair
        edge.propagation = Propagation.LAZY
        edge_id = edge.edge_id
        data = graph.to_dict()

        graph.clear()
        graph.load_from_dict(data)

        assert graph.get_edge_wrapper(edge_id).propagation is Propagation.LAZY

    def test_an_unknown_saved_mode_drops_the_edge(self, linked_pair):
        graph, _source, _sink, edge = linked_pair
        edge_id = edge.edge_id
        data = graph.to_dict()
        data["edges"][edge_id]["propagation"] = "sideways"

        graph.clear()
        graph.load_from_dict(data)

        assert graph.get_edge_wrapper(edge_id) is None


class TestToggling:
    def test_eager_toggles_to_lazy_and_back(self):
        assert Propagation.EAGER.toggled() is Propagation.LAZY
        assert Propagation.LAZY.toggled() is Propagation.EAGER

    def test_immediate_does_not_toggle(self):
        with pytest.raises(ValueError, match="cannot be toggled"):
            Propagation.IMMEDIATE.toggled()
