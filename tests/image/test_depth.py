"""The DEPTH type and DepthValue."""

import numpy as np
import pytest
from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

from haywire.barn.builtin.carrier import CarrierValue
from haywire.barn.builtin.types import CARRIER, FLOAT

from haybale_image.types.depth import DEPTH
from haybale_image.types.image import IMAGE, IMAGE_RGB
from haybale_image.value import DepthValue


@pytest.mark.unit
class TestDepthValue:
    def test_refuses_anything_but_uint16_hw(self):
        with pytest.raises(TypeError):
            DepthValue.from_array(np.zeros((2, 2), np.uint8))
        with pytest.raises(ValueError, match="H×W"):
            DepthValue.from_array(np.zeros((2, 2, 3), np.uint16))

    def test_array_is_read_only_shares_the_buffer_and_keeps_fields(self):
        buf = np.zeros((2, 3), np.uint16)
        d = DepthValue.from_array(buf).stamped("t", 1.5, FLOAT)
        assert isinstance(d, CarrierValue)
        assert (d.width, d.height) == (3, 2)
        assert d.array().flags.writeable is False
        assert np.shares_memory(d.array(), buf)
        assert d.fields["t"].value == 1.5

    def test_empty(self):
        assert DepthValue.empty().is_empty
        assert not DepthValue.from_array(np.zeros((1, 1), np.uint16)).is_empty

    def test_type_is_a_visible_unsaved_carrier(self):
        assert issubclass(DEPTH, CARRIER)
        assert not issubclass(DEPTH, IMAGE)
        assert DEPTH.element_type_cls is DepthValue
        assert DEPTH.class_identity.hidden is False
        assert isinstance(DEPTH.create_field().get_value(), DepthValue)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("inlet_type", "connects"), [(CARRIER, True), (DEPTH, True), (IMAGE, False), (IMAGE_RGB, False)]
)
def test_depth_reaches_a_carrier_inlet_but_not_an_image_inlet(
    graph_with_library_system, library_system, inlet_type, connects
):
    graph = graph_with_library_system
    key = EdgeLinkTestNode.class_identity.registry_key
    source = graph.create_node_wrapper(key, position=(0, 0))
    sink = graph.create_node_wrapper(key, position=(300, 0))
    source.node.add(DEPTH.as_outlet("depth_src"))
    sink.node.add(inlet_type.as_inlet("target"))
    edge = graph.create_edge_wrapper(source.node_id, "depth_src", sink.node_id, "target")
    graph._validation.force_immediate_validation()
    assert edge.is_functional() is connects
