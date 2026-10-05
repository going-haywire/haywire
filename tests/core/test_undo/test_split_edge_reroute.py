"""Tests for splitting a data edge with a reroute node.

Covers the SplitEdgeWithRerouteAction composite (child structure + real
execution against a live graph) and the editor entry point.
"""

from typing import Any, cast

import pytest

from haywire.core.graph.base import BaseGraph

pytestmark = pytest.mark.unit


# The reroute node ships in the framework-owned builtin library; the split
# action owns the port ids.
_RR_KEY = "haywire-core:node:RerouteNode"
_RR_IN = "in"
_RR_OUT = "out"


def _build_split_action(graph, **overrides):
    from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

    kwargs = dict(
        graph=graph,
        edge_id="e0",
        position=(50.0, 60.0),
        registry_key=_RR_KEY,
    )
    kwargs.update(overrides)
    return SplitEdgeWithRerouteAction(**kwargs)


def test_split_action_resolves_outlet_type_and_builds_children():
    """Construction resolves the outlet IType and builds the 5 child actions in
    order: remove edge -> add node -> add ports -> two add-edges."""
    from haywire.core.undo.actions.graph_actions import (
        RemoveElementsAction,
        AddNodeAction,
        AddEdgeAction,
        _AddReroutePortsAction,
    )

    sentinel_type = object()

    class _Port:
        stored_type = sentinel_type

    class _Node:
        ports = {"result": _Port()}

    class _NodeWrapper:
        node = _Node()

    class _Edge:
        source_node_id = "A"
        outlet_port_id = "result"
        sink_node_id = "B"
        inlet_port_id = "value_a"

    class _G:
        def get_edge_wrapper(self, edge_id):
            return _Edge()

        def get_node_wrapper(self, node_id):
            return _NodeWrapper()

        def generate_unique_node_id(self, registry_key="node"):
            return "reroute_1"

    action = _build_split_action(_G())

    assert action.reroute_node_id == "reroute_1"
    kinds = [type(a) for a in action.actions]
    assert kinds == [
        RemoveElementsAction,
        AddNodeAction,
        _AddReroutePortsAction,
        AddEdgeAction,
        AddEdgeAction,
    ]

    remove, add_node, addports, edge_in, edge_out = action.actions
    assert remove.edges == ["e0"]
    assert add_node.node_id == "reroute_1"
    # Registry key comes from the caller — NOT hardcoded in core.
    assert add_node.registry_key == _RR_KEY
    assert add_node.position == (50.0, 60.0)
    # Reroute typed to the OUTLET's concrete type (Q2/2A); ids threaded through.
    assert addports.itype is sentinel_type
    assert (addports.inlet_id, addports.outlet_id) == (_RR_IN, _RR_OUT)
    # The inlet forwards immediate (callback) values through the reroute's handler.
    assert addports.inlet_on_change == "forward_immediate"
    # First edge: A.out -> reroute.in ; second: reroute.out -> B.in
    assert (edge_in.source_node_id, edge_in.outlet_port_id) == ("A", "result")
    assert (edge_in.sink_node_id, edge_in.inlet_port_id) == ("reroute_1", _RR_IN)
    assert (edge_out.source_node_id, edge_out.outlet_port_id) == ("reroute_1", _RR_OUT)
    assert (edge_out.sink_node_id, edge_out.inlet_port_id) == ("B", "value_a")


def test_split_action_raises_on_missing_edge():
    g = BaseGraph(filestem="G")
    with pytest.raises(ValueError, match="not found"):
        _build_split_action(g, edge_id="nope")


def test_add_ports_action_rejigs_to_new_type():
    from haywire.core.undo.actions.graph_actions import _AddReroutePortsAction

    calls: dict = {"rejig_include": None, "added": []}

    class _Spec:
        def __init__(self, kind, id):
            self.kind = kind
            self.id = id

    class _Type:
        @staticmethod
        def as_inlet(id, label="", **kwargs):
            return _Spec("inlet", id)

        @staticmethod
        def as_outlet(id, label=""):
            return _Spec("outlet", id)

    class _Rejig:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Node:
        def rejig(self, include=None, exclude=None):
            calls["rejig_include"] = include
            return _Rejig()

        def add(self, spec):
            calls["added"].append((spec.kind, spec.id))

    class _G:
        def get_node_wrapper(self, node_id):
            return type("W", (), {"node": _Node()})()

    action = _AddReroutePortsAction(
        graph=cast(Any, _G)(), node_id="r", itype=_Type, inlet_id="in", outlet_id="out"
    )
    action._execute_impl()
    assert calls["rejig_include"] == ["in", "out"]
    assert calls["added"] == [("inlet", "in"), ("outlet", "out")]
    # Undo is a no-op (node removal handles teardown).
    action._undo_impl()


def test_add_ports_action_raises_on_missing_node():
    from haywire.core.undo.actions.graph_actions import _AddReroutePortsAction

    class _G:
        def get_node_wrapper(self, node_id):
            return None

    action = _AddReroutePortsAction(
        graph=cast(Any, _G)(), node_id="r", itype=object(), inlet_id="in", outlet_id="out"
    )
    with pytest.raises(RuntimeError, match="not found"):
        action._execute_impl()


def test_editor_split_returns_reroute_id(monkeypatch):
    from haywire.core.graph import editor as editor_module
    from haywire.core.graph.editor import Editor

    added = {}

    class _HM:
        def add_action(self, action):
            added["action"] = action

    class _FakeAction:
        reroute_node_id = "reroute_x"

        def __init__(self, *a, **k):
            pass

    # editor.py imports the action by name, so patch it on that module.
    monkeypatch.setattr(editor_module, "SplitEdgeWithRerouteAction", _FakeAction)

    ed = Editor.__new__(Editor)
    ed.graph = cast(Any, object())
    ed.history_manager = cast(Any, _HM())

    result = ed.split_edge_with_reroute("e0", (1.0, 2.0), registry_key=_RR_KEY)

    assert result == "reroute_x"
    assert isinstance(added["action"], _FakeAction)


def test_editor_split_returns_none_on_error():
    from haywire.core.graph.editor import Editor

    class _HM:
        def add_action(self, action):
            raise RuntimeError("boom")

    ed = Editor.__new__(Editor)
    ed.graph = BaseGraph(filestem="G")
    ed.history_manager = cast(Any, _HM())
    # Unknown edge -> action ctor raises inside the try -> None.
    assert ed.split_edge_with_reroute("nope", (0.0, 0.0), registry_key=_RR_KEY) is None


def _reroute_validator_with_ports(ports):
    """Build a StructuralValidator + a fake REROUTE wrapper holding `ports`.

    Each port is (port_type, wire_type, has_pin).
    """
    from haywire.barn.builtin import wires
    from haywire.core.validation.structural_validator import StructuralValidator
    from haywire.core.node.behavior import NodeBehaviorFlags, NodeType
    from haywire.core.types.enums import PortType

    class _Port:
        def __init__(self, port_type, wire_type, has_pin):
            self.id = f"{port_type}-{wire_type.id}"
            self.port_type = port_type
            self.wire_key = wire_type.id
            self.widget_key = None
            self._has_pin = has_pin

        def has_pin(self):
            return self._has_pin

    port_objs = [_Port(pt, wt, hp) for (pt, wt, hp) in ports]

    class _Node:
        behavior = NodeBehaviorFlags(node_type=NodeType.REROUTE)

        def __init__(self):
            self.ports = {p.id: p for p in port_objs}

        def get_ports(self, is_port_type=None, has_pin=None, **_filters):
            return [
                p
                for p in self.ports.values()
                if (is_port_type is None or is_port_type == p.port_type)
                and (has_pin is None or has_pin == p.has_pin())
            ]

    class _Wrapper:
        node = _Node()

    validator = StructuralValidator.__new__(StructuralValidator)
    return validator, _Wrapper(), wires, PortType


def test_validate_reroute_portless_latent_state_is_valid():
    validator, wrapper, _W, _P = _reroute_validator_with_ports([])
    ok, err, _ = validator.validate_node(wrapper)
    assert ok
    assert err is None


def test_validate_reroute_configured_pair_is_valid():
    _, _, wires, PortType = _reroute_validator_with_ports([])
    validator, wrapper, *_ = _reroute_validator_with_ports(
        [
            (PortType.INLET, wires.DataWire, True),
            (PortType.OUTLET, wires.DataWire, True),
        ]
    )
    ok, err, _ = validator.validate_node(wrapper)
    assert ok
    assert err is None


def test_validate_reroute_outlet_only_is_invalid():
    _, _, wires, PortType = _reroute_validator_with_ports([])
    validator, wrapper, *_ = _reroute_validator_with_ports([(PortType.OUTLET, wires.DataWire, True)])
    ok, err, _ = validator.validate_node(wrapper)
    assert not ok
    assert "exactly one inlet and one outlet" in err


def test_validate_reroute_accepts_control_passthrough_pair():
    """A CONTROL inlet + CONTROL outlet is a valid configured reroute."""
    _, _, wires, PortType = _reroute_validator_with_ports([])
    validator, wrapper, *_ = _reroute_validator_with_ports(
        [
            (PortType.INLET, wires.ControlWire, True),
            (PortType.OUTLET, wires.ControlWire, True),
        ]
    )
    ok, err, _ = validator.validate_node(wrapper)
    assert ok
    assert err is None


def test_validate_reroute_accepts_callback_passthrough_pair():
    """A CALLBACK inlet + CALLBACK outlet is a valid configured reroute."""
    _, _, wires, PortType = _reroute_validator_with_ports([])
    validator, wrapper, *_ = _reroute_validator_with_ports(
        [
            (PortType.INLET, wires.CallbackWire, True),
            (PortType.OUTLET, wires.CallbackWire, True),
        ]
    )
    ok, err, _ = validator.validate_node(wrapper)
    assert ok
    assert err is None


def test_validate_reroute_rejects_mixed_wire_types():
    """An inlet and outlet on different wire types is invalid."""
    _, _, wires, PortType = _reroute_validator_with_ports([])
    validator, wrapper, *_ = _reroute_validator_with_ports(
        [
            (PortType.INLET, wires.DataWire, True),
            (PortType.OUTLET, wires.ControlWire, True),
        ]
    )
    ok, err, _ = validator.validate_node(wrapper)
    assert not ok


def test_reroute_node_type_is_standalone_bit():
    """REROUTE is a standalone bit — not DATA, not CONTROL."""
    from haywire.core.node.behavior import NodeBehaviorFlags, NodeType

    flags = NodeBehaviorFlags(node_type=NodeType.REROUTE)
    assert flags.is_reroute_node is True
    assert flags.is_data_node is False
    assert flags.is_control_node is False


@pytest.mark.integration
class TestSplitEdgeRerouteIntegration:
    """Execute a real split against a live graph with real nodes/edges/types."""

    def _two_connected_nodes(self, graph):
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        key = TestAddFloatNode.class_identity.registry_key
        node_a = graph.create_node_wrapper(key, position=(100, 100))
        node_b = graph.create_node_wrapper(key, position=(300, 100))
        edge = graph.create_edge_wrapper(node_a.node_id, "result", node_b.node_id, "value_a")
        assert edge.state.is_valid()
        return node_a, node_b, edge

    def _reroute_args(self):
        """The split action owns the port ids now; only the registry key remains."""
        from haywire.barn.builtin.nodes.reroute import RerouteNode

        return dict(registry_key=RerouteNode.class_identity.registry_key)

    def test_split_inserts_typed_reroute_and_two_valid_edges(
        self, graph_with_library_system, library_system
    ):
        from haywire.barn.builtin.nodes.reroute import RerouteNode
        from haywire.barn.builtin.types import FLOAT
        from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

        graph = graph_with_library_system
        node_a, node_b, edge = self._two_connected_nodes(graph)
        original_ids = {node_a.node_id, node_b.node_id}
        original_edge_id = edge.edge_id

        action = SplitEdgeWithRerouteAction(
            graph=cast(Any, graph), edge_id=edge.edge_id, position=(200.0, 200.0), **self._reroute_args()
        )
        action._execute_impl()

        # Original edge is gone.
        assert graph.get_edge_wrapper(original_edge_id) is None

        # Exactly one new node — the reroute — exists.
        new_ids = set(graph.node_wrappers.keys()) - original_ids
        assert len(new_ids) == 1
        reroute_id = next(iter(new_ids))
        assert reroute_id == action.reroute_node_id

        # Reroute has exactly the typed in/out ports, matching the outlet (FLOAT).
        reroute = graph.node_wrappers[reroute_id].node
        # An unknown registry key yields the error node, which accepts the same ports.
        assert isinstance(reroute, RerouteNode)
        assert set(reroute.ports.keys()) == {"in", "out"}
        assert reroute.ports["in"].stored_type is FLOAT
        assert reroute.ports["out"].stored_type is FLOAT

        # Two valid edges: A.result -> reroute.in and reroute.out -> B.value_a.
        edges = list(graph.edge_wrappers.values())
        assert len(edges) == 2
        assert all(e.state.is_valid() for e in edges)
        pairs = {(e.source_node_id, e.sink_node_id) for e in edges}
        assert pairs == {(node_a.node_id, reroute_id), (reroute_id, node_b.node_id)}

    def test_split_control_edge_inserts_reroute(self, graph_with_library_system, library_system):
        """Splitting a CONTROL edge inserts a reroute with EXEC inlet/outlet."""
        from haywire.barn.builtin.types import EXEC
        from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction
        from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        graph = graph_with_library_system

        begin_key = TestBeginPlayNode.class_identity.registry_key
        print_key = TestPrintNode.class_identity.registry_key

        begin = graph.create_node_wrapper(begin_key, position=(100, 100))
        print_node = graph.create_node_wrapper(print_key, position=(300, 100))
        edge = graph.create_edge_wrapper(begin.node_id, "exec", print_node.node_id, "exec")
        assert edge.state.is_valid()
        from haywire.barn.builtin.wires import ControlWire

        assert edge.wire_type.id == ControlWire.id

        original_ids = {begin.node_id, print_node.node_id}
        original_edge_id = edge.edge_id

        action = SplitEdgeWithRerouteAction(
            graph=cast(Any, graph),
            edge_id=edge.edge_id,
            position=(200.0, 200.0),
            **self._reroute_args(),
        )
        action._execute_impl()

        # Original edge is gone.
        assert graph.get_edge_wrapper(original_edge_id) is None

        # Exactly one new node — the reroute.
        new_ids = set(graph.node_wrappers.keys()) - original_ids
        assert len(new_ids) == 1
        reroute_id = next(iter(new_ids))

        # Reroute has EXEC-typed ports.
        reroute = graph.node_wrappers[reroute_id].node
        assert set(reroute.ports.keys()) == {"in", "out"}
        assert reroute.ports["in"].stored_type is EXEC
        assert reroute.ports["out"].stored_type is EXEC
        assert reroute.ports["in"].wire_type.id == ControlWire.id
        assert reroute.ports["out"].wire_type.id == ControlWire.id

        # Two valid edges.
        edges = list(graph.edge_wrappers.values())
        assert len(edges) == 2
        assert all(e.state.is_valid() for e in edges)
        pairs = {(e.source_node_id, e.sink_node_id) for e in edges}
        assert pairs == {(begin.node_id, reroute_id), (reroute_id, print_node.node_id)}

    def test_a_data_reroute_still_forwards_only_when_it_runs(
        self, graph_with_library_system, library_system
    ):
        """The inlet's on_change handler forwards immediate values only; DATA waits for the worker."""
        from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

        graph = graph_with_library_system
        node_a, node_b, edge = self._two_connected_nodes(graph)
        action = SplitEdgeWithRerouteAction(
            graph=cast(Any, graph), edge_id=edge.edge_id, position=(200.0, 200.0), **self._reroute_args()
        )
        action._execute_impl()
        reroute = graph.node_wrappers[action.reroute_node_id].node
        sink = node_b.node.ports["value_a"]

        node_a.node.out("result", 42.0)
        reroute.ports["in"].resolve_dirty_data()  # fires the deferred on_change

        assert reroute.ports["in"].get_value() == 42.0
        assert sink.get_value() != 42.0

    def test_split_undo_restores_original_edge(self, graph_with_library_system, library_system):
        from haywire.core.undo.actions.graph_actions import SplitEdgeWithRerouteAction

        graph = graph_with_library_system
        node_a, node_b, edge = self._two_connected_nodes(graph)
        original_ids = {node_a.node_id, node_b.node_id}
        original_edge_id = edge.edge_id

        action = SplitEdgeWithRerouteAction(
            graph=cast(Any, graph), edge_id=edge.edge_id, position=(200.0, 200.0), **self._reroute_args()
        )
        action._execute_impl()
        action._undo_impl()

        # Back to exactly the two original nodes and the one original edge.
        assert set(graph.node_wrappers.keys()) == original_ids
        restored = graph.get_edge_wrapper(original_edge_id)
        assert restored is not None
        assert restored.state.is_valid()
