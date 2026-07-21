"""RevealGraphInstance signal shape."""

import pytest

pytestmark = pytest.mark.unit


def test_reveal_graph_instance_is_session_local():
    """Deliberately NOT cross_session — see the class docstring for why
    (a personal navigation click must not affect a peer session's UI)."""
    from haywire.core.session.signals import RevealGraphInstance

    assert RevealGraphInstance.cross_session is False


def test_reveal_graph_instance_carries_locator_ids():
    from haywire.core.session.signals import RevealGraphInstance

    event = RevealGraphInstance(graph_id="webcam", node_id="n1")
    assert event.graph_id == "webcam"
    assert event.node_id == "n1"
    assert event.edge_id is None


def test_reveal_graph_instance_graph_id_only():
    from haywire.core.session.signals import RevealGraphInstance

    event = RevealGraphInstance(graph_id="webcam")
    assert event.node_id is None
    assert event.edge_id is None
