"""Audio Clock, File Player, Clip Player and Recorder nodes."""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import make_node
from tests.wait import wait_until

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
    cb = importlib.import_module("haybale_audio.types.callback").AUDIO_CALLBACK
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
    assert wait_until(lambda: ctx.emit_callback.call_count >= 10)
    assert node.worker(_context("stop")) == "stopped"
    calls = ctx.emit_callback.call_args_list
    assert len(calls) >= 10
    first = calls[0].kwargs
    assert first["event_name"] == ["listener"], "one emit carries every subscriber"
    assert "backlog" not in first, "a block stream is never pooled"
    assert first["payload"]["block_number"] == 0
    assert (first["payload"]["audio"].channels, first["payload"]["audio"].frames) == (1, 256)


def test_recorder_writes_blocks_and_closes_on_stop(graph_with_library_system, tmp_path, monkeypatch):
    mod = importlib.import_module("haybale_audio.nodes.recorder")
    target = tmp_path / "rec.wav"
    monkeypatch.setattr(mod, "resolve_volume_path", lambda path: target)
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
    monkeypatch.setattr(mod, "resolve_volume_path", lambda path: target)
    node = _node(graph_with_library_system, "file_player", "FilePlayerNode")
    node.value = lambda port_id: _subscribers() if port_id == "callbacks" else None
    ctx = _context("start")

    assert node.worker(ctx, path="vol://in.wav") == "started"
    assert wait_until(lambda: ctx.emit_callback.call_count >= 4)  # 20 ms of audio is four blocks
    node.worker(_context("stop"), path=None)

    payloads = [c.kwargs["payload"] for c in ctx.emit_callback.call_args_list]
    assert [p["audio"].frames for p in payloads] == [256, 256, 256, 192]
    assert node.ports["status"].get_value() == "Stopped"


def _clip(value: float, frames: int, channels: int = 1, rate: int = 48000) -> Any:
    block_cls = importlib.import_module("haybale_audio.value").AudioBlock
    return block_cls(np.full((channels, frames), value, np.float32), rate)


def _clip_player(graph: Any, **settings: Any) -> Any:
    node = _node(graph, "clip_player", "ClipPlayerNode")
    node.value = lambda port_id: _subscribers() if port_id == "callbacks" else None
    for name, value in settings.items():
        setattr(node.playback, name, value)
    return node


def _payloads(ctx: MagicMock) -> list[dict]:
    return [c.kwargs["payload"] for c in ctx.emit_callback.call_args_list]


def test_clip_player_plays_a_clip_in_blocks_at_its_own_rate(graph_with_library_system):
    node = _clip_player(graph_with_library_system)
    ctx = _context("start")

    assert node.worker(ctx, clip=_clip(0.25, 960, channels=2, rate=24000)) == "started"  # 40 ms
    assert wait_until(lambda: node.ports["status"].get_value() == "Finished")

    blocks = [p["audio"] for p in _payloads(ctx)]
    assert [b.frames for b in blocks] == [256, 256, 256, 192]
    assert {(b.channels, b.sample_rate) for b in blocks} == {(2, 24000)}
    assert all(np.all(b.data == 0.25) for b in blocks)


def test_clip_player_without_subscriber_does_not_start(graph_with_library_system):
    node = _node(graph_with_library_system, "clip_player", "ClipPlayerNode")
    assert node.worker(_context("start"), clip=_clip(0.25, 960)) is None
    assert node.ports["status"].get_value() == "No subscriber"


def test_clip_player_start_needs_a_clip(graph_with_library_system):
    from haywire.api import Refusal

    node = _clip_player(graph_with_library_system)
    with pytest.raises(Refusal, match="no clip"):
        node.worker(_context("start"), clip=None)


def test_clip_player_start_while_playing_switches_to_the_new_clip(graph_with_library_system):
    node = _clip_player(graph_with_library_system)
    ctx = _context("start")
    node.worker(ctx, clip=_clip(0.25, 48000))  # 1 s
    assert wait_until(lambda: ctx.emit_callback.call_count >= 2)
    pump = node.hb_pump

    assert node.worker(ctx, clip=_clip(0.5, 512)) == "started"
    assert wait_until(lambda: node.ports["status"].get_value() == "Finished")

    assert node.hb_pump is pump, "the running pump plays on: no gap"
    values = [float(p["audio"].data[0, 0]) for p in _payloads(ctx)]
    assert values[-2:] == [0.5, 0.5], "the new clip, from its first block, ends playback"
    assert values.count(0.25) < 48000 // 256, "the old clip is cut"
    numbers = [p["block_number"] for p in _payloads(ctx)]
    assert numbers == list(range(len(numbers)))


def test_clip_player_keep_running_sends_silence_after_the_clip(graph_with_library_system):
    node = _clip_player(graph_with_library_system, keep_running=True)
    ctx = _context("start")
    node.worker(ctx, clip=_clip(0.25, 512))

    assert wait_until(lambda: ctx.emit_callback.call_count >= 6)
    assert node.ports["status"].get_value() == "Silence until the next clip"
    blocks = [p["audio"] for p in _payloads(ctx)]
    assert all(np.all(b.data == 0.25) for b in blocks[:2])
    assert all(not b.data.any() and b.frames == 256 for b in blocks[2:])

    assert node.worker(_context("stop")) == "stopped"
    assert node.ports["status"].get_value() == "Stopped"
    assert node.hb_pump is None


def test_clip_player_loop_repeats_the_clip(graph_with_library_system):
    node = _clip_player(graph_with_library_system, loop=True)
    ctx = _context("start")
    node.worker(ctx, clip=_clip(0.25, 300))

    assert wait_until(lambda: ctx.emit_callback.call_count >= 6)
    node.worker(_context("stop"))
    assert [p["audio"].frames for p in _payloads(ctx)][:4] == [256, 44, 256, 44]


@pytest.mark.unit
def test_clip_reader_keeping_running_adds_no_stall_to_a_mixer_input():
    from haybale_audio.dsp.buffer import PullBuffer

    reader_cls = importlib.import_module("haybale_audio.nodes.clip_player")._ClipReader
    ends: list[int] = []
    reader = reader_cls(
        _clip(0.5, 24000, rate=24000), 128, keep_running=True, on_clip_end=lambda: ends.append(1)
    )
    mixer_input = PullBuffer(48000, 2, 256, prefill_blocks=8)
    for tick in range(1200):  # about 6.4 s of 48 kHz ticks, a 24 kHz block for each
        if tick == 600:
            assert reader.play(_clip(0.5, 12000, rate=24000))
        mixer_input.write(reader.read_block())
        mixer_input.read(256)

    assert mixer_input.restarts == 0
    assert len(ends) == 2, "each clip's end is reported once"
