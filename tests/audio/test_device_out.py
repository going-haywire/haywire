"""FrameFifo, channel fitting, DeviceOutput and the Device Out node, against a fake device."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haybale_audio.dsp.channels import fit
from haybale_audio.dsp.fifo import FrameFifo
from haybale_audio.io.device import DeviceOutput, StreamCallback
from haybale_audio.value import AudioBlock
from tests.conftest import make_node

pytestmark = pytest.mark.unit


class FakeStream:
    def __init__(self, callback: StreamCallback) -> None:
        self.callback = callback
        self.state = "open"

    def start(self) -> None:
        self.state = "started"

    def stop(self) -> None:
        self.state = "stopped"

    def close(self) -> None:
        self.state = "closed"

    def pull(self, frames: int, channels: int) -> np.ndarray:
        outdata = np.full((frames, channels), 9.0, dtype=np.float32)
        self.callback(outdata, frames, None, None)
        return outdata


class FakeBackend:
    def __init__(self, rate: int = 48000, channels: int = 2) -> None:
        self.rate, self.channels = rate, channels
        self.stream: FakeStream | None = None
        self.opened: tuple[Any, int, int] | None = None

    def device_info(self, device: str | int | None) -> tuple[int, int]:
        return self.rate, self.channels

    def open(self, device: str | int | None, sample_rate: int, channels: int, callback: StreamCallback):
        self.opened = (device, sample_rate, channels)
        self.stream = FakeStream(callback)
        return self.stream


def _block(value: float, channels: int = 1, frames: int = 256, rate: int = 48000) -> AudioBlock:
    return AudioBlock(np.full((channels, frames), value, dtype=np.float32), rate)


def test_fifo_returns_pushed_frames_in_order_across_chunks():
    fifo = FrameFifo(1, 100)
    fifo.push(np.arange(0, 5, dtype=np.float32)[None, :])
    fifo.push(np.arange(5, 8, dtype=np.float32)[None, :])
    np.testing.assert_array_equal(fifo.pop(6)[0], [0, 1, 2, 3, 4, 5])
    assert fifo.depth == 2


def test_fifo_pads_with_silence_and_counts_underruns():
    fifo = FrameFifo(1, 100)
    fifo.push(np.ones((1, 3), dtype=np.float32))
    np.testing.assert_array_equal(fifo.pop(5)[0], [1, 1, 1, 0, 0])
    assert fifo.underruns == 2


def test_fifo_drops_the_oldest_frames_when_full():
    fifo = FrameFifo(1, 4)
    fifo.push(np.arange(0, 3, dtype=np.float32)[None, :])
    fifo.push(np.arange(3, 6, dtype=np.float32)[None, :])
    assert fifo.overruns == 2
    np.testing.assert_array_equal(fifo.pop(4)[0], [2, 3, 4, 5])


def test_fit_repeats_mono_trims_extra_and_pads_missing_channels():
    mono = np.array([[1.0, 2.0]], dtype=np.float32)
    np.testing.assert_array_equal(fit(mono, 2), [[1, 2], [1, 2]])
    four = np.arange(8, dtype=np.float32).reshape(4, 2)
    np.testing.assert_array_equal(fit(four, 2), four[:2])
    two = np.ones((2, 2), dtype=np.float32)
    np.testing.assert_array_equal(fit(two, 3)[2], [0, 0])


def test_output_is_silent_until_the_prefill_is_queued():
    backend = FakeBackend()
    out = DeviceOutput(None, prefill_blocks=2, backend=backend)
    out.write(_block(0.5))
    assert backend.stream is not None
    assert backend.stream.state == "started"
    assert not backend.stream.pull(128, 2).any(), "one of two prefill blocks is not enough"
    out.write(_block(0.5))
    out.write(_block(0.5))  # the converter's first block is short, so the prefill needs one more
    played = backend.stream.pull(128, 2)
    assert played.shape == (128, 2)
    assert np.allclose(played, 0.5, atol=0.1), "mono block plays on both channels"
    assert np.allclose(played[:, 0], played[:, 1])


def test_output_restarts_after_an_underrun():
    backend = FakeBackend()
    out = DeviceOutput(None, prefill_blocks=1, backend=backend)
    out.write(_block(0.5))
    out.write(_block(0.5))
    assert backend.stream is not None
    backend.stream.pull(256, 2)
    backend.stream.pull(256, 2)  # the queue holds 236 of these 256 frames
    assert out.underruns == 1
    out.write(_block(0.5))
    assert backend.stream.pull(64, 2).any(), "playback resumes once the prefill is back"


def test_output_resamples_to_the_device_rate():
    backend = FakeBackend(rate=44100, channels=2)
    out = DeviceOutput(None, prefill_blocks=4, backend=backend)
    for _ in range(40):
        out.write(_block(0.25, frames=480, rate=48000))
    assert backend.opened == (None, 44100, 2)
    assert out.sample_rate == 44100
    expected = 40 * 480 * 44100 / 48000
    assert out.depth + out.overruns == pytest.approx(expected, rel=0.02)


def test_output_limits_channels_to_the_device():
    backend = FakeBackend(channels=2)
    out = DeviceOutput(None, backend=backend)
    out.write(_block(0.1, channels=6))
    assert out.channels == 2


def test_close_stops_the_stream_and_the_next_write_reopens():
    backend = FakeBackend()
    out = DeviceOutput(None, backend=backend)
    out.write(_block(0.1))
    first = backend.stream
    out.close()
    assert first is not None
    assert first.state == "closed"
    out.write(_block(0.1))
    assert backend.stream is not first


def test_invalid_prefill_is_rejected():
    with pytest.raises(ValueError, match="prefill_blocks"):
        DeviceOutput(None, prefill_blocks=0, backend=FakeBackend())


@pytest.mark.integration
def test_node_plays_blocks_and_stops(graph_with_library_system, monkeypatch):
    mod = importlib.import_module("haybale_audio.nodes.device_out")
    backend = FakeBackend()
    monkeypatch.setattr(mod, "DeviceOutput", lambda device, prefill: DeviceOutput(device, prefill, backend))
    cls = mod.DeviceOutNode
    wrapper = make_node(graph_with_library_system, cls.class_identity.registry_key, position=(0, 0))
    node = wrapper.node
    assert isinstance(node, cls)

    write, stop = MagicMock(), MagicMock()
    write.control_pin, stop.control_pin = "write", "stop"
    assert node.worker(write, audio=_block(0.5)) == "next"
    assert backend.opened is not None
    assert backend.opened[0] is None, "an empty device setting is the default"
    assert node.ports["depth"].get_value() > 0
    assert node.worker(stop) is None
    assert backend.stream is not None
    assert backend.stream.state == "closed"
    assert node.ports["status"].get_value() == "Stopped"


def test_node_write_without_a_block_is_an_error(graph_with_library_system):
    mod = importlib.import_module("haybale_audio.nodes.device_out")
    wrapper = make_node(
        graph_with_library_system, mod.DeviceOutNode.class_identity.registry_key, position=(0, 0)
    )
    ctx = MagicMock()
    ctx.control_pin = "write"
    with pytest.raises(ValueError, match="audio block"):
        wrapper.node.worker(ctx)
