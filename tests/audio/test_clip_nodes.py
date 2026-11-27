"""The clip nodes: AUDIO_CLIP ports, Clip Event, Collect Clip, Clip Segmenter, Clip Queue, and
Clip Player's On Finish."""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haywire.api import Refusal
from tests.conftest import make_edge, make_node
from tests.wait import wait_until

pytestmark = pytest.mark.integration

RATE = 48000
BLOCK = 480  # 10 ms


def _wrapper(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper


def _node(graph: Any, module: str, name: str) -> Any:
    return _wrapper(graph, module, name).node


def _context(pin: str) -> MagicMock:
    ctx = MagicMock()
    ctx.control_pin = pin
    return ctx


def _block(value: float = 0.0, frames: int = BLOCK, channels: int = 1, rate: int = RATE) -> Any:
    block_cls = importlib.import_module("haybale_audio.value").AudioBlock
    return block_cls(np.full((channels, frames), value, np.float32), rate)


def _tone(blocks: int, channels: int = 2) -> list[Any]:
    block_cls = importlib.import_module("haybale_audio.value").AudioBlock
    t = np.arange(blocks * BLOCK) / RATE
    wave = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    data = np.tile(wave, (channels, 1))
    return [block_cls(data[:, n * BLOCK : (n + 1) * BLOCK].copy(), RATE) for n in range(blocks)]


def _silence(blocks: int, channels: int = 2) -> list[Any]:
    return [_block(0.0, channels=channels) for _ in range(blocks)]


# --- AUDIO_CLIP and AUDIO never connect -------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "outlet", "sink", "inlet", "valid"),
    [
        (("collect_clip", "CollectClipNode"), "clip", ("clip_player", "ClipPlayerNode"), "clip", True),
        (("clip_event", "ClipEventNode"), "clip", ("clip_queue", "ClipQueueNode"), "clip", True),
        (("clip_queue", "ClipQueueNode"), "clip_out", ("clip_player", "ClipPlayerNode"), "clip", True),
        (("audio_event", "AudioEventNode"), "audio", ("clip_player", "ClipPlayerNode"), "clip", False),
        (("collect_clip", "CollectClipNode"), "clip", ("device_out", "DeviceOutNode"), "audio", False),
        (("clip_event", "ClipEventNode"), "clip", ("collect_clip", "CollectClipNode"), "audio", False),
    ],
    ids=[
        "collect-to-player",
        "event-to-queue",
        "queue-to-player",
        "block-to-clip",
        "clip-to-device",
        "clip-to-block",
    ],
)
def test_a_clip_port_connects_only_to_a_clip_port(
    graph_with_library_system, source, outlet, sink, inlet, valid
):
    graph = graph_with_library_system
    a = _wrapper(graph, *source)
    b = _wrapper(graph, *sink)
    edge = make_edge(graph, a.node_id, outlet, b.node_id, inlet)
    assert edge.state.is_valid() is valid


# --- Clip Event ---------------------------------------------------------------------------------


def test_clip_event_puts_the_clip_on_its_outlets(graph_with_library_system):
    node = _node(graph_with_library_system, "clip_event", "ClipEventNode")
    clip = _block(0.5, frames=4800)
    ctx = _context("")
    ctx.trigger.payload = {"clip": clip, "timestamp": 1.5, "clip_number": 3}

    assert node.worker(ctx) == "clip_ready"
    assert node.ports["clip"].get_value() is clip
    assert node.ports["timestamp"].get_value() == 1.5
    assert node.ports["clip_number"].get_value() == 3
    assert node.ports["listen_callback"].get_value().name == node.node_id


def test_clip_event_without_a_clip_runs_nothing(graph_with_library_system):
    node = _node(graph_with_library_system, "clip_event", "ClipEventNode")
    ctx = _context("")
    ctx.trigger.payload = {"audio": _block()}
    assert node.worker(ctx) is None


def test_clip_event_subscribes_with_its_delivery_and_queue_settings(graph_with_library_system):
    from haywire.api import Delivery, QueueMode

    node = _node(graph_with_library_system, "clip_event", "ClipEventNode")
    assert node.event_subscription.delivery is Delivery.EVERY
    assert node.event_subscription.max_queue_size == 16

    node.delivery.mode = "Pooled"
    node.dispatch.queue_mode = "Drop (newest only)"
    assert node.event_subscription.delivery is Delivery.POOLED
    assert node.event_subscription.queue_mode is QueueMode.DROP


# --- Collect Clip ------------------------------------------------------------------------------


def test_collect_clip_sends_the_gathered_blocks_on_stop(graph_with_library_system):
    node = _node(graph_with_library_system, "collect_clip", "CollectClipNode")
    block = _block(0.5, frames=1600, rate=16000)

    assert node.worker(_context("stop")) is None  # nothing gathered: nothing sent
    assert node.worker(_context("add"), audio=block, max_seconds=300.0) == "next"
    assert node.worker(_context("add"), audio=block, max_seconds=300.0) == "next"
    assert node.ports["seconds"].get_value() == pytest.approx(0.2)
    assert node.worker(_context("stop")) == "done"

    sent = node.ports["clip"].get_value()
    assert (sent.channels, sent.frames, sent.sample_rate) == (1, 3200, 16000)
    assert node.ports["status"].get_value() == "Sent 0.2 s"
    assert node.worker(_context("stop")) is None  # the next clip starts empty


def test_collect_clip_without_audio_is_refused(graph_with_library_system):
    node = _node(graph_with_library_system, "collect_clip", "CollectClipNode")
    with pytest.raises(Refusal, match="connect an Audio Event"):
        node.worker(_context("add"), audio=None)


def test_collect_clip_drops_blocks_past_max_seconds(graph_with_library_system):
    node = _node(graph_with_library_system, "collect_clip", "CollectClipNode")
    block = _block(frames=1600, rate=16000)
    for _ in range(3):
        assert node.worker(_context("add"), audio=block, max_seconds=0.25) == "next"
    assert node.ports["status"].get_value() == "Full at 0.2 s — 1 blocks dropped"
    node.worker(_context("stop"))
    assert node.ports["clip"].get_value().frames == 3200


# --- Clip Segmenter ----------------------------------------------------------------------------

_SETTINGS = {
    "threshold": 0.01,
    "hangover_ms": 100,
    "preroll_ms": 0,
    "postroll_ms": 0,
    "min_seconds": 0.1,
    "max_seconds": 30.0,
}


def _segmenter(graph: Any, subscribed: bool = True, **settings: Any) -> Any:
    node = _node(graph, "clip_segmenter", "ClipSegmenterNode")
    for name, value in {**_SETTINGS, **settings}.items():
        setattr(node.segmenting, name, value)
    if subscribed:
        cb = importlib.import_module("haybale_audio.types.clip_callback").CLIP_CALLBACK
        subs = {"a": cb(name="worker_a"), "b": cb(name="worker_b")}
        node.value = lambda port_id: subs if port_id == "callbacks" else None
    return node


def _feed(node: Any, ctx: Any, blocks: list[Any]) -> None:
    for block in blocks:
        assert node.worker(ctx, audio=block) == "next"


def test_clip_segmenter_sends_each_clip_in_the_flows_format_in_one_emit(graph_with_library_system):
    node = _segmenter(graph_with_library_system)
    ctx = _context("add")
    _feed(node, ctx, _silence(10) + _tone(50) + _silence(10))
    _feed(node, ctx, _tone(30) + _silence(10))

    calls = ctx.emit_callback.call_args_list
    assert len(calls) == 2
    first = calls[0].kwargs
    assert first["event_name"] == ["worker_a", "worker_b"], "one emit carries every subscriber"
    assert first["backlog"] is node.backlog, "the segmenter owns its pool's backlog"
    clip = first["payload"]["clip"]
    assert (clip.channels, clip.sample_rate, clip.frames) == (2, RATE, 50 * BLOCK), "the format is kept"
    assert first["payload"]["timestamp"] == pytest.approx(0.1)
    assert first["payload"]["clip_number"] == 1
    assert calls[1].kwargs["payload"]["clip_number"] == 2


def test_clip_segmenter_cut_with_nothing_open_sends_nothing(graph_with_library_system):
    node = _segmenter(graph_with_library_system)
    cut = _context("cut")
    assert node.worker(cut, audio=None) is None
    assert cut.emit_callback.call_count == 0


def test_clip_segmenter_cut_sends_the_open_segment_at_once(graph_with_library_system):
    node = _segmenter(graph_with_library_system)
    _feed(node, _context("add"), _tone(30))
    cut = _context("cut")
    node.worker(cut, audio=None)
    (call,) = cut.emit_callback.call_args_list
    assert call.kwargs["payload"]["clip"].frames == 30 * BLOCK


def test_clip_segmenter_keeps_the_post_roll_at_most_the_hang_over(graph_with_library_system):
    node = _segmenter(graph_with_library_system, postroll_ms=50)
    ctx = _context("add")
    _feed(node, ctx, _tone(30) + _silence(10))
    assert ctx.emit_callback.call_args_list[0].kwargs["payload"]["clip"].frames == 35 * BLOCK

    node = _segmenter(graph_with_library_system, postroll_ms=400)  # more than the 100 ms hang-over
    ctx = _context("add")
    _feed(node, ctx, _tone(30) + _silence(10))
    assert ctx.emit_callback.call_args_list[0].kwargs["payload"]["clip"].frames == 40 * BLOCK


def test_clip_segmenter_without_subscriber_sends_nothing(graph_with_library_system):
    node = _segmenter(graph_with_library_system, subscribed=False)
    ctx = _context("add")
    _feed(node, ctx, _tone(20) + _silence(10))
    assert ctx.emit_callback.call_count == 0
    assert node.ports["status"].get_value().endswith("sent 1, discarded 0 (no subscriber)")


def test_clip_segmenter_without_audio_is_an_error(graph_with_library_system):
    node = _segmenter(graph_with_library_system)
    with pytest.raises(Refusal, match="connect an Audio Event"):
        node.worker(_context("add"), audio=None)


# --- Clip Queue --------------------------------------------------------------------------------


def _queue(graph: Any, order: str = "Oldest first", max_clips: int = 16) -> Any:
    node = _node(graph, "clip_queue", "ClipQueueNode")
    node.queue.order = order
    node.queue.max_clips = max_clips
    return node


def _push_all(node: Any, clips: list[Any]) -> None:
    for clip in clips:
        assert node.worker(_context("push"), clip=clip) == "pushed"


def _pop_values(node: Any, times: int) -> list[float | None]:
    out: list[float | None] = []
    for _ in range(times):
        if node.worker(_context("pop")) == "popped":
            out.append(float(node.ports["clip_out"].get_value().data[0, 0]))
        else:
            out.append(None)
    return out


@pytest.mark.parametrize(
    ("order", "expected"),
    [
        ("Oldest first", [1.0, 2.0, 3.0, None]),
        ("Newest first", [3.0, 2.0, 1.0, None]),
        ("Newest only", [3.0, None, None, None]),
    ],
)
def test_clip_queue_pops_in_its_order(graph_with_library_system, order, expected):
    node = _queue(graph_with_library_system, order)
    _push_all(node, [_block(v) for v in (1.0, 2.0, 3.0)])
    assert _pop_values(node, 4) == expected
    assert node.ports["count"].get_value() == 0


def test_clip_queue_drops_the_oldest_past_max_clips(graph_with_library_system):
    node = _queue(graph_with_library_system, max_clips=2)
    _push_all(node, [_block(v) for v in (1.0, 2.0, 3.0)])
    assert node.ports["count"].get_value() == 2
    assert node.ports["status"].get_value() == "2 clips waiting (1 dropped)"
    assert _pop_values(node, 2) == [2.0, 3.0]


def test_clip_queue_clear_empties_it(graph_with_library_system):
    node = _queue(graph_with_library_system)
    _push_all(node, [_block(1.0), _block(2.0)])
    assert node.worker(_context("clear")) == "cleared"
    assert node.ports["count"].get_value() == 0
    assert node.worker(_context("pop")) == "empty"


def test_clip_queue_push_without_a_clip_is_an_error(graph_with_library_system):
    node = _queue(graph_with_library_system)
    with pytest.raises(Refusal, match="connect one to Clip"):
        node.worker(_context("push"), clip=None)


# --- Clip Player's On Finish -------------------------------------------------------------------


def _player(graph: Any, finish: bool = True, **settings: Any) -> Any:
    node = _node(graph, "clip_player", "ClipPlayerNode")
    audio_cb = importlib.import_module("haybale_audio.types.callback").AUDIO_CALLBACK
    values = {
        "callbacks": {"edge": audio_cb(name="listener")},
        "finish_callbacks": {"e": "tick"} if finish else None,
    }
    node.value = lambda port_id: values.get(port_id)
    for name, value in settings.items():
        setattr(node.playback, name, value)
    return node


def _finish_emits(ctx: MagicMock) -> list[Any]:
    return [c.kwargs for c in ctx.emit_callback.call_args_list if c.kwargs["event_name"] == ["tick"]]


def test_clip_player_runs_on_finish_once_a_clip_has_played(graph_with_library_system):
    node = _player(graph_with_library_system)
    ctx = _context("start")
    assert node.worker(ctx, clip=_block(0.25, frames=960, rate=24000)) == "started"
    assert wait_until(lambda: node.ports["status"].get_value() == "Finished")

    assert wait_until(lambda: len(_finish_emits(ctx)) == 1)
    (emit,) = _finish_emits(ctx)
    assert "backlog" not in emit, "On Finish uses the default backlog"


def test_clip_player_runs_no_on_finish_on_stop(graph_with_library_system):
    node = _player(graph_with_library_system)
    ctx = _context("start")
    node.worker(ctx, clip=_block(frames=48000))  # 1 s
    assert wait_until(lambda: ctx.emit_callback.call_count >= 2)
    assert node.worker(_context("stop")) == "stopped"
    assert _finish_emits(ctx) == []
    assert node.ports["status"].get_value() == "Stopped"


def test_clip_player_keeping_running_runs_on_finish_at_each_clips_end(graph_with_library_system):
    node = _player(graph_with_library_system, keep_running=True)
    ctx = _context("start")
    node.worker(ctx, clip=_block(frames=480))
    assert wait_until(lambda: len(_finish_emits(ctx)) == 1)
    node.worker(ctx, clip=_block(frames=480))  # the running pump switches to it
    assert wait_until(lambda: len(_finish_emits(ctx)) == 2)
    node.worker(_context("stop"))


def test_clip_player_stopped_as_the_clip_runs_out_runs_no_on_finish(graph_with_library_system):
    """The reader has ended but the pump's end has not been handled yet when Stop arrives."""
    reader_cls = importlib.import_module("haybale_audio.nodes.clip_player")._ClipReader
    node = _player(graph_with_library_system)
    ctx = _context("start")
    reader = reader_cls(_block(frames=10), 256)
    while reader.read_block() is not None:
        pass
    node.hb_reader = reader
    node.hb_stop()
    node.hb_on_end(ctx, reader, None)
    assert _finish_emits(ctx) == []


def test_keep_running_reports_the_end_with_the_last_block_so_the_next_clip_follows_at_once():
    """A queue chain switches the next clip in on the report: no silent block comes between."""
    reader_cls = importlib.import_module("haybale_audio.nodes.clip_player")._ClipReader
    nxt = _block(2.0, frames=256)
    reader = reader_cls(_block(1.0, frames=300), 256, keep_running=True)
    queue = [nxt]
    reader.on_clip_end = lambda: queue and reader.play(queue.pop())
    blocks = [reader.read_block() for _ in range(4)]
    assert [(b.frames, float(b.data[0, 0])) for b in blocks] == [
        (256, 1.0),
        (44, 1.0),
        (256, 2.0),
        (256, 0.0),
    ]
