"""The structural validator ignores VISUAL pins, except on a reroute."""

import pytest

from haywire.core.types.enums import PortType
from haywire.core.types.wire import WireRole

pytestmark = pytest.mark.unit


class _Port:
    def __init__(self, port_id, port_type, role):
        self.id = port_id
        self.port_type = port_type
        self._role = role
        self.wire_key = f"lib:wire:{role.name}"
        self.is_dependent = role is WireRole.DEPENDENT

    def has_pin(self):
        return True

    def has_role(self, role):
        return self._role is role


class _Node:
    def __init__(self, node_type, ports, subscription=None):
        from haywire.core.node.behavior import NodeBehaviorFlags

        self.behavior = NodeBehaviorFlags(node_type=node_type)
        self.ports = {p.id: p for p in ports}
        self.event_subscription = subscription
        self.identity = type(
            "_Identity",
            (),
            {"_is_subgraph_input": True, "_is_subgraph_output": False, "_is_graph_node": False},
        )()

    def get_ports(self, is_port_type=None, has_pin=None, is_role=None, is_not_role=None, **_):
        return [
            p
            for p in self.ports.values()
            if (is_port_type is None or p.port_type == is_port_type)
            and (is_role is None or p.has_role(is_role))
            and (is_not_role is None or not p.has_role(is_not_role))
        ]


def _validate(node):
    from haywire.core.validation.structural_validator import StructuralValidator

    validator = StructuralValidator.__new__(StructuralValidator)
    wrapper = type("_Wrapper", (), {"node": node, "graph": None})()
    return validator.validate_node(wrapper)


def test_an_event_node_may_carry_a_visual_inlet():
    from haywire.core.node.behavior import NodeType

    node = _Node(
        NodeType.EVENT,
        [_Port("note", PortType.INLET, WireRole.VISUAL), _Port("exec", PortType.OUTLET, WireRole.SEQUENCE)],
        subscription=object(),
    )
    assert _validate(node)[0]


def test_a_data_node_may_carry_visual_pins():
    from haywire.core.node.behavior import NodeType

    node = _Node(
        NodeType.DATA,
        [
            _Port("note", PortType.INLET, WireRole.VISUAL),
            _Port("value", PortType.OUTLET, WireRole.DEPENDENT),
        ],
    )
    assert _validate(node)[0]


def test_a_boundary_node_ignores_a_visual_pin_against_its_direction():
    from haywire.core.node.behavior import NodeType

    node = _Node(
        NodeType.BOUNDARY,
        [_Port("note", PortType.INLET, WireRole.VISUAL), _Port("out", PortType.OUTLET, WireRole.DEPENDENT)],
    )
    assert _validate(node)[0]
