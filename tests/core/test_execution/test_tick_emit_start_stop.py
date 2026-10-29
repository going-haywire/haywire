"""TickEmit start/stop from several threads at once (node-owned thread contract, ADR 0064)."""

import threading
from types import SimpleNamespace
from typing import List

import pytest

from haywire.core.graph.base import BaseGraph

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _tick_node(graph: BaseGraph):
    from haybale_core.nodes.emits.tick_emit import TickEmitNode

    wrapper = make_node(graph, TickEmitNode.class_identity.registry_key)
    assert isinstance(wrapper.node, TickEmitNode)
    return wrapper.node


def _context():
    return SimpleNamespace(control_pin="start", emit_callback=lambda **kwargs: None)


def _tick_threads() -> List[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith("TickEmit-") and t.is_alive()]


def _together(n: int, fn) -> List[BaseException]:
    barrier = threading.Barrier(n)
    errors: List[BaseException] = []

    def run():
        barrier.wait()
        try:
            fn()
        except BaseException as e:  # noqa: BLE001 - the test reports every failure
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5.0)
    return errors


def test_concurrent_start_spawns_one_tick_thread(graph_with_library_system: BaseGraph, library_system):
    node = _tick_node(graph_with_library_system)
    before = len(_tick_threads())
    try:
        assert _together(8, lambda: node._handle_start(_context())) == []
        assert len(_tick_threads()) - before == 1
    finally:
        node._stop_thread()
    assert len(_tick_threads()) == before


def test_concurrent_stop_never_raises(graph_with_library_system: BaseGraph, library_system):
    node = _tick_node(graph_with_library_system)
    node._handle_start(_context())
    assert _together(8, node._stop_thread) == []
    assert node._thread is None
