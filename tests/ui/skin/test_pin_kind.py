"""A pin's icon kind comes from its wire type's pin_kind."""

import pytest

from haywire.core.types import PortType

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def test_callback_and_control_pins_take_their_wire_types_kind(graph_with_library_system):
    from haybale_testing.nodes.testbed.emit_callback_node import TestEmitCallbackNode

    from haywire.ui.skin.pin_icons import DEFAULT_PIN_ICONS

    node = make_node(graph_with_library_system, TestEmitCallbackNode.class_identity.registry_key).node

    assert DEFAULT_PIN_ICONS.role_of(node.ports["edge_callback"]) == "callback_in_multi"
    assert DEFAULT_PIN_ICONS.role_of(node.ports["exec"]) == "control_out"


def test_a_config_port_resolves_to_no_icon(graph_with_library_system):
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    from haywire.ui.skin.pin_icons import DEFAULT_PIN_ICONS

    node = make_node(graph_with_library_system, FoldProbeNode.class_identity.registry_key).node
    config = node.ports["substeps"]

    assert config.port_type is PortType.CONFIG
    assert DEFAULT_PIN_ICONS.resolve(config) is None
