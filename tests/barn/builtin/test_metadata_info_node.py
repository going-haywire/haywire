"""New Bundle and Metadata Info."""

import numpy as np
import pytest
from haybale_image.value import ImageMetadata, ImageValue

from haywire.barn.builtin.carrier import BundleValue
from haywire.barn.builtin.nodes.metadata import MetadataInfoNode, NewBundleNode
from haywire.barn.builtin.types import FLOAT, STRING

pytestmark = pytest.mark.integration


def _make(graph, cls):
    wrapper = graph.create_node_wrapper(cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls)
    return wrapper.node


def _run(node, value):
    node.worker(None, value)
    return node.ports["text"].data.get_value(), node.ports["count"].data.get_value()


def test_info_lists_fields_and_describe_lines(graph_with_library_system, library_system):
    info = _make(graph_with_library_system, MetadataInfoNode)
    image = ImageValue.from_array(np.zeros((2, 2), np.uint8)).with_metadata(ImageMetadata(icc=b"abc"))
    text, count = _run(info, image.stamped("t", 1.5, FLOAT))
    assert "t (FLOAT) = 1.5" in text
    assert "icc: 3 bytes" in text
    assert count == 1


def test_info_on_an_empty_bundle_says_so(graph_with_library_system, library_system):
    info = _make(graph_with_library_system, MetadataInfoNode)
    assert _run(info, BundleValue()) == ("No fields", 0)


def test_a_long_value_is_cut_short(graph_with_library_system, library_system):
    info = _make(graph_with_library_system, MetadataInfoNode)
    text, _ = _run(info, BundleValue().stamped("s", "x" * 500, STRING))
    assert len(text) < 100
    assert text.endswith("...")


def test_new_bundle_gives_a_fresh_empty_bundle(graph_with_library_system, library_system):
    new = _make(graph_with_library_system, NewBundleNode)
    new.worker(None)
    value = new.ports["bundle"].data.get_value()
    assert isinstance(value, BundleValue)
    assert dict(value.fields) == {}
