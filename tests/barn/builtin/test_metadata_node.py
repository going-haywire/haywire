"""What the Metadata node stamps and reads when it runs."""

from typing import Any, cast

import pytest
from haybale_image.types.image import IMAGE, IMAGE_RGB
from haybale_image.value import ImageValue
from haybale_testing.types.test_types import TEST_INT

import numpy as np

from haywire.barn.builtin.carrier import BundleValue
from haywire.barn.builtin.nodes import metadata as mdn
from haywire.barn.builtin.nodes.metadata import MetadataNode, MetadataNodeBase
from haywire.barn.builtin.types import BUNDLE, FIELD_LIST, FLOAT, INT, STRING
from haywire.core.node import NodeType, node
from tests.core.test_types.test_add_type import _make_link_node

pytestmark = pytest.mark.integration


def _validate(graph):
    graph._validation.force_immediate_validation()


def _make(graph, stamp=(), read=()):
    wrapper = graph.create_node_wrapper(MetadataNode.class_identity.registry_key, position=(300, 0))
    assert isinstance(wrapper.node, MetadataNode)
    stamps, reads = FIELD_LIST(), FIELD_LIST()
    for key, type_cls in stamp:
        stamps = stamps.with_added(key, type_cls)
    for key, type_cls in read:
        reads = reads.with_added(key, type_cls)
    wrapper.node.metadata_fields.stamp = stamps
    wrapper.node.metadata_fields.read = reads
    _validate(graph)
    return wrapper


def _feed(graph, wrapper, value, type_cls=BUNDLE):
    """Wire a source of ``type_cls`` holding ``value`` into the carrier inlet."""
    source = _make_link_node(graph, (0, 0))
    source.node.add(type_cls.as_outlet("carrier_src"))
    edge = graph.create_edge_wrapper(source.node_id, "carrier_src", wrapper.node_id, "carrier_inlet")
    _validate(graph)
    assert edge.is_functional()
    source.node.out("carrier_src", value)
    return source


def _outlet(wrapper):
    return wrapper.node.ports["carrier_outlet"].data.get_value()


def test_stamps_reach_the_outlet_and_not_the_input(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("t", FLOAT)])
    start = BundleValue()
    _feed(graph, meta, start)
    meta.node.ports["t_in"].set_value(1.5)
    meta.node.worker(None)
    assert _outlet(meta).fields["t"].value == 1.5
    assert _outlet(meta).fields["t"].type_key == FLOAT.class_identity.registry_key
    assert dict(start.fields) == {}


def test_a_wired_stamp_pin_stamps_the_incoming_value(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("n", TEST_INT)])
    _feed(graph, meta, BundleValue())
    source = _make_link_node(graph, (0, 300))
    edge = graph.create_edge_wrapper(source.node_id, "int_outlet", meta.node_id, "n_in")
    _validate(graph)
    assert edge.is_functional()
    source.node.out("int_outlet", 9)
    meta.node.worker(None)
    assert _outlet(meta).fields["n"].value == 9


def test_stamping_keeps_the_fields_already_there(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("t", FLOAT)])
    _feed(graph, meta, BundleValue().stamped("old", 1, INT))
    meta.node.worker(None)
    assert set(_outlet(meta).fields) == {"old", "t"}


def test_one_node_can_stamp_and_read_the_same_key(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("t", FLOAT)], read=[("t", FLOAT)])
    _feed(graph, meta, BundleValue())
    meta.node.ports["t_in"].set_value(1.5)
    meta.node.worker(None)
    assert meta.node.ports["t_out"].data.get_value() == 1.5


def test_a_present_key_is_written_to_its_pin(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, read=[("n", INT)])
    _feed(graph, meta, BundleValue().stamped("n", 5, INT))
    meta.node.worker(None)
    assert meta.node.ports["n_out"].data.get_value() == 5


def test_a_derived_type_reads_as_its_parent(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, read=[("img", IMAGE)])
    pixels = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    _feed(graph, meta, BundleValue().stamped("img", pixels, IMAGE_RGB))
    meta.node.worker(None)
    assert meta.node.ports["img_out"].data.get_value() is pixels


def test_an_image_stays_an_image(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("t", FLOAT)])
    pixels = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    _feed(graph, meta, pixels, IMAGE_RGB)
    meta.node.worker(None)
    assert isinstance(_outlet(meta), ImageValue)
    assert _outlet(meta).array() is pixels.array()
    assert dict(pixels.fields) == {}


def test_a_key_absent_now_replaces_the_last_value_with_the_default(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    meta = _make(graph, read=[("n", TEST_INT)])
    source = _feed(graph, meta, BundleValue().stamped("n", 5, TEST_INT))
    sink = _make_link_node(graph, (600, 0))
    edge = graph.create_edge_wrapper(meta.node_id, "n_out", sink.node_id, "int_inlet")
    _validate(graph)
    assert edge.is_functional()

    meta.node.worker(None)
    assert sink.node.value("int_inlet") == 5

    source.node.out("carrier_src", BundleValue())
    meta.node.worker(None)
    assert sink.node.value("int_inlet") == 0


def test_a_type_mismatch_writes_defaults_and_raises_after_the_other_pins(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    meta = _make(graph, read=[("t", STRING), ("ok", INT)])
    meta.node.ports["t_out"].data.set_value("stale")
    _feed(graph, meta, BundleValue().stamped("t", 1.5, FLOAT).stamped("ok", 3, INT))
    with pytest.raises(ValueError, match="Field 't' holds FLOAT, this pin reads STRING"):
        meta.node.worker(None)
    assert meta.node.ports["t_out"].data.get_value() == ""
    assert meta.node.ports["ok_out"].data.get_value() == 3
    assert "ok" in _outlet(meta).fields


def test_a_stamped_type_that_is_gone_counts_as_a_mismatch(graph_with_library_system, library_system):
    from haywire.barn.builtin.carrier import Stamp

    graph = graph_with_library_system
    meta = _make(graph, read=[("t", INT)])
    _feed(graph, meta, BundleValue().with_fields({"t": Stamp(1, "nolib:type:GONE")}))
    with pytest.raises(ValueError, match="Field 't' holds nolib:type:GONE, this pin reads INT"):
        meta.node.worker(None)


def test_nothing_connected_gives_an_empty_carrier(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("t", FLOAT)])
    meta.node.worker(None)
    assert set(_outlet(meta).fields) == {"t"}


@node(label="Metadata Library Probe", menu="testing/testbed", node_type=NodeType.DATA)
class _LibraryNode(MetadataNodeBase):
    """A library's own node, with its fields declared on the class."""

    READ_FIELDS = FIELD_LIST().with_added("camera_timestamp", FLOAT)


def test_a_library_node_declares_fixed_fields(graph_with_library_system, library_system, monkeypatch):
    graph = graph_with_library_system
    source = _make_link_node(graph, (0, 0))
    key = _LibraryNode.class_identity.registry_key
    factory = source._node_factory
    original = factory.get_node
    monkeypatch.setattr(factory, "get_node", lambda k: (_LibraryNode, None) if k == key else original(k))
    wrapper = graph.create_node_wrapper(key, position=(300, 0))
    assert isinstance(wrapper.node, _LibraryNode)
    assert "camera_timestamp_out" in wrapper.node.ports
    _feed(graph, wrapper, BundleValue().stamped("camera_timestamp", 1.5, FLOAT))
    wrapper.node.worker(cast(Any, None))
    assert wrapper.node.ports["camera_timestamp_out"].data.get_value() == 1.5


def test_an_unwired_carrier_keeps_the_outlets_kind_of_value(graph_with_library_system, library_system):
    graph = graph_with_library_system
    meta = _make(graph, stamp=[("t", FLOAT)])
    source = _feed(graph, meta, ImageValue.from_array(np.zeros((2, 2, 3), np.uint8)), IMAGE_RGB)
    edge = next(e for e in graph.edge_wrappers.values() if e.source_node_id == source.node_id)
    graph.remove_edge_wrapper(edge.edge_id)
    _validate(graph)
    assert meta.node.ports["carrier_outlet"].type_cls is IMAGE_RGB
    meta.node.worker(None)
    assert isinstance(_outlet(meta), ImageValue)
    assert _outlet(meta).is_empty
    assert "t" in _outlet(meta).fields


def test_an_absent_key_on_a_type_with_no_default_is_reported(
    graph_with_library_system, library_system, monkeypatch
):
    """Such an outlet cannot clear its consumer, which would keep the last value."""
    graph = graph_with_library_system
    meta = _make(graph, read=[("n", INT), ("ok", INT)])
    _feed(graph, meta, BundleValue().stamped("ok", 3, INT))
    written: dict = {}
    monkeypatch.setattr(mdn, "_default_of", lambda port: None if port.id == "n_out" else 0)
    monkeypatch.setattr(meta.node, "out", written.__setitem__)
    with pytest.raises(ValueError, match="Field 'n' is absent and INT has no default"):
        meta.node.worker(None)
    assert written["ok_out"] == 3
