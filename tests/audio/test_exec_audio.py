"""EXEC_AUDIO: an EXEC that audio flows drive standard control nodes with, and the reverse refused."""

import importlib
from typing import Any

import pytest
from haywire.barn.builtin.types import EXEC
from haywire.barn.builtin.wires import ControlWire
from haywire.core.adapter.factory import AdapterFactory
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.types.wire import WireRole, wire_type_of

from haybale_audio.types.exec_audio import EXEC_AUDIO
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.unit


def _chain(source: type, sink: type) -> tuple[object, str | None]:
    return AdapterFactory(AdapterRegistry()).create_chain(source, sink, "edge")  # type: ignore[arg-type]


def test_it_is_an_exec_on_the_control_wire():
    assert issubclass(EXEC_AUDIO, EXEC)
    wire = wire_type_of(EXEC_AUDIO)
    assert wire is ControlWire
    assert wire.role is WireRole.SEQUENCE


def test_it_is_registered_as_a_type_of_the_audio_library():
    assert EXEC_AUDIO.class_identity.registry_key == "haybale-audio:type:EXEC_AUDIO"
    assert EXEC_AUDIO.class_identity.label == "Audio Execution Signal"


def test_an_audio_flow_connects_to_an_audio_flow():
    chain, error = _chain(EXEC_AUDIO, EXEC_AUDIO)
    assert (chain is not None, error) == (True, None)


def test_an_audio_flow_can_drive_a_standard_control_node():
    chain, error = _chain(EXEC_AUDIO, EXEC)
    assert (chain is not None, error) == (True, None)


def test_a_standard_control_node_cannot_drive_an_audio_flow():
    chain, error = _chain(EXEC, EXEC_AUDIO)
    assert chain is None
    assert error is not None
    assert "EXEC" in error


def test_its_default_is_an_empty_payload():
    assert EXEC_AUDIO.create_default().value == {}


# --- the table, through real nodes and real edge validation ----------------------------------------


def _audio(graph: Any, module: str, name: str):
    cls = getattr(importlib.import_module(f"haybale_audio.nodes.{module}"), name)
    return make_node(graph, cls.class_identity.registry_key, position=(0, 0))


def _testing(graph: Any, module: str, name: str):
    cls = getattr(importlib.import_module(f"haybale_testing.nodes.testbed.{module}"), name)
    return make_node(graph, cls.class_identity.registry_key, position=(0, 0))


@pytest.mark.integration
def test_an_audio_flow_chains_from_an_event_through_the_nodes(graph_with_library_system):
    g = graph_with_library_system
    event = _audio(g, "audio_event", "AudioEventNode")
    reblock = _audio(g, "reblock", "ReblockNode")
    recorder = _audio(g, "recorder", "RecorderNode")
    assert make_edge(g, event.node_id, "block_ready", reblock.node_id, "write").state.is_valid()
    assert make_edge(g, reblock.node_id, "next", recorder.node_id, "write").state.is_valid()


@pytest.mark.integration
def test_an_event_can_drive_a_standard_control_node_in_a_graph(graph_with_library_system):
    g = graph_with_library_system
    event = _audio(g, "audio_event", "AudioEventNode")
    sink = _testing(g, "print_node", "TestPrintNode")
    assert make_edge(g, event.node_id, "block_ready", sink.node_id, "exec").state.is_valid()


@pytest.mark.integration
def test_a_begin_play_cannot_drive_a_recorder_in_a_graph(graph_with_library_system):
    g = graph_with_library_system
    begin = _testing(g, "begin_play_node", "TestBeginPlayNode")
    recorder = _audio(g, "recorder", "RecorderNode")
    edge = make_edge(g, begin.node_id, "exec", recorder.node_id, "write")
    assert not edge.state.is_valid()
    assert "No adapter chain found: EXEC → EXEC_AUDIO" in str(edge.state.error_build)


@pytest.mark.integration
def test_a_standard_control_node_still_starts_and_stops_audio_nodes(graph_with_library_system):
    g = graph_with_library_system
    begin = _testing(g, "begin_play_node", "TestBeginPlayNode")
    player = _audio(g, "file_player", "FilePlayerNode")
    recorder = _audio(g, "recorder", "RecorderNode")
    assert make_edge(g, begin.node_id, "exec", player.node_id, "start").state.is_valid()
    assert make_edge(g, player.node_id, "started", recorder.node_id, "stop").state.is_valid()


@pytest.mark.integration
def test_a_node_after_the_exit_cannot_re_enter_the_audio_flow(graph_with_library_system):
    g = graph_with_library_system
    event = _audio(g, "audio_event", "AudioEventNode")
    sink = _testing(g, "print_node", "TestPrintNode")
    recorder = _audio(g, "recorder", "RecorderNode")
    assert make_edge(g, event.node_id, "block_ready", sink.node_id, "exec").state.is_valid()
    assert not make_edge(g, sink.node_id, "done", recorder.node_id, "write").state.is_valid()


@pytest.mark.integration
def test_a_group_boundary_slot_dragged_onto_an_audio_pin_becomes_an_audio_pin(graph_with_library_system):
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode
    from haywire.barn.builtin.types import ADD
    from haywire.core.graph.scheduler import SyncScheduler
    from haywire.core.graph.subgraph import SubgraphDefinition

    from haybale_audio.nodes.recorder import RecorderNode

    definition = graph_with_library_system.add_subgraph(
        SubgraphDefinition(key="sg_audio", label="Group", validation_scheduler=SyncScheduler())
    )
    boundary = definition.create_node_wrapper(SubgraphInputNode.class_identity.registry_key)
    interior = definition.create_node_wrapper(RecorderNode.class_identity.registry_key)
    assert boundary is not None
    assert interior is not None
    slot = next(p for p in boundary.node.get_all_ports() if p.type_cls and issubclass(p.type_cls, ADD))

    definition.create_edge_wrapper(boundary.node_id, slot.id, interior.node_id, "write")
    definition.force_validation()

    assert boundary.node.ports[slot.id].type_cls is EXEC_AUDIO
