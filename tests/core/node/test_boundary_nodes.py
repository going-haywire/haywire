"""Boundary nodes: registration, the registry's two slots, and the validator rules."""

from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph

pytestmark = pytest.mark.unit


def _fresh_registry():
    from haywire.core.node.registry import NodeRegistry

    return NodeRegistry()


class _FakeBehavior:
    def __init__(self, node_type):
        self.node_type = node_type


class _FakeNode:
    """Minimal stand-in for a BaseNode, exposing what the validator reads."""

    def __init__(self, identity, node_type, ports=()):
        self.identity = identity
        self._ports = list(ports)
        self.behavior = _FakeBehavior(node_type)
        self.event_subscription = None

    def get_ports(self, is_port_type=None, has_pin=None, is_flow_type=None, **kw):
        from haywire.core.types.enums import PortType

        out = self._ports
        if is_port_type is PortType.INLET:
            out = [p for p in out if p.port_type is PortType.INLET]
        elif is_port_type is PortType.OUTLET:
            out = [p for p in out if p.port_type is PortType.OUTLET]
        return list(out)


class _FakeWrapper:
    def __init__(self, node, node_id="n1"):
        self.node = node
        self.node_id = node_id


class _FakePort:
    def __init__(self, pid, port_type, needs_loopback=False):
        self.id = pid
        self.port_type = port_type
        self.needs_loopback = needs_loopback


def _identity(label="Fake", **flags):
    from haywire.core.node.identity import NodeIdentity

    return NodeIdentity(registry_id=label, registry_key=f"t:node:{label}", label=label, **flags)


def _validator():
    from haywire.core.validation.structural_validator import StructuralValidator

    # The node-level and subgraph-contents rules read only what they are handed.
    return StructuralValidator(graph=cast("BaseGraph", None))


# ---------------------------------------------------------------------------
# NodeType.BOUNDARY
# ---------------------------------------------------------------------------


def test_boundary_carries_neither_data_nor_control_bit():
    from haywire.core.node import NodeType

    assert NodeType.BOUNDARY & NodeType.CONTROL == 0
    assert NodeType.BOUNDARY & NodeType.DATA == 0


def test_behavior_exposes_is_boundary_node():
    from haywire.core.node import NodeType
    from haywire.core.node.behavior import NodeBehaviorFlags

    assert NodeBehaviorFlags(node_type=NodeType.BOUNDARY).is_boundary_node is True
    assert NodeBehaviorFlags(node_type=NodeType.DATA).is_boundary_node is False


# ---------------------------------------------------------------------------
# The two classes
# ---------------------------------------------------------------------------


def test_both_classes_are_boundary_typed_and_flagged():
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode
    from haywire.core.node import NodeType

    assert NodeType.BOUNDARY in SubgraphInputNode.class_behavior.node_type
    assert NodeType.BOUNDARY in SubgraphOutputNode.class_behavior.node_type
    assert SubgraphInputNode.class_identity._is_subgraph_input is True
    assert SubgraphInputNode.class_identity._is_subgraph_output is False
    assert SubgraphOutputNode.class_identity._is_subgraph_output is True
    assert SubgraphOutputNode.class_identity._is_subgraph_input is False


def test_both_classes_are_hidden_from_the_add_node_menu():
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    reg = _fresh_registry()
    in_key = reg._register_class(SubgraphInputNode)
    out_key = reg._register_class(SubgraphOutputNode)

    assert reg.get(in_key) is SubgraphInputNode
    assert reg.get(out_key) is SubgraphOutputNode
    assert in_key not in reg.list_visible_names()
    assert out_key not in reg.list_visible_names()


def test_both_classes_bind_the_boundary_skin_by_key_string():
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    for cls in (SubgraphInputNode, SubgraphOutputNode):
        descriptor = cls.props._settings_descriptors()["skin"]
        assert descriptor._default == "haywire-core:skin:SubgraphIOSkin"


def test_module_does_not_import_the_skin_class():
    """The boundary nodes bind their skin by key string, never by import.

    Importing it would pull haywire.ui onto the headless execution path.
    """
    import ast
    import inspect

    import haywire.barn.builtin.nodes.subgraph_io as mod

    imported: list[str] = []
    for stmt in ast.walk(ast.parse(inspect.getsource(mod))):
        if isinstance(stmt, ast.Import):
            imported.extend(alias.name for alias in stmt.names)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module:
            imported.append(stmt.module)

    assert imported, "no imports parsed — the guard would pass vacuously"
    assert not [name for name in imported if "skin" in name or name.startswith("nicegui")]
    assert not hasattr(mod, "SubgraphIOSkin")


# ---------------------------------------------------------------------------
# Registry slots
# ---------------------------------------------------------------------------


def test_registry_tracks_both_boundary_slots():
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    reg = _fresh_registry()
    assert reg._get_subgraph_input_node() is None
    assert reg._get_subgraph_output_node() is None

    reg._register_class(SubgraphInputNode)
    reg._register_class(SubgraphOutputNode)

    assert reg._get_subgraph_input_node() is SubgraphInputNode
    assert reg._get_subgraph_output_node() is SubgraphOutputNode


def test_registry_clears_boundary_slots_on_unregister():
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    reg = _fresh_registry()
    in_key = reg._register_class(SubgraphInputNode)
    out_key = reg._register_class(SubgraphOutputNode)

    reg._unregister_class(in_key)
    assert reg._get_subgraph_input_node() is None
    assert reg._get_subgraph_output_node() is SubgraphOutputNode

    reg._unregister_class(out_key)
    assert reg._get_subgraph_output_node() is None


def test_factory_exposes_both_boundary_nodes():
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode
    from haywire.core.node.factory import NodeFactory

    reg = _fresh_registry()
    factory = NodeFactory(reg)
    assert factory.get_subgraph_input_node() is None
    assert factory.get_subgraph_output_node() is None

    reg._register_class(SubgraphInputNode)
    reg._register_class(SubgraphOutputNode)

    assert factory.get_subgraph_input_node() is SubgraphInputNode
    assert factory.get_subgraph_output_node() is SubgraphOutputNode


# ---------------------------------------------------------------------------
# _validate_boundary_node
# ---------------------------------------------------------------------------


def test_port_less_boundary_node_is_valid():
    from haywire.core.node import NodeType

    node = _FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY)
    ok, err, _ = _validator().validate_node(_FakeWrapper(node))
    assert ok is True
    assert err is None


def test_subgraph_input_with_an_inlet_fails_with_a_named_reason():
    from haywire.core.node import NodeType
    from haywire.core.types.enums import PortType

    ports = [_FakePort("value", PortType.INLET), _FakePort("out", PortType.OUTLET)]
    node = _FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY, ports)
    ok, err, suggestions = _validator().validate_node(_FakeWrapper(node))
    assert ok is False
    assert "only outlets" in err
    assert "value" in err
    assert suggestions


def test_subgraph_output_with_an_outlet_fails_with_a_named_reason():
    from haywire.core.node import NodeType
    from haywire.core.types.enums import PortType

    ports = [_FakePort("result", PortType.OUTLET), _FakePort("in", PortType.INLET)]
    node = _FakeNode(_identity(_is_subgraph_output=True), NodeType.BOUNDARY, ports)
    ok, err, suggestions = _validator().validate_node(_FakeWrapper(node))
    assert ok is False
    assert "only inlets" in err
    assert "result" in err
    assert suggestions


def test_single_direction_boundary_node_is_valid():
    from haywire.core.node import NodeType
    from haywire.core.types.enums import PortType

    ports = [_FakePort("a", PortType.OUTLET), _FakePort("b", PortType.OUTLET)]
    node = _FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY, ports)
    ok, err, _ = _validator().validate_node(_FakeWrapper(node))
    assert ok is True
    assert err is None


def test_a_loopback_outlet_may_cross_the_boundary():
    """Under inlining the loopback stack is one list spanning host and Subgraph."""
    from haywire.core.node import NodeType
    from haywire.core.types.enums import PortType

    ports = [_FakePort("body", PortType.OUTLET, needs_loopback=True)]
    node = _FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY, ports)
    ok, err, _ = _validator().validate_node(_FakeWrapper(node))
    assert ok is True
    assert err is None


# ---------------------------------------------------------------------------
# validate_subgraph_contents
# ---------------------------------------------------------------------------


def _boundary_pair():
    from haywire.core.node import NodeType

    return [
        _FakeWrapper(_FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY), "in"),
        _FakeWrapper(_FakeNode(_identity(_is_subgraph_output=True), NodeType.BOUNDARY), "out"),
    ]


def test_a_subgraph_with_exactly_one_boundary_pair_is_valid():
    from haywire.core.node import NodeType

    wrappers = _boundary_pair()
    wrappers.append(_FakeWrapper(_FakeNode(_identity(label="Add"), NodeType.DATA), "add"))
    ok, err, _ = _validator().validate_subgraph_contents(wrappers)
    assert ok is True
    assert err is None


def test_a_subgraph_with_two_inputs_fails():
    from haywire.core.node import NodeType

    wrappers = _boundary_pair()
    wrappers.append(_FakeWrapper(_FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY), "in2"))
    ok, err, _ = _validator().validate_subgraph_contents(wrappers)
    assert ok is False
    assert "exactly one" in err


def test_a_subgraph_missing_its_output_fails():
    from haywire.core.node import NodeType

    wrappers = [
        _FakeWrapper(_FakeNode(_identity(_is_subgraph_input=True), NodeType.BOUNDARY), "in"),
    ]
    ok, err, _ = _validator().validate_subgraph_contents(wrappers)
    assert ok is False
    assert "exactly one" in err


def test_a_subgraph_containing_an_event_node_fails():
    from haywire.core.node import NodeType

    wrappers = _boundary_pair()
    wrappers.append(_FakeWrapper(_FakeNode(_identity(label="Begin Play"), NodeType.EVENT), "ev"))
    ok, err, suggestions = _validator().validate_subgraph_contents(wrappers)
    assert ok is False
    assert "EVENT or OUTPUT" in err
    assert "Begin Play" in err
    assert suggestions


def test_a_subgraph_containing_an_output_node_fails():
    from haywire.core.node import NodeType

    wrappers = _boundary_pair()
    wrappers.append(_FakeWrapper(_FakeNode(_identity(label="Shutdown"), NodeType.OUTPUT), "sd"))
    ok, err, _ = _validator().validate_subgraph_contents(wrappers)
    assert ok is False
    assert "EVENT or OUTPUT" in err
    assert "Shutdown" in err
