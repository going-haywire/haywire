"""A node never holds its own lock while it waits for its graph's validation lock.

A validation batch holds the graph's validation lock while it builds and
housekeeps nodes, which takes each node's lock. Anything that takes the two in
the opposite order on another thread deadlocks against it, so every test here
holds the validation lock on this thread, runs one node operation on a worker,
and checks that the node's lock is still free while the worker waits.
"""

import threading
import time
from typing import Any, Callable, cast

import pytest

pytestmark = pytest.mark.integration


def _node_lock_is_free_while_the_worker_waits(wrapper, action: Callable[[], Any]) -> bool:
    """Run *action* on a worker while this thread holds the graph's validation lock.

    Returns whether this thread could take the node's lock meanwhile. On the
    broken order the worker holds it while blocked on the validation lock.
    """
    errors: list[BaseException] = []

    def run() -> None:
        try:
            action()
        except BaseException as e:  # noqa: BLE001 — reported by the test
            errors.append(e)

    with wrapper.graph._validation.lock:
        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        time.sleep(0.2)  # let the worker reach the validation lock
        free = wrapper._lock.acquire(timeout=1.0)
        if free:
            wrapper._lock.release()
    worker.join(timeout=10)
    assert not worker.is_alive(), "the worker never finished"
    assert not errors, errors
    return free


@pytest.fixture
def wrapper(graph_with_library_system, library_system):
    """A validated Add node: registered, and no longer structurally dirty."""
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(TestAddFloatNode.class_identity.registry_key, position=(0, 0))
    graph.force_validation()
    assert wrapper._is_dirty_structural is False
    return wrapper


@pytest.mark.parametrize("method", ["redraw", "mark_layout_changed", "request_graph_reassembly"])
def test_a_graph_notification_holds_no_node_lock(wrapper, method):
    assert _node_lock_is_free_while_the_worker_waits(wrapper, getattr(wrapper, method))


def test_marking_structural_change_takes_the_validation_lock_first(wrapper):
    assert _node_lock_is_free_while_the_worker_waits(wrapper, wrapper.mark_as_structuraly_dirty)


def test_building_takes_the_validation_lock_first(wrapper):
    assert _node_lock_is_free_while_the_worker_waits(wrapper, wrapper.build)


def test_a_hot_reload_takes_the_validation_lock_first(wrapper):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

    event = LifeCycleEvent(
        registry_key=wrapper.registry_key,
        event_type=LifeCycleEventType.CLASS_RELOADED,
        affected_class=TestAddFloatNode,
        library_identity=cast(Any, None),
    )

    assert _node_lock_is_free_while_the_worker_waits(
        wrapper, lambda: wrapper._on_node_lifecycle_event(event)
    )
