"""Every graph of one tree validates under one lock, so a host and its Subgraphs never validate at once."""

import threading
import time

import pytest

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.types import ChangeReason

pytestmark = pytest.mark.integration


def test_a_subgraph_validates_under_its_hosts_lock(graph_with_library_system):
    graph = graph_with_library_system

    definition = graph.add_subgraph(SubgraphDefinition(key="sg_lock", label="G"))

    assert definition._validation.lock is graph._validation.lock


def test_a_nested_subgraph_added_first_shares_the_roots_lock(graph_with_library_system):
    graph = graph_with_library_system
    outer = SubgraphDefinition(key="sg_outer", label="Outer")
    inner = outer.add_subgraph(SubgraphDefinition(key="sg_inner", label="Inner"))

    graph.add_subgraph(outer)

    assert inner._validation.lock is graph._validation.lock


def test_a_subgraph_batch_waits_while_its_host_validates(graph_with_library_system):
    graph = graph_with_library_system
    definition = graph.add_subgraph(SubgraphDefinition(key="sg_wait", label="G"))
    worker = threading.Thread(
        target=lambda: definition._validation.mark_graph_dirty(ChangeReason.GRAPH_REQUIRE_REASSEMBLY),
        daemon=True,
    )

    with graph._validation.lock:
        worker.start()
        time.sleep(0.2)
        assert worker.is_alive(), "the Subgraph marked itself dirty while its host held the lock"
    worker.join(timeout=10)

    assert not worker.is_alive()
