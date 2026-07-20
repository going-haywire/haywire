"""Locator fields + navigation predicates on HaywireException."""

import pytest

from haywire.core.errors.haywire_exception import HaywireException

pytestmark = pytest.mark.unit


def _exc(msg: str = "boom", **kwargs) -> HaywireException:
    return HaywireException.create(msg, **kwargs)


def test_locator_fields_default_none():
    exc = _exc()
    assert exc.graph_id is None
    assert exc.edge_id is None
    assert exc.node_id is None  # pre-existing field, still defaults None


def test_enrich_sets_graph_and_edge_id():
    exc = _exc().enrich(graph_id="/tmp/g.haywire", edge_id="edge::o@n1>>i@n2")
    assert exc.graph_id == "/tmp/g.haywire"
    assert exc.edge_id == "edge::o@n1>>i@n2"


def test_enrich_is_chainable_with_locator():
    exc = _exc().enrich(graph_id="/tmp/g.haywire").enrich(node_id="node_1")
    assert exc.graph_id == "/tmp/g.haywire"
    assert exc.node_id == "node_1"


def test_can_open_component_requires_registry_key():
    assert _exc().can_open_component() is False
    assert _exc(registry_key="lib:node:Foo").can_open_component() is True


def test_can_reveal_instance_requires_graph_plus_node_or_edge():
    # graph_id alone is not enough — need something to select inside it.
    assert _exc().enrich(graph_id="/tmp/g.haywire").can_reveal_instance() is False
    # graph + node
    assert _exc().enrich(graph_id="/tmp/g.haywire", node_id="n1").can_reveal_instance() is True
    # graph + edge
    assert _exc().enrich(graph_id="/tmp/g.haywire", edge_id="edge::o@a>>i@b").can_reveal_instance() is True
    # node without graph — can't reveal (don't know which graph)
    assert _exc().enrich(node_id="n1").can_reveal_instance() is False


def test_to_dict_includes_locator_fields():
    exc = _exc().enrich(graph_id="/tmp/g.haywire", node_id="n1", edge_id="edge::o@a>>i@b")
    d = exc.to_dict()
    assert d["graph_id"] == "/tmp/g.haywire"
    assert d["node_id"] == "n1"
    assert d["edge_id"] == "edge::o@a>>i@b"


def test_from_dict_round_trips_locator():
    exc = _exc().enrich(graph_id="/tmp/g.haywire", node_id="n1")
    restored = HaywireException.from_dict(exc.to_dict())
    assert restored.graph_id == "/tmp/g.haywire"
    assert restored.node_id == "n1"


def test_edge_error_carries_edge_id_via_enrich():
    # The edge_wrapper validation paths call .enrich(edge_id=<self.edge_id>).
    # This is the contract those sites must satisfy.
    exc = _exc("bad edge").enrich(edge_id="edge::out@n1>>in@n2")
    assert exc.edge_id == "edge::out@n1>>in@n2"
    assert exc.can_reveal_instance() is False  # no graph_id yet
    exc.enrich(graph_id="/tmp/g.haywire")
    assert exc.can_reveal_instance() is True
