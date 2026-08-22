"""Graph identity (graph_id, filestem) and the `meta` settings bag.

Companion to test_prehydration.py: that covers the on-disk migration, this
covers the in-memory contract the migration targets.
"""

from __future__ import annotations

import json

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler


@pytest.fixture
def graph():
    return BaseGraph(filestem="G", validation_scheduler=SyncScheduler())


# ---------------------------------------------------------------------------
# graph_id — transient instance identity
# ---------------------------------------------------------------------------


def test_graph_id_is_unique_per_instance(graph):
    """Two instances never share an id, even from identical construction."""
    other = BaseGraph(filestem="G", validation_scheduler=SyncScheduler())
    assert graph.graph_id != other.graph_id


def test_graph_id_is_not_serialized(graph):
    """It answers "which loaded instance?" — a file recording one would lie."""
    assert "graph_id" not in graph.to_dict()


def test_graph_id_survives_a_load(graph):
    """Loading data into a live graph does not re-identify the instance."""
    before = graph.graph_id
    graph.load_from_dict({"nodes": {}, "edges": {}})
    assert graph.graph_id == before


def test_two_graphs_from_one_dict_differ(graph):
    """The point of instance identity: same document, two live instances."""
    data = graph.to_dict()
    a = BaseGraph(filestem="A", validation_scheduler=SyncScheduler())
    b = BaseGraph(filestem="B", validation_scheduler=SyncScheduler())
    a.load_from_dict(json.loads(json.dumps(data)))
    b.load_from_dict(json.loads(json.dumps(data)))
    assert a.graph_id != b.graph_id


# ---------------------------------------------------------------------------
# filestem — derived, never trusted from the file
# ---------------------------------------------------------------------------


def test_filestem_seeded_from_name_while_unsaved(graph):
    """An unsaved graph still needs something to show in a tab."""
    assert graph.filestem == "G"


def test_save_stamps_filestem_from_path(graph, tmp_path):
    target = tmp_path / "my_graph.haywire"
    assert graph.save_to_file(str(target))
    assert graph.filestem == "my_graph"


def test_load_stamps_filestem_from_path_not_from_file(graph, tmp_path):
    """A stale stem inside the file must never win over the real filename.

    This is the concrete bug the rule prevents: every shipped fixture stores
    a stale "Untitled N" from creation time.
    """
    source = tmp_path / "real_name.haywire"
    payload = graph.to_dict()
    payload["filestem"] = "Untitled 6"  # the lie
    source.write_text(json.dumps(payload))

    loaded = BaseGraph(filestem="ignored", validation_scheduler=SyncScheduler())
    assert loaded.load_from_file(str(source))
    assert loaded.filestem == "real_name"


def test_filestem_follows_a_save_as(graph, tmp_path):
    graph.save_to_file(str(tmp_path / "first.haywire"))
    graph.save_to_file(str(tmp_path / "second.haywire"))
    assert graph.filestem == "second"


# ---------------------------------------------------------------------------
# created_at / modified_at
# ---------------------------------------------------------------------------


def test_created_at_is_stamped_at_construction(graph):
    """Previously never written — it stayed None for a graph's whole life."""
    assert graph.created_at


def test_modified_at_is_stamped_on_save(graph, tmp_path):
    assert graph.modified_at is None
    graph.save_to_file(str(tmp_path / "g.haywire"))
    assert graph.modified_at


def test_created_at_survives_a_round_trip(graph, tmp_path):
    target = tmp_path / "g.haywire"
    graph.save_to_file(str(target))
    original = graph.created_at

    loaded = BaseGraph(filestem="other", validation_scheduler=SyncScheduler())
    loaded.load_from_file(str(target))
    assert loaded.created_at == original


# ---------------------------------------------------------------------------
# The `meta` bag
# ---------------------------------------------------------------------------


def test_meta_defaults(graph):
    assert graph.meta.label == ""
    assert graph.meta.description == ""
    assert graph.meta.author == ""
    assert graph.meta.version == "1.0.0"


def test_meta_round_trips(graph):
    graph.meta.label = "Face Tracker"
    graph.meta.description = "Tracks faces"
    graph.meta.author = "ann"
    graph.meta.version = "2.1.0"

    loaded = BaseGraph(filestem="other", validation_scheduler=SyncScheduler())
    loaded.load_from_dict(json.loads(json.dumps(graph.to_dict())))

    assert loaded.meta.label == "Face Tracker"
    assert loaded.meta.description == "Tracks faces"
    assert loaded.meta.author == "ann"
    assert loaded.meta.version == "2.1.0"


def test_meta_is_serialized_under_its_own_key(graph):
    """A settings bag nests under {"values", "promoted"} — not a flat dict.

    Settings.from_dict raises PromotedFormatError on the flat shape, so the
    v2 upgrader must emit this structure too.
    """
    graph.meta.label = "L"
    data = graph.to_dict()
    assert data["meta"]["values"]["label"] == "L"
    # Not scattered across the file root any more.
    assert "label" not in data
    assert "description" not in data


def test_absent_meta_falls_back_to_defaults(graph):
    """Pre-v2 files carry no `label`; from_dict must supply the default."""
    graph.load_from_dict({"nodes": {}, "edges": {}, "meta": {"values": {"author": "ann"}, "promoted": {}}})
    assert graph.meta.author == "ann"
    assert graph.meta.label == ""
    assert graph.meta.version == "1.0.0"


def test_reload_does_not_leak_previous_meta(graph):
    """reset_all guard: a reused graph must not keep the old document's values."""
    graph.meta.label = "First"
    graph.load_from_dict({"nodes": {}, "edges": {}, "meta": {"values": {}, "promoted": {}}})
    assert graph.meta.label == ""


def test_settings_bag_for_finds_both_bags(graph):
    """THE lookup seam for graph mirrors — it must know about meta too."""
    from haywire.core.graph.metadata import GraphMetadata
    from haywire.core.graph.properties import GraphProperties

    assert graph.settings_bag_for(GraphProperties) is graph.props
    assert graph.settings_bag_for(GraphMetadata) is graph.meta


def test_cleanup_releases_both_bags(graph):
    """Without meta.cleanup() the bag's registry subscriptions leak per graph."""
    graph.cleanup()  # must not raise; both bags are released
