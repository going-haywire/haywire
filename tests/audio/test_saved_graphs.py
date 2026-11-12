"""Saved audio graphs: a flow still loads, and an edge that is now refused is kept."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


def _mixer(graph):
    (mixer,) = [w.node for w in graph.list_node_wrappers() if type(w.node).__name__ == "AudioMixerNode"]
    return mixer


def test_a_saved_audio_flow_loads_with_its_mixer_inputs_collecting(graph_with_library_system):
    """File Players, Audio Clock, Audio Events, Audio Mixer and Device Out, saved when each mixer input
    had a `Write` pin: the inputs collect their blocks, the `Write` pins are gone, and their edges are
    kept invalid."""
    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "audio_flow.haywire"))
    graph.force_validation()

    mixer = _mixer(graph)
    assert mixer.ports["in_0"].queues_values
    assert mixer.ports["in_1"].queues_values
    assert not [p for p in mixer.ports if p.startswith("write_")]
    edges = graph.list_edge_wrappers()
    assert len(edges) == 13
    invalid = sorted(e.inlet_port_id for e in edges if not e.state.is_valid())
    assert invalid == ["write_0", "write_1"]


def test_mixer_inputs_still_collect_after_a_save_and_load(graph_with_library_system, tmp_path):
    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "audio_flow.haywire"))
    graph.force_validation()
    path = tmp_path / "resaved.haywire"
    assert graph.save_to_file(str(path))

    assert graph.load_from_file(str(path))
    graph.force_validation()

    mixer = _mixer(graph)
    assert mixer.ports["in_0"].queues_values
    assert mixer.ports["in_1"].queues_values


def test_an_edge_from_a_control_node_into_an_audio_pin_loads_invalid_and_is_kept(graph_with_library_system):
    """A graph saved when a Begin Play could drive a Recorder's Write: the edge stays, flagged invalid."""
    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "control_drives_audio.haywire"))
    graph.force_validation()

    (edge,) = graph.list_edge_wrappers()
    assert not edge.state.is_valid()
    assert "No adapter chain found: EXEC → EXEC_AUDIO" in str(edge.state.error_build)
