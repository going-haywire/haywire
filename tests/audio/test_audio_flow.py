"""Audio blocks through real flows: Audio Clock, Audio Event, Reblock, Audio Event, Recorder."""

import importlib
import time
from types import SimpleNamespace

import pytest
import soundfile as sf

from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph

from tests.conftest import make_edge, make_node

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _add(graph: BaseGraph, module: str, name: str, x: int):
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    return make_node(graph, cls.class_identity.registry_key, position=(x, 0))


def test_clock_through_reblock_to_recorder(graph_with_library_system: BaseGraph, tmp_path, monkeypatch):
    target = tmp_path / "flow.wav"
    monkeypatch.setattr(
        importlib.import_module("haybale_audio.nodes.recorder"), "resolve", lambda path: target
    )
    g = graph_with_library_system
    clock = _add(g, "audio_clock", "AudioClockNode", 0)
    first = _add(g, "audio_event", "AudioEventNode", 200)
    reblock = _add(g, "reblock", "ReblockNode", 400)
    second = _add(g, "audio_event", "AudioEventNode", 600)
    recorder = _add(g, "recorder", "RecorderNode", 800)

    clock.node.clock.block_size = 512
    reblock.node.reblock.block_size = 256
    recorder.node.ports["path"].set_value("flow.wav")

    make_edge(g, first.node_id, "listen_callback", clock.node_id, "callbacks")
    make_edge(g, first.node_id, "block_ready", reblock.node_id, "write")
    make_edge(g, first.node_id, "audio", reblock.node_id, "audio")
    make_edge(g, second.node_id, "listen_callback", reblock.node_id, "callbacks")
    make_edge(g, second.node_id, "block_ready", recorder.node_id, "write")
    make_edge(g, second.node_id, "audio", recorder.node_id, "audio")

    interpreter = Interpreter()
    interpreter.load_graph(g)
    interpreter.start_execution()
    try:
        vm = interpreter.vm
        sizes: dict[str, set[int]] = {}
        deliver = vm.emit_callback

        def record(event_name, payload=None):
            sizes.setdefault(event_name, set()).add(payload["audio"].frames)
            deliver(event_name, payload)

        vm.emit_callback = record  # every emitter reaches the VM through this
        assert clock.node.worker(SimpleNamespace(control_pin="start", emit_callback=record)) == "started"
        time.sleep(0.5)
        clock.node.worker(SimpleNamespace(control_pin="stop", emit_callback=record))
        time.sleep(0.2)  # the queued blocks drain through both flows
    finally:
        interpreter.stop_execution(timeout=2.0)
        interpreter.shutdown()

    assert sizes[first.node_id] == {512}, "the clock delivers 512-sample blocks to the first Audio Event"
    assert sizes[second.node_id] == {256}, "the Reblock delivers 256-sample blocks to the second"
    data, rate = sf.read(str(target), dtype="float32", always_2d=True)
    assert rate == 48000
    assert data.shape[1] == 1
    assert len(data) % 256 == 0, "the Reblock delivers whole 256-sample blocks"
    assert len(data) >= 40 * 256, "512-sample blocks every 10.7 ms for 0.5 s, cut to 256"
