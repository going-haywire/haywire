"""Saved audio graphs: a flow still loads, and an edge that is now refused is kept."""

from __future__ import annotations

import logging
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
    kept invalid.
    """
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


def test_a_saved_mixer_input_comes_to_own_its_gain_and_mute(graph_with_library_system, tmp_path):
    """Saved before inputs owned their `Gain` and `Mute`: after loading, removing an input takes them
    along, and a save keeps the link.
    """
    from haywire.core.node.promotion import remove_port

    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "audio_flow.haywire"))
    graph.force_validation()
    mixer = _mixer(graph)
    for n in (0, 1):
        assert mixer.ports[f"gain_{n}"].owner == f"in_{n}"
        assert mixer.ports[f"mute_{n}"].owner == f"in_{n}"

    path = tmp_path / "resaved.haywire"
    assert graph.save_to_file(str(path))
    assert graph.load_from_file(str(path))
    mixer = _mixer(graph)
    assert mixer.ports["gain_1"].owner == "in_1"

    assert remove_port(mixer, "in_1")
    assert not {"in_1", "gain_1", "mute_1"} & set(mixer.ports)


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
    assert "No adapter chain found: EXEC → AUDIO_EXEC" in str(edge.state.error_build)


def test_the_device_in_soak_graph_loads_with_every_edge_valid(graph_with_library_system):
    """Begin Play starts a Device In whose Audio Event plays each block on a Device Out: the graph
    of the PR's soak check.
    """
    graph = graph_with_library_system
    assert graph.load_from_file(str(FIXTURES / "device_in_soak.haywire"))
    graph.force_validation()

    kinds = sorted(type(w.node).__name__ for w in graph.list_node_wrappers())
    assert kinds == ["AudioEventNode", "BeginPlayEventNode", "DeviceInNode", "DeviceOutNode"]
    edges = graph.list_edge_wrappers()
    assert len(edges) == 4
    assert all(e.state.is_valid() for e in edges)


def test_a_graph_saved_with_pooled_audio_settings_loads_without_them(
    graph_with_library_system, tmp_path, caplog
):
    """Saved while Audio Event had Delivery and the block emitters a Backlog (ADR 0097, before block
    streams were never pooled): an Audio Event set to Pooled and a File Player with a Backlog whose
    Size was promoted to a config port. Both load as valid nodes, the Audio Event takes every block,
    the promoted port is gone, and a save drops the old settings.
    """
    from haywire.api import Delivery

    graph = graph_with_library_system
    with caplog.at_level(logging.WARNING):
        assert graph.load_from_file(str(FIXTURES / "pooled_audio_settings.haywire"))
        graph.force_validation()
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], "loads without an error"

    nodes = {type(w.node).__name__: w.node for w in graph.list_node_wrappers()}
    assert set(nodes) == {"FilePlayerNode", "AudioEventNode", "DeviceOutNode"}, "no stand-in nodes"
    assert all(w.state.is_valid() for w in graph.list_node_wrappers())
    assert nodes["AudioEventNode"].event_subscription.delivery is Delivery.EVERY
    player = nodes["FilePlayerNode"]
    assert not hasattr(player, "backlog")
    assert "backlog.size" not in player.ports
    assert all(e.state.is_valid() for e in graph.list_edge_wrappers())

    path = tmp_path / "resaved.haywire"
    assert graph.save_to_file(str(path))
    text = path.read_text()
    assert '"backlog"' not in text
    assert '"delivery"' not in text
