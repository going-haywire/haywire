"""Audio Clock, File Player and Recorder nodes."""

import importlib
import time
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _node(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _context(pin: str) -> MagicMock:
    ctx = MagicMock()
    ctx.control_pin = pin
    return ctx


def _subscribers() -> dict:
    cb = importlib.import_module("haybale_audio.types.callback").CALLBACK_AUDIO
    return {"edge": cb(name="listener")}


def test_clock_without_subscriber_does_not_start(graph_with_library_system):
    node = _node(graph_with_library_system, "audio_clock", "AudioClockNode")
    assert node.worker(_context("start")) is None
    assert node.ports["status"].get_value() == "No subscriber"


def test_clock_emits_silent_blocks_to_its_subscribers(graph_with_library_system):
    node = _node(graph_with_library_system, "audio_clock", "AudioClockNode")
    node.value = lambda port_id: _subscribers() if port_id == "callbacks" else None
    ctx = _context("start")
    assert node.worker(ctx) == "started"
    time.sleep(0.1)
    assert node.worker(_context("stop")) == "stopped"
    calls = ctx.emit_callback.call_args_list
    assert len(calls) >= 10, "256 samples at 48 kHz is a block every 5.3 ms"
    first = calls[0].kwargs
    assert first["event_name"] == "listener"
    assert first["payload"]["block_number"] == 0
    assert (first["payload"]["audio"].channels, first["payload"]["audio"].frames) == (1, 256)


def test_recorder_writes_blocks_and_closes_on_stop(graph_with_library_system, tmp_path, monkeypatch):
    mod = importlib.import_module("haybale_audio.nodes.recorder")
    target = tmp_path / "rec.wav"
    monkeypatch.setattr(mod, "resolve", lambda path: target)
    node = _node(graph_with_library_system, "recorder", "RecorderNode")
    block = importlib.import_module("haybale_audio.value").AudioBlock.silence(2, 256, 48000)

    for _ in range(3):
        assert node.worker(_context("write"), audio=block, path="vol://rec.wav") == "next"
    assert node.ports["frames"].get_value() == 768
    assert node.worker(_context("stop")) is None

    import soundfile as sf

    data, rate = sf.read(str(target), dtype="float32")
    assert (data.shape, rate) == ((768, 2), 48000)


def test_recorder_write_needs_audio(graph_with_library_system):
    node = _node(graph_with_library_system, "recorder", "RecorderNode")
    with pytest.raises(ValueError, match="audio block and a path"):
        node.worker(_context("write"), audio=None, path="vol://x.wav")


def test_file_player_plays_a_file(graph_with_library_system, tmp_path, monkeypatch):
    import soundfile as sf

    mod = importlib.import_module("haybale_audio.nodes.file_player")
    target = tmp_path / "in.wav"
    sf.write(str(target), np.full((960, 2), 0.25, np.float32), 48000, subtype="FLOAT")  # 20 ms
    monkeypatch.setattr(mod, "resolve", lambda path: target)
    node = _node(graph_with_library_system, "file_player", "FilePlayerNode")
    node.value = lambda port_id: _subscribers() if port_id == "callbacks" else None
    ctx = _context("start")

    assert node.worker(ctx, path="vol://in.wav") == "started"
    time.sleep(0.15)
    node.worker(_context("stop"), path=None)

    payloads = [c.kwargs["payload"] for c in ctx.emit_callback.call_args_list]
    assert [p["audio"].frames for p in payloads] == [256, 256, 256, 192]
    assert node.ports["status"].get_value() == "Stopped"
