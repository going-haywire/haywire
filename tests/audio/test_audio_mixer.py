"""PullBuffer, mix and the Audio Mixer node: per-input ports, buffering and summing."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haybale_audio.dsp.buffer import PullBuffer
from haybale_audio.dsp.mix import mix
from haybale_audio.value import AudioBlock
from tests.conftest import make_edge, make_node


def _block(value: float, channels: int = 1, frames: int = 256, rate: int = 48000) -> AudioBlock:
    return AudioBlock(np.full((channels, frames), value, dtype=np.float32), rate)


@pytest.mark.unit
def test_buffer_is_silent_until_prefilled_and_restarts_after_a_stall():
    buf = PullBuffer(48000, 1, 256, prefill_blocks=2)
    buf.write(_block(0.5))
    assert buf.read(256) is None, "236 frames after the converter's first block is short of 512"
    buf.write(_block(0.5))
    buf.write(_block(0.5))
    out = buf.read(256)
    assert out is not None
    assert out.shape == (1, 256)
    assert buf.read(1000) is not None, "asking for more than is queued pads with silence"
    assert buf.restarts == 1
    assert buf.read(256) is None, "playback waits for the prefill again"


@pytest.mark.unit
def test_buffer_starts_playing_at_its_prefill_depth():
    buf = PullBuffer(48000, 1, 256, prefill_blocks=2)
    for _ in range(40):
        buf.write(_block(0.5))  # written long before the first read
    assert buf.depth > 5000
    assert buf.read(256) is not None
    assert buf.depth == 2 * 256 - 256, "the excess is dropped and the first read is taken from the rest"


@pytest.mark.unit
def test_buffer_converts_rate_and_channels():
    buf = PullBuffer(48000, 2, 256, prefill_blocks=1)
    for _ in range(10):
        buf.write(_block(0.25, channels=1, frames=441, rate=44100))
    out = buf.read(256)
    assert out is not None
    assert out.shape == (2, 256)
    assert np.allclose(out[0], out[1])


@pytest.mark.unit
def test_mix_sums_with_gains_and_fits_channels():
    mono = np.full((1, 4), 0.5, dtype=np.float32)
    stereo = np.array([[0.1] * 4, [0.3] * 4], dtype=np.float32)
    out = mix([(mono, 1.0), (stereo, 2.0)], channels=2, frames=4)
    np.testing.assert_allclose(out[0], 0.7)
    np.testing.assert_allclose(out[1], 1.1)
    assert out.dtype == np.float32


@pytest.mark.unit
def test_mix_of_nothing_is_silence():
    assert not mix([], 2, 8).any()


def _mixer(graph: Any):
    mod = importlib.import_module("haybale_audio.nodes.audio_mixer")
    wrapper = make_node(graph, mod.AudioMixerNode.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, mod.AudioMixerNode), "an unknown key yields an ErrorNode"
    return wrapper


def _event(graph: Any):
    mod = importlib.import_module("haybale_audio.nodes.audio_event")
    return make_node(graph, mod.AudioEventNode.class_identity.registry_key, position=(0, 0))


def _pin(name: str, block: AudioBlock | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.control_pin = name
    ctx.trigger.payload = {"audio": block} if block is not None else {}
    return ctx


@pytest.mark.integration
def test_each_connected_source_gets_its_own_pins(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    assert "in_1" not in mixer.node.ports
    for n in range(2):
        make_edge(g, _event(g).node_id, "audio", mixer.node_id, f"in_{n}")
        for pin in (f"in_{n}", f"write_{n}", f"gain_{n}", f"mute_{n}"):
            assert pin in mixer.node.ports, pin
        assert f"in_{n + 1}" in mixer.node.ports, "a fresh open input appears below"


@pytest.mark.integration
def test_tick_mixes_the_inputs_with_gain_and_mute(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    for n in range(3):
        make_edge(g, _event(g).node_id, "audio", mixer.node_id, f"in_{n}")
    values: dict[str, Any] = {
        "in_0": _block(0.25),
        "in_1": _block(0.5),
        "gain_1": 0.5,
        "in_2": _block(0.9),
        "mute_2": True,
    }
    mixer.node.value = lambda port_id: values.get(port_id)
    clock = _block(0.0)

    for _ in range(10):
        for n in range(3):
            mixer.node.worker(_pin(f"write_{n}"))
    assert mixer.node.worker(_pin("tick", clock)) == "next"
    assert mixer.node.worker(_pin("tick", clock)) == "next"

    mixed = mixer.node.ports["mixed"].get_value()
    assert (mixed.channels, mixed.frames, mixed.sample_rate) == (1, 256, 48000)
    np.testing.assert_allclose(mixed.data, 0.5, atol=1e-3)


@pytest.mark.integration
def test_blocks_written_before_the_first_tick_are_kept(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    make_edge(g, _event(g).node_id, "audio", mixer.node_id, "in_0")
    values = {"in_0": _block(0.4)}
    mixer.node.value = lambda port_id: values.get(port_id)
    for _ in range(10):
        mixer.node.worker(_pin("write_0"))
    clock = _block(0.0)
    mixer.node.worker(_pin("tick", clock))
    mixer.node.worker(_pin("tick", clock))
    np.testing.assert_allclose(mixer.node.ports["mixed"].get_value().data, 0.4, atol=1e-3)


@pytest.mark.integration
def test_input_that_has_not_filled_its_prefill_is_silent(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    make_edge(g, _event(g).node_id, "audio", mixer.node_id, "in_0")
    values = {"in_0": _block(0.4)}
    mixer.node.value = lambda port_id: values.get(port_id)
    mixer.node.worker(_pin("write_0"))
    mixer.node.worker(_pin("tick", _block(0.0)))
    assert not mixer.node.ports["mixed"].get_value().data.any()


@pytest.mark.integration
def test_tick_without_a_triggering_audio_block_is_an_error(graph_with_library_system):
    mixer = _mixer(graph_with_library_system)
    with pytest.raises(ValueError, match="audio event"):
        mixer.node.worker(_pin("tick"))


@pytest.mark.integration
def test_write_without_a_block_is_an_error(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    make_edge(g, _event(g).node_id, "audio", mixer.node_id, "in_0")
    mixer.node.value = lambda port_id: None
    with pytest.raises(ValueError, match="audio block"):
        mixer.node.worker(_pin("write_0"))
