"""Saved audio graphs under EXEC_AUDIO: a flow still loads valid, and an edge that is now refused is kept."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


def test_a_saved_audio_flow_loads_with_every_edge_valid(graph_with_library_system):
    """File Players, Audio Clock, Audio Events, Audio Mixer and Device Out, wired as in the example graph."""
    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "audio_flow.haywire"))
    graph.force_validation()

    edges = graph.list_edge_wrappers()
    assert len(edges) == 14
    assert [e.edge_id for e in edges if not e.state.is_valid()] == []


def test_an_edge_from_a_control_node_into_an_audio_pin_loads_invalid_and_is_kept(graph_with_library_system):
    """A graph saved when a Begin Play could drive a Recorder's Write: the edge stays, flagged invalid."""
    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "control_drives_audio.haywire"))
    graph.force_validation()

    (edge,) = graph.list_edge_wrappers()
    assert not edge.state.is_valid()
    assert "No adapter chain found: EXEC → EXEC_AUDIO" in str(edge.state.error_build)
