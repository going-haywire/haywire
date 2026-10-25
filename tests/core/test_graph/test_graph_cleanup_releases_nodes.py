"""A discarded graph's nodes stop hearing about their class: ``cleanup()`` releases every wrapper."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _subscribed(factory, wrapper) -> bool:
    return wrapper._on_node_lifecycle_event in factory._lifecycle_event_subscribers.get(_key(), [])


def test_cleanup_unsubscribes_every_node_from_the_factory(graph_with_library_system, library_system):
    graph = graph_with_library_system
    factory = library_system.get_node_factory()
    wrappers = [graph.create_node_wrapper(_key()) for _ in range(2)]
    assert all(_subscribed(factory, w) for w in wrappers)
    bags = [w.node.props for w in wrappers]

    graph.cleanup()

    assert not any(_subscribed(factory, w) for w in wrappers)
    assert all(w.is_cleaned_up for w in wrappers)
    assert all(bag._cleaned_up for bag in bags)
