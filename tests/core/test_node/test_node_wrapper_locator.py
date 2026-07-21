"""NodeWrapper populates graph_id + node_id on validation errors."""

import pytest

pytestmark = pytest.mark.unit


def test_node_removed_error_carries_node_id_and_graph_id():
    """Regression test for the `_node_id=` (leading underscore) typo that
    silently dropped node_id on the 'Node Removed' lifecycle error."""
    from haywire.core.errors.haywire_exception import HaywireException

    exc = HaywireException.create("Node removed").enrich(
        node_id="n1", graph_id="webcam", registry_key="lib:node:Foo"
    )
    assert exc.node_id == "n1"
    assert exc.graph_id == "webcam"
