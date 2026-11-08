"""Reblock, Resample, Channel Select and Mix to Mono nodes."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haybale_audio.value import AudioBlock
from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _node(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _with_listener(node: Any) -> None:
    cb = importlib.import_module("haybale_audio.types.callback").CALLBACK_AUDIO
    node.value = lambda port_id: {"edge": cb(name="listener")} if port_id == "callbacks" else None


def _ramp(ch: int, frames: int, start: int = 0, rate: int = 48000) -> AudioBlock:
    row = np.arange(start, start + frames, dtype=np.float32)
    return AudioBlock(np.stack([row * (c + 1) for c in range(ch)]), rate)


def _emitted(ctx: MagicMock) -> list[dict]:
    return [c.kwargs["payload"] for c in ctx.emit_callback.call_args_list]


def test_reblock_delivers_fixed_blocks_in_order(graph_with_library_system):
    node = _node(graph_with_library_system, "reblock", "ReblockNode")
    _with_listener(node)
    ctx = MagicMock()
    start = 0
    for size in (1024, 100, 300):
        assert node.worker(ctx, audio=_ramp(2, size, start)) == "next"
        start += size
    out = _emitted(ctx)
    assert [p["audio"].frames for p in out] == [256] * 5, "1424 frames give five blocks, 144 remain"
    assert [p["block_number"] for p in out] == [0, 1, 2, 3, 4]
    assert out[1]["timestamp"] == pytest.approx(256 / 48000)
    np.testing.assert_array_equal(out[4]["audio"].data[0], np.arange(1024, 1280, dtype=np.float32))


def test_reblock_rejects_missing_audio(graph_with_library_system):
    node = _node(graph_with_library_system, "reblock", "ReblockNode")
    with pytest.raises(ValueError, match="no audio block"):
        node.worker(MagicMock(), audio=None)


def test_resample_delivers_blocks_at_the_target_rate(graph_with_library_system):
    node = _node(graph_with_library_system, "resample", "ResampleNode")
    _with_listener(node)
    ctx = MagicMock()
    for _ in range(40):
        node.worker(ctx, audio=AudioBlock.silence(2, 441, 44100))
    out = _emitted(ctx)
    assert out
    assert {p["audio"].sample_rate for p in out} == {48000}
    assert sum(p["audio"].frames for p in out) == pytest.approx(40 * 480, abs=200)
    assert [p["block_number"] for p in out] == list(range(len(out)))


def test_channel_select_reorders(graph_with_library_system):
    node = _node(graph_with_library_system, "channel_select", "ChannelSelectNode")
    node.worker(MagicMock(), audio=_ramp(2, 4), channels="1, 0, 0")
    out = node.ports["selected"].get_value()
    assert out.channels == 3
    np.testing.assert_array_equal(out.data[0], _ramp(2, 4).data[1])


def test_channel_select_names_a_missing_channel(graph_with_library_system):
    node = _node(graph_with_library_system, "channel_select", "ChannelSelectNode")
    with pytest.raises(ValueError, match="channel 5 does not exist"):
        node.worker(MagicMock(), audio=_ramp(2, 4), channels="0, 5")


def test_mix_to_mono_averages(graph_with_library_system):
    node = _node(graph_with_library_system, "to_mono", "MixToMonoNode")
    node.worker(MagicMock(), audio=AudioBlock(np.array([[1.0, 2.0], [3.0, 4.0]], np.float32), 48000))
    np.testing.assert_array_equal(node.ports["mono"].get_value().data, [[2.0, 3.0]])
