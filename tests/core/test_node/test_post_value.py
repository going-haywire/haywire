"""``BaseNode.post_value``: a node-owned thread hands a port write to the validation scheduler."""

import threading
from typing import Any, List

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _add_node(graph: BaseGraph):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    assert isinstance(wrapper.node, TestAddFloatNode)
    return wrapper.node


def _recording(port: Any, writes: List[tuple], delivered: threading.Event) -> None:
    real_set_value = port.set_value

    def set_value(value, *args, **kwargs):
        writes.append((threading.current_thread(), value))
        result = real_set_value(value, *args, **kwargs)
        delivered.set()
        return result

    port.set_value = set_value


def test_post_value_delivers_on_scheduler_thread(graph_with_library_system: BaseGraph, library_system):
    graph = graph_with_library_system
    node = _add_node(graph)
    graph._validation.adopt_scheduler(ThreadingTimerScheduler())
    writes: List[tuple] = []
    delivered = threading.Event()
    _recording(node.ports["value_a"], writes, delivered)

    posted_from: List[threading.Thread] = []

    def post():
        posted_from.append(threading.current_thread())
        node.post_value("value_a", 7.5)

    poster = threading.Thread(target=post)
    poster.start()
    poster.join(2.0)
    assert delivered.wait(2.0)
    assert writes[0][0] is not posted_from[0]
    assert node.value("value_a") == 7.5


def test_post_value_inline_under_sync_scheduler(graph_with_library_system: BaseGraph, library_system):
    node = _add_node(graph_with_library_system)
    node.post_value("value_a", 3.0)
    assert node.value("value_a") == 3.0


def test_post_value_to_a_missing_port_is_ignored(graph_with_library_system: BaseGraph, library_system):
    node = _add_node(graph_with_library_system)
    node.post_value("no_such_port", 1.0)  # must not raise
