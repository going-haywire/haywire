"""Audio Event: publishes its listener name on CALLBACK_AUDIO and unpacks the emitter's payload."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _event(graph: Any) -> Any:
    cls = importlib.import_module("haybale_audio.nodes.audio_event").AudioEventNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def test_listen_outlet_publishes_node_id(graph_with_library_system):
    node = _event(graph_with_library_system)
    value = node.ports["listen_callback"].get_value()
    cb = importlib.import_module("haybale_audio.types.callback").CALLBACK_AUDIO
    assert isinstance(value, cb), "a dict here breaks the emitter's pooled inlet"
    assert value.name == node.node_id


def test_defaults_to_block_with_deep_queue(graph_with_library_system):
    from haywire.core.execution import QueueMode

    sub = _event(graph_with_library_system).event_subscription
    assert sub.queue_mode is QueueMode.BLOCK, "Drop loses audio blocks"
    assert sub.max_queue_size == 100


def test_worker_unpacks_payload(graph_with_library_system):
    value_mod = importlib.import_module("haybale_audio.value")
    node = _event(graph_with_library_system)
    block = value_mod.AudioBlock.silence(2, 256, 48000)
    ctx = MagicMock()
    ctx.trigger.payload = {"audio": block, "timestamp": 1.5, "block_number": 7}
    assert node.worker(ctx) == "block_ready"
    assert node.ports["audio"].get_value() is block
    assert node.ports["timestamp"].get_value() == 1.5
    assert node.ports["block_number"].get_value() == 7


def test_worker_ignores_payload_without_audio(graph_with_library_system):
    node = _event(graph_with_library_system)
    ctx = MagicMock()
    ctx.trigger.payload = {"timestamp": 1.0}
    assert node.worker(ctx) is None
