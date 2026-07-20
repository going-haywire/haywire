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
