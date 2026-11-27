"""DeviceInput and the Device In node, against a fake input device."""

from __future__ import annotations

import importlib
import sys
import threading
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haybale_audio.io.device import MIN_QUEUE_BLOCKS, DeviceInput, InputCallback, input_device_names
from tests.conftest import make_node
from tests.wait import wait_until

pytestmark = pytest.mark.unit


class FakeInputStream:
    """Stands in for the device: the test calls ``feed`` where the device would call back."""

    def __init__(self, channels: int, block_size: int, callback: InputCallback) -> None:
        self.state = "open"
        self.channels = channels
        self.block_size = block_size
        self.callback = callback
        self.latency = 0.0053

    def start(self) -> None:
        self.state = "started"

    def stop(self) -> None:
        self.state = "stopped"

    def close(self) -> None:
        self.state = "closed"

    def feed(self, value: float = 0.0, frames: int | None = None, overflowed: bool = False) -> None:
        """Deliver one interleaved (frames, channels) block, as PortAudio does."""
        data = np.full((frames or self.block_size, self.channels), value, dtype=np.float32)
        self.callback(data, overflowed)


class FakeInputBackend:
    def __init__(self, rate: int = 48000, channels: int = 2) -> None:
        self.rate, self.channels = rate, channels
        self.stream: FakeInputStream | None = None
        self.opened: tuple[Any, int, int, int] | None = None

    def device_info(self, device: str | int | None) -> tuple[int, int]:
        return self.rate, self.channels

    def open(
        self,
        device: str | int | None,
        sample_rate: int,
        channels: int,
        block_size: int,
        callback: InputCallback,
    ) -> FakeInputStream:
        self.opened = (device, sample_rate, channels, block_size)
        self.stream = FakeInputStream(channels, block_size, callback)
        return self.stream


def _opened(backend: FakeInputBackend, **kwargs: Any) -> tuple[DeviceInput, FakeInputStream]:
    device = DeviceInput(None, backend=backend, **kwargs)
    device.open()
    assert backend.stream is not None
    return device, backend.stream


def test_blocks_come_at_the_device_rate_and_channels():
    device, stream = _opened(FakeInputBackend(rate=44100, channels=2))
    assert stream.state == "started"
    stream.feed(0.5)
    block = device.read()
    assert block is not None
    assert (block.sample_rate, block.channels, block.frames) == (44100, 2, 256)
    assert block.data.flags.c_contiguous, "planar (channels, frames), owned by the block"
    assert np.allclose(block.data, 0.5)
    device.close()


def test_asked_rate_and_channels_are_passed_to_the_device_and_limited_to_it():
    backend = FakeInputBackend(rate=48000, channels=2)
    device, _ = _opened(backend, sample_rate=16000, channels=6, block_size=128)
    assert backend.opened == (None, 16000, 2, 128)
    assert (device.sample_rate, device.channels) == (16000, 2)
    device.close()


def test_the_callback_keeps_its_own_copy_of_the_block():
    device, stream = _opened(FakeInputBackend(channels=1))
    data = np.ones((256, 1), dtype=np.float32)
    stream.callback(data, False)
    data[:] = 0  # PortAudio reuses its buffer for the next block
    block = device.read()
    assert block is not None
    assert np.allclose(block.data, 1.0)
    device.close()


def test_a_full_queue_loses_the_block_and_counts_it():
    device, stream = _opened(FakeInputBackend(), block_size=48000)  # 1 s blocks: the queue's floor
    for _ in range(MIN_QUEUE_BLOCKS + 3):
        stream.feed()
    assert device.lost == 3
    for _ in range(MIN_QUEUE_BLOCKS):
        assert device.read() is not None
    device.close()


def test_device_overflows_and_the_real_block_size_are_recorded():
    device, stream = _opened(FakeInputBackend(), block_size=256)
    stream.feed(frames=512, overflowed=True)
    assert device.overflows == 1
    assert device.block_frames == 512
    assert device.latency == pytest.approx(0.0053)
    device.close()


def test_close_stops_the_stream_and_ends_a_waiting_read():
    device, stream = _opened(FakeInputBackend())
    result: list[Any] = []
    reader = threading.Thread(target=lambda: result.append(device.read()))
    reader.start()
    device.close()
    reader.join(timeout=5)
    assert not reader.is_alive()
    assert result == [None]
    assert stream.state == "closed"


def test_input_device_names_are_listed_without_repeats(monkeypatch):
    sd = MagicMock()
    sd.query_devices.return_value = [
        {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2},
        {"name": "Microphone", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "Microphone", "max_input_channels": 1, "max_output_channels": 0},
        {"name": "Interface", "max_input_channels": 8, "max_output_channels": 8},
    ]
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    assert input_device_names() == ["Microphone", "Interface"]


def test_input_device_names_are_empty_without_a_sound_system(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # makes the import raise ImportError
    assert input_device_names() == []


# --- the node ----------------------------------------------------------------


def _context(pin: str) -> MagicMock:
    ctx = MagicMock()
    ctx.control_pin = pin
    return ctx


def _node(graph: Any, monkeypatch: pytest.MonkeyPatch, backend: FakeInputBackend) -> Any:
    mod = importlib.import_module("haybale_audio.nodes.device_in")
    monkeypatch.setattr(
        mod,
        "DeviceInput",
        lambda device, rate, channels, block_size: DeviceInput(device, rate, channels, block_size, backend),
    )
    cls = mod.DeviceInNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _subscribed(node: Any) -> None:
    cb = importlib.import_module("haybale_audio.types.callback").AUDIO_CALLBACK
    node.value = lambda port_id: {"edge": cb(name="listener")} if port_id == "callbacks" else None


@pytest.mark.integration
def test_node_without_subscriber_does_not_open_the_device(graph_with_library_system, monkeypatch):
    backend = FakeInputBackend()
    node = _node(graph_with_library_system, monkeypatch, backend)
    assert node.worker(_context("start")) is None
    assert backend.stream is None
    assert node.ports["status"].get_value() == "No subscriber"


@pytest.mark.integration
def test_node_delivers_device_blocks_to_its_subscribers_and_stops(graph_with_library_system, monkeypatch):
    backend = FakeInputBackend(rate=44100, channels=2)
    node = _node(graph_with_library_system, monkeypatch, backend)
    _subscribed(node)
    ctx = _context("start")
    assert node.worker(ctx) == "started"
    assert backend.opened == (None, 44100, 2, 256), "device default rate, all channels, block 256"
    stream = backend.stream
    assert stream is not None
    for value in (0.1, 0.2, 0.3):
        stream.feed(value)
    assert wait_until(lambda: ctx.emit_callback.call_count >= 3)
    assert node.worker(_context("stop")) == "stopped"
    assert stream.state == "closed"
    assert node.ports["status"].get_value() == "Stopped"

    payloads = [c.kwargs["payload"] for c in ctx.emit_callback.call_args_list]
    assert ctx.emit_callback.call_args_list[0].kwargs["event_name"] == ["listener"]
    assert ctx.emit_callback.call_args_list[0].kwargs["backlog"] is node.backlog
    assert [p["block_number"] for p in payloads] == [0, 1, 2]
    assert [round(float(p["audio"].data[0, 0]), 1) for p in payloads] == [0.1, 0.2, 0.3]
    assert all((p["audio"].sample_rate, p["audio"].channels) == (44100, 2) for p in payloads)


@pytest.mark.integration
def test_node_settings_choose_rate_and_channels(graph_with_library_system, monkeypatch):
    backend = FakeInputBackend(rate=48000, channels=2)
    node = _node(graph_with_library_system, monkeypatch, backend)
    _subscribed(node)
    node.recording.sample_rate = "16000"
    node.recording.channels = "1"
    node.recording.block_size = 512
    assert node.worker(_context("start")) == "started"
    assert backend.opened == (None, 16000, 1, 512)
    node.worker(_context("stop"))


@pytest.mark.integration
def test_node_closes_the_device_on_teardown(graph_with_library_system, monkeypatch):
    backend = FakeInputBackend()
    node = _node(graph_with_library_system, monkeypatch, backend)
    _subscribed(node)
    node.worker(_context("start"))
    pump = node.hb_pump
    node.on_teardown()
    assert backend.stream is not None
    assert backend.stream.state == "closed"
    assert not pump.running


@pytest.mark.integration
def test_node_closes_the_device_on_shutdown(graph_with_library_system, monkeypatch):
    backend = FakeInputBackend()
    node = _node(graph_with_library_system, monkeypatch, backend)
    _subscribed(node)
    node.worker(_context("start"))
    node.on_shutdown(_context("shutdown"))
    assert backend.stream is not None
    assert backend.stream.state == "closed"
    assert node.hb_pump is None


def test_status_shows_the_real_block_size_latency_and_losses():
    status_text = importlib.import_module("haybale_audio.nodes.device_in").status_text
    device, stream = _opened(FakeInputBackend(rate=48000, channels=2), block_size=256)
    stream.feed()
    assert status_text(device) == (
        "Listening 2 ch at 48000 Hz, blocks 256, latency 5.3 ms, lost 0, overflow 0"
    )
    stream.feed(frames=512, overflowed=True)
    assert "blocks 512 (asked 256)" in status_text(device)
    assert "overflow 1" in status_text(device)
    device.close()


# --- refreshing the device list -----------------------------------------------


class _FakeStream:
    def __init__(self) -> None:
        self.closed = False


def _fake_sounddevice() -> Any:
    sd = MagicMock()
    sd.InputStream = type("InputStream", (_FakeStream,), {})
    sd.OutputStream = type("OutputStream", (_FakeStream,), {})
    sd.RawInputStream = type("RawInputStream", (_FakeStream,), {})
    sd.RawOutputStream = type("RawOutputStream", (_FakeStream,), {})
    return sd


def test_refresh_restarts_portaudio_when_no_stream_is_open(monkeypatch):
    from haybale_audio.io.device import refresh_devices

    sd = _fake_sounddevice()
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    assert refresh_devices()
    sd._terminate.assert_called_once()
    sd._initialize.assert_called_once()


def test_refresh_leaves_portaudio_running_while_a_stream_is_open(monkeypatch):
    from haybale_audio.io.device import refresh_devices

    sd = _fake_sounddevice()
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    stream = sd.OutputStream()
    assert not refresh_devices(), "a restart would end the open stream"
    sd._terminate.assert_not_called()
    stream.closed = True
    assert refresh_devices()
    sd._terminate.assert_called_once()


def test_refresh_without_a_sound_system_does_nothing(monkeypatch):
    from haybale_audio.io.device import refresh_devices

    monkeypatch.setitem(sys.modules, "sounddevice", None)  # makes the import raise ImportError
    assert not refresh_devices()


def test_both_device_settings_offer_a_refresh_button():
    for module, cls in (("device_in", "DeviceInSettings"), ("device_out", "DeviceOutSettings")):
        settings = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), cls)
        assert callable(settings.device.widget_config["properties"]["refresh"]), module


# --- a device that does not open ------------------------------------------------


class _PortAudioError(Exception):
    """Stands in for ``sounddevice.PortAudioError``: (message, code)."""


_UNAVAILABLE = _PortAudioError("Error opening OutputStream: Device unavailable", -9985)
_BAD_RATE = _PortAudioError("Error opening InputStream: Invalid sample rate", -9997)
_BAD_CHANNELS = _PortAudioError("Error opening InputStream: Invalid number of channels", -9998)
_HOST_ERROR = _PortAudioError("Unanticipated host error", -9999)


def _failing_sounddevice(error: Exception) -> Any:
    sd = _fake_sounddevice()
    sd.PortAudioError = _PortAudioError
    sd.query_devices.return_value = []

    def fail(**kwargs: Any) -> None:
        raise error

    sd.InputStream = sd.OutputStream = fail
    return sd


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_UNAVAILABLE, "choose the entry without 'hw:'"),
        (_BAD_RATE, "does not support this sample rate"),
        (_BAD_CHANNELS, "choose fewer"),
        (_HOST_ERROR, "Unanticipated host error"),
    ],
    ids=["unavailable", "sample rate", "channels", "other"],
)
def test_a_device_that_does_not_open_is_refused_in_plain_words(monkeypatch, error, expected):
    from haybale_audio.io.device import SoundDeviceBackend, SoundDeviceInputBackend
    from haywire.api import Refusal

    monkeypatch.setitem(sys.modules, "sounddevice", _failing_sounddevice(error))
    with pytest.raises(Refusal, match="Cannot open the output device 'Speakers'") as out:
        SoundDeviceBackend().open("Speakers", 48000, 2)
    assert expected in out.value.message
    with pytest.raises(Refusal, match="Cannot open the default input device") as into:
        SoundDeviceInputBackend().open(None, 48000, 2, 256, lambda data, overflowed: None)
    assert expected in into.value.message


def test_a_device_name_that_is_not_there_says_to_refresh(monkeypatch):
    from haybale_audio.io.device import SoundDeviceInputBackend
    from haywire.api import Refusal

    sd = _failing_sounddevice(_PortAudioError("unused", -1))
    sd.query_devices.side_effect = ValueError("No input device matching 'Headset'")
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    with pytest.raises(Refusal, match="press refresh"):
        SoundDeviceInputBackend().device_info("Headset")


@pytest.mark.integration
def test_node_shows_why_the_device_did_not_open(graph_with_library_system, monkeypatch):
    from haywire.api import Refusal

    class _BusyBackend(FakeInputBackend):
        def open(self, *args: Any, **kwargs: Any) -> FakeInputStream:
            raise Refusal("Cannot open the default input device: it is unavailable.")

    node = _node(graph_with_library_system, monkeypatch, _BusyBackend())
    _subscribed(node)
    with pytest.raises(Refusal):
        node.worker(_context("start"))
    status = node.ports["status"].get_value()
    assert status == "Error: Cannot open the default input device: it is unavailable."
    assert node.hb_input is None


@pytest.mark.integration
def test_device_out_shows_why_the_device_did_not_open(graph_with_library_system, monkeypatch):
    from haybale_audio.io.device import DeviceOutput
    from haywire.api import Refusal

    mod = importlib.import_module("haybale_audio.nodes.device_out")

    class _BusyOutput:
        def device_info(self, device: Any) -> tuple[int, int]:
            return 48000, 2

        def open(self, *args: Any, **kwargs: Any) -> Any:
            raise Refusal("Cannot open the default output device: it is unavailable.")

    monkeypatch.setattr(
        mod,
        "DeviceOutput",
        lambda device, prefill, latency=None: DeviceOutput(
            device, prefill, _BusyOutput(), latency, threaded=False
        ),
    )
    key = mod.DeviceOutNode.class_identity.registry_key
    wrapper = make_node(graph_with_library_system, key, position=(0, 0))
    node = wrapper.node
    block = importlib.import_module("haybale_audio.value").AudioBlock.silence(2, 256, 48000)
    with pytest.raises(Refusal):
        node.worker(_context("write"), audio=block)
    assert node.ports["status"].get_value().startswith("Error: Cannot open the default output device")
    assert isinstance(node, mod.DeviceOutNode)
    assert node.hb_output is None
