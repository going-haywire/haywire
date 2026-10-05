"""Types declare a wire type, and every port derives its own from its type."""

import pytest

from haywire.core.types import PortType, WireRole
from haywire.core.types.wire import WILDCARD

from tests.conftest import make_node


def _id(wire) -> str:
    assert wire is not None
    return wire.id


@pytest.mark.unit
class TestBuiltinWireTypes:
    def test_ids(self):
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert DataWire.id == "haywire-core:wire:DataWire"
        assert ControlWire.id == "haywire-core:wire:ControlWire"
        assert CallbackWire.id == "haywire-core:wire:CallbackWire"

    def test_roles_and_pin_kinds(self):
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert (DataWire.role, DataWire.pin_kind) == (WireRole.DEPENDENT, "data")
        assert (ControlWire.role, ControlWire.pin_kind) == (WireRole.SEQUENCE, "control")
        assert (CallbackWire.role, CallbackWire.pin_kind) == (WireRole.IMMEDIATE, "callback")


@pytest.mark.unit
class TestTypesDeclare:
    def test_each_builtin_signal_type_names_its_wire_type(self):
        from haywire.barn.builtin.types import CALLBACK, EXEC, FLOAT
        from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire

        assert _id(FLOAT.class_identity.wire_type) == DataWire.id
        assert _id(EXEC.class_identity.wire_type) == ControlWire.id
        assert _id(CALLBACK.class_identity.wire_type) == CallbackWire.id

    def test_a_derived_type_inherits_its_parents_wire_type(self):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.wires import DataWire
        from haywire.core.types import type as haywire_type

        @haywire_type(label="Derived")
        class Derived(FLOAT):
            """A FLOAT variant."""

        assert _id(Derived.class_identity.wire_type) == DataWire.id

    def test_a_port_spec_carries_no_wire_type(self):
        from haywire.barn.builtin.types import FLOAT

        assert "wire_type" not in FLOAT.as_inlet("x")["kwargs"]

    def test_a_port_spec_refuses_a_wire_type_kwarg(self):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.wires import DataWire

        with pytest.raises(TypeError, match="takes its wire type from its type"):
            FLOAT.as_inlet("x", wire_type=DataWire)


@pytest.mark.integration
class TestPortsDerive:
    def test_a_data_inlet(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

        from haywire.barn.builtin.wires import DataWire

        node = make_node(graph_with_library_system, TestAddFloatNode.class_identity.registry_key).node
        port = node.ports["value_a"]

        assert _id(port.wire_type) == DataWire.id
        assert port.wire_key == DataWire.id
        assert port.has_role(WireRole.DEPENDENT)
        assert port.is_dependent

    def test_a_pooled_callback_inlet_takes_its_elements(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

        from haywire.barn.builtin.wires import CallbackWire, ControlWire

        node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node

        assert _id(node.ports["edge_callback"].wire_type) == CallbackWire.id
        assert _id(node.ports["exec"].wire_type) == ControlWire.id
        assert not node.ports["edge_callback"].is_dependent

    def test_an_array_outlet_takes_its_elements(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

        from haywire.barn.builtin.wires import DataWire

        node = make_node(graph_with_library_system, EdgeLinkTestNode.class_identity.registry_key).node

        assert _id(node.ports["array_float_outlet"].wire_type) == DataWire.id

    def test_config_ports_and_folds_have_none(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

        node = make_node(graph_with_library_system, FoldProbeNode.class_identity.registry_key).node
        config = node.ports["substeps"]
        folds = [p for p in node.ports.values() if p.is_fold]

        assert config.port_type is PortType.CONFIG
        assert config.wire_type is None
        assert config.wire_key is None
        assert folds
        assert all(f.wire_type is None for f in folds)

    def test_a_bare_add_slot_is_the_wildcard_and_counts_as_dependent(self, graph_with_library_system):
        from haybale_testing.nodes.testbed.add_port_test import AddPortTestNode

        from haywire.barn.builtin.wires import DataWire

        node = make_node(graph_with_library_system, AddPortTestNode.class_identity.registry_key).node
        bare = node.ports["add_out_0"]
        decided = node.ports["str_in_0"]

        assert bare.wire_type is None
        assert bare.wire_key == WILDCARD
        assert bare.is_dependent
        assert not bare.has_role(WireRole.DEPENDENT)
        assert _id(decided.wire_type) == DataWire.id


@pytest.mark.unit
def test_flow_type_is_gone():
    import haywire.core.types as types_pkg
    from haywire.core.types import DataTypeIdentity, enums

    assert not hasattr(types_pkg, "FlowType")
    assert not hasattr(enums, "FlowType")
    assert "flow_type" not in DataTypeIdentity.__dataclass_fields__


@pytest.mark.unit
def test_a_bare_add_declares_no_wire_type():
    from haywire.barn.builtin.types import ADD

    assert ADD.class_identity.wire_type is None
