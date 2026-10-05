"""The immediate path's guards: an unchanged value tells the node nothing, and a loop ends after one pass."""

import logging
from typing import Any, cast

import pytest

from tests.conftest import make_edge, make_node
from tests.core.test_graph.callback_group import EMIT, LISTEN, build_group, subscriptions

pytestmark = pytest.mark.integration

RELAY = "haybale-testing:node:CallbackRelayProbeNode"
PORT_LOGGER = "haywire.core.types.port"


def _split_with_reroute(graph, edge_id: str) -> str:
    """Split *edge_id* with a reroute node the way the canvas does, returning the reroute's id."""
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    action = SplitEdgeWithRerouteAction(
        graph=cast(Any, graph),
        edge_id=edge_id,
        position=(200.0, 0.0),
        registry_key=RerouteNode.class_identity.registry_key,
    )
    action._execute_impl()
    reroute_id = action.reroute_node_id
    assert reroute_id is not None
    return reroute_id


def _loop_warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == PORT_LOGGER and "loop" in r.getMessage()]


class TestEchoGuard:
    def test_two_callback_reroutes_looped_keep_the_listener_subscribed(
        self, graph_with_library_system, caplog
    ):
        """Plain reroutes relay the value unchanged, so the echo guard ends the loop: no warning."""
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)
        graph = graph_with_library_system
        listener = make_node(graph, LISTEN, position=(0, 0))
        emitter = make_node(graph, EMIT, position=(600, 0))
        edge = make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
        first = _split_with_reroute(graph, edge.edge_id)
        onward = next(e for e in graph.edge_wrappers.values() if e.source_node_id == first)
        second = _split_with_reroute(graph, onward.edge_id)

        make_edge(graph, second, "out", first, "in")  # closes the loop, displacing the listener's edge
        graph.force_validation()

        assert subscriptions(emitter) == [listener.node.value("listen_callback")]
        assert _loop_warnings(caplog) == []

    def test_a_pool_fed_the_same_subscription_twice_tells_its_node_once(self, graph_with_library_system):
        graph = graph_with_library_system
        listener = make_node(graph, LISTEN, position=(0, 0))
        emitter = make_node(graph, EMIT, position=(400, 0))
        heard: list = []
        emitter.node.printout = lambda port, value: heard.append(value)  # type: ignore[attr-defined]
        make_edge(graph, listener.node_id, "listen_callback", emitter.node_id, "edge_callback")
        graph.force_validation()
        assert len(heard) == 1

        listener.node.out("listen_callback", listener.node.value("listen_callback"))

        assert len(heard) == 1


class TestReentrancyGuard:
    def test_a_renaming_loop_is_cut_after_one_pass(self, graph_with_library_system, caplog):
        graph = graph_with_library_system
        first = make_node(graph, RELAY, position=(0, 0))
        second = make_node(graph, RELAY, position=(300, 0))
        first.node.suffix = "2"  # type: ignore[attr-defined]
        second.node.suffix = "2"  # type: ignore[attr-defined]
        make_edge(graph, first.node_id, "out", second.node_id, "in")
        make_edge(graph, second.node_id, "out", first.node_id, "in")
        graph.force_validation()
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)

        first.node.out("out", "x")

        assert first.is_valid() and second.is_valid()  # noqa: PT018
        assert second.node.heard == ["x"]  # type: ignore[attr-defined]
        assert first.node.heard == ["x2"]  # type: ignore[attr-defined]
        # Q24: "x22" reached `second.in` while its on_change ran; it was dropped and not stored.
        assert second.node.ports["in"].get_value() == "x"
        warnings = _loop_warnings(caplog)
        assert len(warnings) == 1
        assert second.node_id in warnings[0]


class TestAcrossASubgraphBoundary:
    @staticmethod
    def _loop_through_a_group(graph, suffix: str):
        """listener -> card -> (interior relay) -> card -> probe -> card; the probe closes the loop."""
        group = build_group(graph)
        group.definition.create_edge_wrapper(
            group.input_node.node_id, "sub_in", group.output_node.node_id, "sub_out"
        )
        listener = make_node(graph, LISTEN, position=(0, 0))
        make_edge(graph, listener.node_id, "listen_callback", group.card.node_id, "in_sub_in")
        probe = make_node(graph, RELAY, position=(600, 0))
        probe.node.suffix = suffix  # type: ignore[attr-defined]
        make_edge(graph, group.card.node_id, "out_sub_out", probe.node_id, "in")
        make_edge(graph, probe.node_id, "out", group.card.node_id, "in_sub_in")
        graph.force_validation()
        return group, listener, probe

    def test_an_unchanged_value_looped_through_a_group_ends(self, graph_with_library_system, caplog):
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)

        group, listener, _probe = self._loop_through_a_group(graph_with_library_system, "")

        assert group.card.node.ports["in_sub_in"].get_value() == listener.node.value("listen_callback")
        assert _loop_warnings(caplog) == []

    def test_a_renaming_loop_through_a_group_is_cut_once(self, graph_with_library_system, caplog):
        """The interior relay runs on the same call stack, so one set covers both graphs."""
        caplog.set_level(logging.WARNING, logger=PORT_LOGGER)

        self._loop_through_a_group(graph_with_library_system, "2")

        assert len(_loop_warnings(caplog)) == 1
