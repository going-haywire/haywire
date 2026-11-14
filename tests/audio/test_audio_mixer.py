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


def _sources(graph: Any, mixer: Any, count: int) -> list[Any]:
    """Connect *count* Audio Events to the mixer's inputs; return their nodes."""
    events = []
    for n in range(count):
        event = _event(graph)
        make_edge(graph, event.node_id, "audio", mixer.node_id, f"in_{n}")
        events.append(event.node)
    graph.force_validation()
    return events


@pytest.mark.integration
def test_each_connected_source_gets_its_own_pins(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    assert "in_1" not in mixer.node.ports
    for n in range(2):
        make_edge(g, _event(g).node_id, "audio", mixer.node_id, f"in_{n}")
        for pin in (f"in_{n}", f"gain_{n}", f"mute_{n}"):
            assert pin in mixer.node.ports, pin
        assert f"write_{n}" not in mixer.node.ports, "an input collects its blocks without a Write pin"
        assert mixer.node.ports[f"in_{n}"].queues_values
        assert f"in_{n + 1}" in mixer.node.ports, "a fresh open input appears below"


@pytest.mark.integration
def test_removing_an_input_removes_its_gain_and_mute_and_undo_restores_them(graph_with_library_system):
    from haywire.core.graph.editor import Editor

    g = graph_with_library_system
    mixer = _mixer(g)
    _sources(g, mixer, 2)
    node = mixer.node
    assert node.ports["gain_0"].owner == "in_0"
    assert not node.ports["gain_0"].is_user_removable()
    node.ports["gain_0"].set_value(0.25)
    editor = Editor(g, mixer._node_factory)

    assert editor.remove_port(mixer.node_id, "in_0")
    assert not {"in_0", "gain_0", "mute_0"} & set(node.ports)
    assert {"in_1", "gain_1", "mute_1"} <= set(node.ports)

    assert editor.undo()
    g.force_validation()
    assert {"in_0", "gain_0", "mute_0"} <= set(node.ports)
    assert node.value("gain_0") == 0.25
    assert node.ports["in_0"].is_linked()


@pytest.mark.integration
def test_tick_mixes_the_inputs_with_gain_and_mute(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    events = _sources(g, mixer, 3)
    mixer.node.ports["gain_1"].set_value(0.5)
    mixer.node.ports["mute_2"].set_value(True)
    clock = _block(0.0)

    for _ in range(10):
        for event, value in zip(events, (0.25, 0.5, 0.9), strict=True):
            event.out("audio", _block(value))
    assert mixer.node.worker(_pin("tick", clock)) == "next"
    assert mixer.node.worker(_pin("tick", clock)) == "next"

    mixed = mixer.node.ports["mixed"].get_value()
    assert (mixed.channels, mixed.frames, mixed.sample_rate) == (1, 256, 48000)
    np.testing.assert_allclose(mixed.data, 0.5, atol=1e-3)


@pytest.mark.integration
def test_a_tick_takes_every_block_collected_since_the_last(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    (event,) = _sources(g, mixer, 1)
    for _ in range(10):
        event.out("audio", _block(0.4))

    mixer.node.worker(_pin("tick", _block(0.0)))

    assert mixer.node.drain("in_0") == []
    assert mixer.node.hb_buffers[0].depth > 0


@pytest.mark.integration
def test_blocks_written_before_the_first_tick_are_kept(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    (event,) = _sources(g, mixer, 1)
    for _ in range(10):
        event.out("audio", _block(0.4))
    clock = _block(0.0)
    mixer.node.worker(_pin("tick", clock))
    mixer.node.worker(_pin("tick", clock))
    np.testing.assert_allclose(mixer.node.ports["mixed"].get_value().data, 0.4, atol=1e-3)


@pytest.mark.integration
def test_input_that_has_not_filled_its_prefill_is_silent(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    (event,) = _sources(g, mixer, 1)
    event.out("audio", _block(0.4))
    mixer.node.worker(_pin("tick", _block(0.0)))
    assert not mixer.node.ports["mixed"].get_value().data.any()


@pytest.mark.integration
def test_blocks_beyond_an_inputs_limit_are_dropped_and_counted(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    (event,) = _sources(g, mixer, 1)
    for _ in range(198):
        event.out("audio", _block(0.4))

    mixer.node.worker(_pin("tick", _block(0.0)))

    assert mixer.node.hb_dropped == 6
    assert "dropped 6" in mixer.node.value("status")


@pytest.mark.integration
def test_a_reset_discards_the_collected_blocks(graph_with_library_system):
    g = graph_with_library_system
    mixer = _mixer(g)
    (event,) = _sources(g, mixer, 1)
    for _ in range(10):
        event.out("audio", _block(0.4))

    mixer.node.hb_reset()

    assert mixer.node.drain("in_0") == []


@pytest.mark.integration
def test_tick_without_a_triggering_audio_block_is_an_error(graph_with_library_system):
    mixer = _mixer(graph_with_library_system)
    with pytest.raises(ValueError, match="audio event"):
        mixer.node.worker(_pin("tick"))
