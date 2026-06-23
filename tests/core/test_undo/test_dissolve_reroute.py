"""Tests for dissolving a reroute node.

Covers DissolveRerouteAction: child-action structure, partial connection
handling, and the editor entry point.
"""

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_edge(source_node_id, outlet_port_id, sink_node_id, inlet_port_id, edge_id):
    class _E:
        pass

    e = _E()
    e.source_node_id = source_node_id
    e.outlet_port_id = outlet_port_id
    e.sink_node_id = sink_node_id
    e.inlet_port_id = inlet_port_id
    e.edge_id = edge_id
    return e


class _FakeGraph:
    """Minimal graph stub for unit tests."""

    def __init__(self, node_id="reroute_1", edges=None):
        self._node_id = node_id
        self._edges = edges or []  # list of EdgeWrapper-like objects

    def get_node_wrapper(self, node_id):
        if node_id == self._node_id:
            return object()  # truthy
        return None

    def _get_all_edges(self, node_id):
        return list(self._edges)


# ---------------------------------------------------------------------------
# Unit tests: child-action structure
# ---------------------------------------------------------------------------


def test_dissolve_fully_connected_creates_bridge_and_remove():
    """Normal case: 1 upstream + 1 downstream → RemoveElementsAction + 1 AddEdgeAction."""
    from haywire.core.undo.actions.graph_actions import (
        DissolveRerouteAction,
        RemoveElementsAction,
        AddEdgeAction,
    )

    upstream = _make_edge("A", "result", "reroute_1", "in", "e_up")
    downstream = _make_edge("reroute_1", "out", "B", "value_a", "e_down")
    graph = _FakeGraph(edges=[upstream, downstream])

    action = DissolveRerouteAction(graph=graph, node_id="reroute_1")

    kinds = [type(a) for a in action.actions]
    assert kinds == [RemoveElementsAction, AddEdgeAction]

    remove, bridge = action.actions
    assert remove.nodes == ["reroute_1"]
    assert bridge.source_node_id == "A"
    assert bridge.outlet_pin_id == "result"
    assert bridge.sink_node_id == "B"
    assert bridge.inlet_pin_id == "value_a"


def test_dissolve_fan_out_creates_multiple_bridges():
    """Outlet fans to two sinks → RemoveElementsAction + 2 AddEdgeActions."""
    from haywire.core.undo.actions.graph_actions import (
        DissolveRerouteAction,
        RemoveElementsAction,
        AddEdgeAction,
    )

    upstream = _make_edge("A", "result", "reroute_1", "in", "e_up")
    down1 = _make_edge("reroute_1", "out", "B", "value_a", "e_d1")
    down2 = _make_edge("reroute_1", "out", "C", "value_b", "e_d2")
    graph = _FakeGraph(edges=[upstream, down1, down2])

    action = DissolveRerouteAction(graph=graph, node_id="reroute_1")

    kinds = [type(a) for a in action.actions]
    assert kinds == [RemoveElementsAction, AddEdgeAction, AddEdgeAction]

    remove = action.actions[0]
    assert remove.nodes == ["reroute_1"]

    sinks = {a.sink_node_id for a in action.actions[1:]}
    assert sinks == {"B", "C"}
    for bridge in action.actions[1:]:
        assert bridge.source_node_id == "A"
        assert bridge.outlet_pin_id == "result"


def test_dissolve_control_fan_in_bridges_all_upstreams():
    """CONTROL reroute with 2 upstreams + 1 downstream → Remove + 2 AddEdgeActions."""
    from haywire.core.undo.actions.graph_actions import (
        DissolveRerouteAction,
        RemoveElementsAction,
        AddEdgeAction,
    )

    up1 = _make_edge("A", "exec", "reroute_1", "in", "e_up1")
    up2 = _make_edge("B", "exec", "reroute_1", "in", "e_up2")
    downstream = _make_edge("reroute_1", "out", "C", "exec", "e_down")
    graph = _FakeGraph(edges=[up1, up2, downstream])

    action = DissolveRerouteAction(graph=graph, node_id="reroute_1")

    kinds = [type(a) for a in action.actions]
    assert kinds == [RemoveElementsAction, AddEdgeAction, AddEdgeAction]

    sources = {a.source_node_id for a in action.actions[1:]}
    assert sources == {"A", "B"}
    for bridge in action.actions[1:]:
        assert bridge.sink_node_id == "C"
        assert bridge.inlet_pin_id == "exec"


def test_dissolve_no_upstream_skips_bridges():
    """No upstream edge → only RemoveElementsAction, no AddEdgeAction."""
    from haywire.core.undo.actions.graph_actions import (
        DissolveRerouteAction,
        RemoveElementsAction,
        AddEdgeAction,
    )

    downstream = _make_edge("reroute_1", "out", "B", "value_a", "e_down")
    graph = _FakeGraph(edges=[downstream])

    action = DissolveRerouteAction(graph=graph, node_id="reroute_1")

    kinds = [type(a) for a in action.actions]
    assert AddEdgeAction not in kinds
    assert any(a is RemoveElementsAction for a in kinds)


def test_dissolve_no_downstream_skips_bridges():
    """No downstream edge → only RemoveElementsAction, no AddEdgeAction."""
    from haywire.core.undo.actions.graph_actions import (
        DissolveRerouteAction,
        RemoveElementsAction,
        AddEdgeAction,
    )

    upstream = _make_edge("A", "result", "reroute_1", "in", "e_up")
    graph = _FakeGraph(edges=[upstream])

    action = DissolveRerouteAction(graph=graph, node_id="reroute_1")

    kinds = [type(a) for a in action.actions]
    assert AddEdgeAction not in kinds
    assert any(a is RemoveElementsAction for a in kinds)


def test_dissolve_no_edges_only_removes_node():
    """No edges at all → only RemoveElementsAction."""
    from haywire.core.undo.actions.graph_actions import (
        DissolveRerouteAction,
        RemoveElementsAction,
    )

    graph = _FakeGraph(edges=[])

    action = DissolveRerouteAction(graph=graph, node_id="reroute_1")

    kinds = [type(a) for a in action.actions]
    assert kinds == [RemoveElementsAction]


def test_dissolve_raises_on_missing_node():
    """Raises ValueError if the node_id doesn't exist in the graph."""
    from haywire.core.undo.actions.graph_actions import DissolveRerouteAction

    graph = _FakeGraph(node_id="exists", edges=[])

    with pytest.raises(ValueError, match="not found"):
        DissolveRerouteAction(graph=graph, node_id="does_not_exist")


def test_editor_dissolve_returns_true_on_success(monkeypatch):
    from haywire.core.graph.editor import Editor

    added = {}

    class _HM:
        def add_action(self, action):
            added["action"] = action

    class _FakeAction:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr("haywire.core.graph.editor.DissolveRerouteAction", _FakeAction)

    ed = Editor.__new__(Editor)
    ed.graph = object()
    ed.history_manager = _HM()

    result = ed.dissolve_reroute("reroute_1")

    assert result is True
    assert isinstance(added["action"], _FakeAction)


def test_editor_dissolve_returns_false_on_error(monkeypatch):
    from haywire.core.graph.editor import Editor

    class _HM:
        def add_action(self, action):
            raise RuntimeError("boom")

    class _FakeAction:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr("haywire.core.graph.editor.DissolveRerouteAction", _FakeAction)

    ed = Editor.__new__(Editor)
    ed.graph = object()
    ed.history_manager = _HM()

    assert ed.dissolve_reroute("reroute_1") is False


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDissolveRerouteIntegration:
    """Execute a real dissolve against a live graph with real nodes/edges/types."""

    def _reroute_args(self):
        from haybale_core.nodes.reroute import RerouteNode

        return dict(registry_key=RerouteNode.class_identity.registry_key)

    def _split_graph(self, graph):
        """Create A → reroute → B and return (node_a, node_b, reroute_id, original_edge_id)."""
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
        from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

        key = TestAddFloatNode.class_identity.registry_key
        node_a = graph.create_node_wrapper(key, position=(100, 100))
        node_b = graph.create_node_wrapper(key, position=(400, 100))
        edge = graph.create_edge_wrapper(node_a.node_id, "result", node_b.node_id, "value_a")
        original_edge_id = edge.edge_id

        action = SplitEdgeWithRerouteAction(
            graph=graph,
            edge_id=edge.edge_id,
            position=(250.0, 100.0),
            **self._reroute_args(),
        )
        action._execute_impl()

        new_ids = set(graph.node_wrappers.keys()) - {node_a.node_id, node_b.node_id}
        reroute_id = next(iter(new_ids))
        return node_a, node_b, reroute_id, original_edge_id

    def test_dissolve_restores_direct_edge(self, graph_with_library_system, library_system):
        from haywire.core.undo.actions.graph_actions import DissolveRerouteAction

        graph = graph_with_library_system
        node_a, node_b, reroute_id, _ = self._split_graph(graph)
        original_ids = {node_a.node_id, node_b.node_id}

        action = DissolveRerouteAction(graph=graph, node_id=reroute_id)
        action._execute_impl()

        # Reroute node is gone.
        assert graph.get_node_wrapper(reroute_id) is None
        assert set(graph.node_wrappers.keys()) == original_ids

        # Exactly one edge: A.result → B.value_a.
        edges = list(graph.edge_wrappers.values())
        assert len(edges) == 1
        e = edges[0]
        assert e.source_node_id == node_a.node_id
        assert e.sink_node_id == node_b.node_id
        assert e.state.is_valid()

    def test_dissolve_undo_restores_reroute(self, graph_with_library_system, library_system):
        from haywire.core.undo.actions.graph_actions import DissolveRerouteAction

        graph = graph_with_library_system
        node_a, node_b, reroute_id, _ = self._split_graph(graph)
        snapshot_edges = set(graph.edge_wrappers.keys())
        snapshot_nodes = set(graph.node_wrappers.keys())

        action = DissolveRerouteAction(graph=graph, node_id=reroute_id)
        action._execute_impl()
        action._undo_impl()

        # Back to reroute + 2 edges.
        assert set(graph.node_wrappers.keys()) == snapshot_nodes
        assert set(graph.edge_wrappers.keys()) == snapshot_edges
        assert all(e.state.is_valid() for e in graph.edge_wrappers.values())
