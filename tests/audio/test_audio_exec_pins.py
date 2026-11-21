"""Which pins of the audio nodes carry AUDIO_EXEC (the audio flow) and which stay EXEC (start and stop)."""

import importlib
from typing import Any

import pytest
from haywire.barn.builtin.types import EXEC

from haybale_audio.types.audio_exec import AUDIO_EXEC
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

# module, class, {pin id: expected type}
_NODES = [
    ("audio_event", "AudioEventNode", {"block_ready": AUDIO_EXEC}),
    ("reblock", "ReblockNode", {"write": AUDIO_EXEC, "next": AUDIO_EXEC}),
    ("resample", "ResampleNode", {"write": AUDIO_EXEC, "next": AUDIO_EXEC}),
    ("recorder", "RecorderNode", {"write": AUDIO_EXEC, "next": AUDIO_EXEC, "stop": EXEC}),
    ("device_out", "DeviceOutNode", {"write": AUDIO_EXEC, "next": AUDIO_EXEC, "stop": EXEC}),
    ("audio_mixer", "AudioMixerNode", {"tick": AUDIO_EXEC, "next": AUDIO_EXEC}),
    (
        "file_player",
        "FilePlayerNode",
        {"start": EXEC, "stop": EXEC, "started": EXEC, "stopped": EXEC},
    ),
    (
        "audio_clock",
        "AudioClockNode",
        {"start": EXEC, "stop": EXEC, "started": EXEC, "stopped": EXEC},
    ),
]


def _node(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


@pytest.mark.parametrize(("module", "name", "pins"), _NODES, ids=[n[0] for n in _NODES])
def test_pins_carry_the_expected_execution_type(graph_with_library_system, module, name, pins):
    node = _node(graph_with_library_system, module, name)
    actual = {pin: node.ports[pin].type_cls for pin in pins}
    assert actual == pins


def test_a_mixer_input_needs_no_write_pin(graph_with_library_system):
    graph = graph_with_library_system
    mixer = make_node(
        graph,
        importlib.import_module(
            "haybale_audio.nodes.audio_mixer"
        ).AudioMixerNode.class_identity.registry_key,
        position=(0, 0),
    )
    event = make_node(
        graph,
        importlib.import_module(
            "haybale_audio.nodes.audio_event"
        ).AudioEventNode.class_identity.registry_key,
        position=(0, 0),
    )
    make_edge(graph, event.node_id, "audio", mixer.node_id, "in_0")
    assert "write_0" not in mixer.node.ports
