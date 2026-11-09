"""FrameFifo, channel fitting, DeviceOutput and the Device Out node, against a fake device."""

import importlib
import sys
import time
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haybale_audio.dsp.channels import fit
from haybale_audio.dsp.fifo import FrameFifo
from haybale_audio.io.device import DeviceOutput, output_device_names
from haybale_audio.value import AudioBlock
from tests.conftest import make_node

pytestmark = pytest.mark.unit


class FakeStream:
    def __init__(self) -> None:
        self.state = "open"
        self.written: list[np.ndarray] = []
        self.underflow = False
        self.size = 4800
        self.queued = 0  # frames the device holds; a test sets it to model a filled device buffer
        self.fail: Exception | None = None

    def start(self) -> None:
        self.state = "started"

    def stop(self) -> None:
        self.state = "stopped"

    def close(self) -> None:
        self.state = "closed"

    @property
    def buffer_frames(self) -> int:
        return self.size

    @property
    def write_available(self) -> int:
        return self.size - self.queued

    def write(self, data: np.ndarray) -> bool:
        if self.fail is not None:
            raise self.fail
        self.written.append(data.copy())
        time.sleep(0.001)  # a device takes time to consume what it is given
        return self.underflow


class FakeBackend:
    def __init__(self, rate: int = 48000, channels: int = 2) -> None:
        self.rate, self.channels = rate, channels
        self.stream: FakeStream | None = None
        self.opened: tuple[Any, int, int] | None = None
        self.latency: float | None = None

    def device_info(self, device: str | int | None) -> tuple[int, int]:
        return self.rate, self.channels

    def open(self, device: str | int | None, sample_rate: int, channels: int, latency: float | None = None):
        self.opened = (device, sample_rate, channels)
        self.latency = latency
        self.stream = FakeStream()
        return self.stream


def _output(backend: FakeBackend, **kwargs: Any) -> DeviceOutput:
    """An output that the test drives with ``render``."""
    return DeviceOutput(None, backend=backend, threaded=False, **kwargs)


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
    out = _output(backend, prefill_blocks=2)
    out.write(_block(0.5))
    assert backend.stream is not None
    assert backend.stream.state == "started"
    assert not out.render(128).any(), "one of two prefill blocks is not enough"
    out.write(_block(0.5))
    out.write(_block(0.5))  # the converter's first block is short, so the prefill needs one more
    played = out.render(128)
    assert played.shape == (128, 2)
    assert np.allclose(played, 0.5, atol=0.1), "mono block plays on both channels"
    assert np.allclose(played[:, 0], played[:, 1])


def test_output_restarts_after_an_underrun():
    out = _output(FakeBackend(), prefill_blocks=1)
    out.write(_block(0.5))
    out.write(_block(0.5))
    out.render(256)
    out.render(256)  # the queue holds 236 of these 256 frames
    assert out.underruns == 1
    out.write(_block(0.5))
    assert out.render(64).any(), "playback resumes once the prefill is back"


def test_output_resamples_to_the_device_rate():
    backend = FakeBackend(rate=44100, channels=2)
    out = _output(backend, prefill_blocks=4)
    for _ in range(40):
        out.write(_block(0.25, frames=480, rate=48000))
    assert backend.opened == (None, 44100, 2)
    assert out.sample_rate == 44100
    expected = 40 * 480 * 44100 / 48000
    assert out.depth + out.overruns == pytest.approx(expected, rel=0.02)


def test_output_limits_channels_to_the_device():
    out = _output(FakeBackend(channels=2))
    out.write(_block(0.1, channels=6))
    assert out.channels == 2


def test_close_stops_the_stream_and_the_next_write_reopens():
    backend = FakeBackend()
    out = _output(backend)
    out.write(_block(0.1))
    first = backend.stream
    out.close()
    assert first is not None
    assert first.state == "closed"
    out.write(_block(0.1))
    assert backend.stream is not first


def test_the_device_buffer_is_passed_on_to_the_device():
    backend = FakeBackend()
    _output(backend, latency=0.1).write(_block(0.1))
    assert backend.latency == 0.1


def _wait_for(condition, timeout: float = 3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.005)
    return False


def test_a_thread_feeds_the_device_until_closed():
    backend = FakeBackend()
    out = DeviceOutput(None, prefill_blocks=1, backend=backend)
    for _ in range(4):
        out.write(_block(0.5))
    stream = backend.stream
    assert stream is not None
    assert _wait_for(lambda: len(stream.written) > 5), "the thread keeps writing, silence included"
    assert all(chunk.shape == (256, 2) for chunk in stream.written)
    assert any(np.allclose(chunk, 0.5, atol=0.1) for chunk in stream.written), "the queued audio reaches it"
    out.close()
    count = len(stream.written)
    time.sleep(0.05)
    assert len(stream.written) == count, "no write after close"


def test_late_audio_is_waited_for_while_the_device_still_holds_some():
    backend = FakeBackend()
    out = DeviceOutput(None, prefill_blocks=1, backend=backend)
    for _ in range(3):
        out.write(_block(0.5))
    stream = backend.stream
    assert stream is not None
    assert _wait_for(lambda: len(stream.written) > 3)
    stream.queued = 3000  # the device holds plenty
    time.sleep(0.05)  # the feeder drains what is queued, then has nothing to give
    count = len(stream.written)
    time.sleep(0.1)
    assert len(stream.written) == count, "no silence is written while the device can bridge the gap"
    stream.queued = 0
    assert _wait_for(lambda: len(stream.written) > count), "silence is written once the device runs low"
    out.close()


def test_a_write_after_which_the_device_ran_dry_is_counted():
    backend = FakeBackend()
    out = DeviceOutput(None, backend=backend)
    out.write(_block(0.1))
    stream = backend.stream
    assert stream is not None
    stream.underflow = True
    assert _wait_for(lambda: out.late_writes > 0)
    out.close()


def test_a_failing_device_is_reported():
    backend = FakeBackend()
    out = DeviceOutput(None, backend=backend)
    out.write(_block(0.1))
    stream = backend.stream
    assert stream is not None
    stream.fail = OSError("device unplugged")
    assert _wait_for(lambda: out.error is not None)
    out.close()


def test_device_names_are_listed_without_repeats(monkeypatch):
    sd = MagicMock()
    sd.query_devices.return_value = [
        {"name": "Speakers", "max_output_channels": 2},
        {"name": "Microphone", "max_output_channels": 0},
        {"name": "Speakers", "max_output_channels": 2},
        {"name": "Headphones", "max_output_channels": 2},
    ]
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    assert output_device_names() == ["Speakers", "Headphones"]


def test_device_names_are_empty_without_a_sound_system(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # makes the import raise ImportError
    assert output_device_names() == []


def test_invalid_prefill_is_rejected():
    with pytest.raises(ValueError, match="prefill_blocks"):
        DeviceOutput(None, prefill_blocks=0, backend=FakeBackend())


@pytest.mark.integration
def test_node_plays_blocks_and_stops(graph_with_library_system, monkeypatch):
    mod = importlib.import_module("haybale_audio.nodes.device_out")
    backend = FakeBackend()
    monkeypatch.setattr(
        mod,
        "DeviceOutput",
        lambda device, prefill, latency=None: DeviceOutput(
            device, prefill, backend, latency, threaded=False
        ),
    )
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
