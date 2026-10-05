"""An element removed and added again within one validation window is recorded as added."""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


def test_a_re_add_after_a_removal_records_the_add():
    from haywire.core.graph.validation import ValidationManager

    store: dict = {}
    for added, removed in (
        (ChangeReason.EDGE_ADDED, ChangeReason.EDGE_REMOVED),
        (ChangeReason.NODE_ADDED, ChangeReason.NODE_REMOVED),
    ):
        ValidationManager._set_reason(None, "x", removed, store)  # type: ignore[arg-type]
        ValidationManager._set_reason(None, "x", added, store)  # type: ignore[arg-type]
        assert store["x"] is added
        # The other order still records the removal.
        ValidationManager._set_reason(None, "x", removed, store)  # type: ignore[arg-type]
        assert store["x"] is removed
        store.clear()


def test_an_edge_removed_and_relinked_in_one_window_reaches_subscribers_as_added(library_system):
    graph = BaseGraph(filestem="Readd", validation_scheduler=ThreadingTimerScheduler())
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    edge = make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()

    seen: list = []
    graph._validation.subscribe(lambda result: seen.append(dict(result.edges)))
    edge_id = edge.edge_id
    graph.remove_edge_wrapper(edge_id)
    make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()

    assert any(changes.get(edge_id) is ChangeReason.EDGE_ADDED for changes in seen), seen
