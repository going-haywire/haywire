"""A DATA inlet takes one edge; only a pooled inlet takes several."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, PortType


@pytest.mark.unit
def test_a_data_inlet_is_single_link_whatever_it_declares():
    port = DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id="v",
        type_cls=FLOAT,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
        allow_multiple_links=True,
    )

    assert port.allow_multiple_links is False


@pytest.mark.integration
def test_a_pooled_inlet_still_takes_several_edges(graph_with_library_system, library_system):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    node = graph_with_library_system.create_node_wrapper(
        EdgeLinkTestNode.class_identity.registry_key, position=(0, 0)
    ).node

    assert node.ports["pooled_float_inlet"].allow_multiple_links is True
