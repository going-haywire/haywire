"""Load and save failures reach the error ledger; the fallbacks stay."""

import json
import os

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.edge.edge_wrapper import EdgeWrapper

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=20)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def _graph() -> BaseGraph:
    return BaseGraph(filestem="g", validation_scheduler=SyncScheduler())


def _two_linked_nodes(library_system):
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    key = EdgeLinkTestNode.class_identity.registry_key
    g = _graph()
    a = make_node(g, key, position=(0, 0))
    b = make_node(g, key, position=(200, 0))
    make_edge(g, a.node_id, "bool_outlet", b.node_id, "bool_inlet")
    return g, a, b


def _entries(ledger):
    return list(ledger.query().entries)


def test_unreadable_file_is_recorded(library_system, ledger, tmp_path):
    bad = tmp_path / "bad.haywire"
    bad.write_text("{not json", encoding="utf-8")
    assert _graph().load_from_file(str(bad)) is False
    entries = _entries(ledger)
    assert len(entries) == 1
    assert entries[0].operation == "Load graph"
    assert entries[0].error_context["path"] == str(bad)


def test_failing_node_is_skipped_and_recorded(library_system, ledger, monkeypatch):
    g, a, b = _two_linked_nodes(library_system)
    data = g.to_dict(include_data=False)
    data["edges"] = {}
    original = NodeWrapper.build

    def build(self, *args, **kwargs):
        if self.node_id == a.node_id:
            raise RuntimeError("boom")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(NodeWrapper, "build", build)
    g2 = _graph()
    assert g2.load_from_dict(data) is True
    assert g2.get_node_wrapper(a.node_id) is None
    assert g2.get_node_wrapper(b.node_id) is not None
    entries = _entries(ledger)
    assert len(entries) == 1
    assert (entries[0].operation, entries[0].node_id) == ("Load graph", a.node_id)
    assert entries[0].graph_id == g2.graph_id


def test_failing_edge_is_skipped_and_recorded(library_system, ledger, monkeypatch):
    g, a, b = _two_linked_nodes(library_system)
    data = g.to_dict(include_data=False)
    edge_id = next(iter(data["edges"]))

    def build(self, *args, **kwargs):
        raise RuntimeError("edge boom")

    monkeypatch.setattr(EdgeWrapper, "build", build)
    g2 = _graph()
    assert g2.load_from_dict(data) is True
    assert len(g2.edge_wrappers) == 0
    entries = _entries(ledger)
    assert len(entries) == 1
    assert (entries[0].operation, entries[0].edge_id) == ("Load graph", edge_id)


def test_save_into_read_only_directory_is_recorded(library_system, ledger, tmp_path):
    g, _a, _b = _two_linked_nodes(library_system)
    target_dir = tmp_path / "ro"
    target_dir.mkdir()
    os.chmod(target_dir, 0o500)
    try:
        target = target_dir / "g.haywire"
        assert g.save_to_file(str(target)) is False
    finally:
        os.chmod(target_dir, 0o700)
    entries = _entries(ledger)
    assert len(entries) == 1
    assert entries[0].operation == "Save graph"
    assert entries[0].error_context["path"] == str(target)


def test_round_trip_records_nothing(library_system, ledger, tmp_path):
    g, _a, _b = _two_linked_nodes(library_system)
    path = tmp_path / "ok.haywire"
    assert g.save_to_file(str(path)) is True
    assert json.loads(path.read_text(encoding="utf-8"))
    assert _graph().load_from_file(str(path)) is True
    assert ledger.query().total == 0
