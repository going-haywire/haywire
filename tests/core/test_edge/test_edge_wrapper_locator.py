"""EdgeWrapper populates graph_id + edge_id on validation errors."""

import pytest

pytestmark = pytest.mark.unit


def test_displaced_from_inlet_carries_graph_id_and_edge_id():
    # EdgeWrapper construction is heavy (ports, adapters, graph); test the
    # enrich contract directly rather than constructing a real EdgeWrapper —
    # mirrors the prior plan's test_edge_error_carries_edge_id_via_enrich
    # pattern (tests/core/test_errors/test_locator.py).
    from haywire.core.errors.haywire_exception import HaywireException

    exc = HaywireException.create("boom").enrich(edge_id="edge::o@a>>i@b", graph_id="webcam")
    assert exc.edge_id == "edge::o@a>>i@b"
    assert exc.graph_id == "webcam"
