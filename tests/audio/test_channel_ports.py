"""Channel Merge and Channel Split: their ADD slots grow audio ports when connected."""

import importlib
from typing import Any

import numpy as np
import pytest

from haybale_audio.value import AudioBlock
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def _add(graph: Any, module: str, name: str):
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper


def _kind(node: Any, port_id: str) -> str:
    """Return ``"AUDIO"``, ``"ADD"`` or ``"missing"`` for the port of that id."""
    port = node.ports.get(port_id)
    if port is None:
        return "missing"
    return (
        "ADD"
        if issubclass(port.type_cls, importlib.import_module("haywire.barn.builtin.types").ADD)
        else "AUDIO"
    )


def _block(channels: int, fill: float) -> AudioBlock:
    return AudioBlock(np.full((channels, 4), fill, np.float32), 48000)


def test_merge_grows_an_input_per_connection(graph_with_library_system):
    g = graph_with_library_system
    merge = _add(g, "channel_merge", "ChannelMergeNode")
    assert (_kind(merge.node, "in_0"), _kind(merge.node, "in_1")) == ("ADD", "missing")

    for n in range(2):
        source = _add(g, "audio_event", "AudioEventNode")
        make_edge(g, source.node_id, "audio", merge.node_id, f"in_{n}")
        assert _kind(merge.node, f"in_{n}") == "AUDIO"
        assert _kind(merge.node, f"in_{n + 1}") == "ADD", "a fresh open input appears below"


def test_merge_stacks_the_connected_blocks(graph_with_library_system):
    g = graph_with_library_system
    merge = _add(g, "channel_merge", "ChannelMergeNode")
    for n in range(2):
        make_edge(g, _add(g, "audio_event", "AudioEventNode").node_id, "audio", merge.node_id, f"in_{n}")
    blocks = {"in_0": _block(1, 0.25), "in_1": _block(2, 0.5)}
    merge.node.value = lambda port_id: blocks.get(port_id)

    merge.node.worker(None)

    out = merge.node.ports["merged"].get_value()
    assert out.channels == 3
    np.testing.assert_array_equal(out.data[:, 0], [0.25, 0.5, 0.5])


def test_merge_skips_inputs_without_a_block(graph_with_library_system):
    g = graph_with_library_system
    merge = _add(g, "channel_merge", "ChannelMergeNode")
    for n in range(2):
        make_edge(g, _add(g, "audio_event", "AudioEventNode").node_id, "audio", merge.node_id, f"in_{n}")
    blocks = {"in_1": _block(1, 0.5)}
    merge.node.value = lambda port_id: blocks.get(port_id)
    merge.node.worker(None)
    assert merge.node.ports["merged"].get_value().channels == 1


def test_merge_without_any_block_is_an_error(graph_with_library_system):
    merge = _add(graph_with_library_system, "channel_merge", "ChannelMergeNode")
    merge.node.value = lambda port_id: None
    with pytest.raises(ValueError, match="no audio block on any input"):
        merge.node.worker(None)


def test_split_grows_an_output_per_connection_and_numbers_them(graph_with_library_system):
    g = graph_with_library_system
    split = _add(g, "channel_split", "ChannelSplitNode")
    assert (_kind(split.node, "ch_0"), _kind(split.node, "ch_1")) == ("ADD", "missing")

    for n in range(2):
        sink = _add(g, "recorder", "RecorderNode")
        make_edge(g, split.node_id, f"ch_{n}", sink.node_id, "audio")
        assert _kind(split.node, f"ch_{n}") == "AUDIO"
        assert _kind(split.node, f"ch_{n + 1}") == "ADD"

    split.node.worker(None, audio=AudioBlock(np.array([[0.1] * 4, [0.2] * 4, [0.3] * 4], np.float32), 48000))
    assert split.node.ports["ch_0"].get_value().data[0, 0] == pytest.approx(0.1)
    assert split.node.ports["ch_1"].get_value().data[0, 0] == pytest.approx(0.2)


def test_split_names_a_missing_channel(graph_with_library_system):
    g = graph_with_library_system
    split = _add(g, "channel_split", "ChannelSplitNode")
    for n in range(2):
        make_edge(g, split.node_id, f"ch_{n}", _add(g, "recorder", "RecorderNode").node_id, "audio")
    with pytest.raises(ValueError, match="channel 1 does not exist"):
        split.node.worker(None, audio=_block(1, 0.1))
