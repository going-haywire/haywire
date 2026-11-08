"""Image Event: publishes its listener name on CALLBACK_IMAGE and unpacks the emitter's payload."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _event(graph: Any) -> Any:
    cls = importlib.import_module("haybale_image.nodes.image_event").ImageEventNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def test_listen_outlet_publishes_node_id(graph_with_library_system):
    node = _event(graph_with_library_system)
    value = node.ports["listen_callback"].get_value()
    cb = importlib.import_module("haybale_image.types.callback").CALLBACK_IMAGE
    assert isinstance(value, cb), "a dict here breaks the emitter's pooled inlet"
    assert value.name == node.node_id


def test_worker_unpacks_payload(graph_with_library_system):
    value_mod = importlib.import_module("haybale_image.value")
    node = _event(graph_with_library_system)
    img = value_mod.ImageValue.from_array(np.zeros((4, 6, 3), np.uint8))
    ctx = MagicMock()
    ctx.trigger.payload = {"image": img, "timestamp": 1.5, "frame_number": 7}
    assert node.worker(ctx) == "frame_ready"
    assert node.ports["image"].get_value() is img
    assert node.ports["timestamp"].get_value() == 1.5
    assert node.ports["frame_number"].get_value() == 7


def test_worker_ignores_payload_without_image(graph_with_library_system):
    node = _event(graph_with_library_system)
    ctx = MagicMock()
    ctx.trigger.payload = {"timestamp": 1.0}
    assert node.worker(ctx) is None


def test_image_callback_is_independent_of_core_callback():
    from haywire.barn.builtin.types import CALLBACK

    cb = importlib.import_module("haybale_image.types.callback").CALLBACK_IMAGE
    assert not issubclass(cb, CALLBACK)
