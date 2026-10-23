"""A node's structural-dirty flag under a scheduler that validates inline.

``SyncScheduler``, and ``LoopScheduler`` with no running loop, run the
validation pass inside ``mark_node_dirty``. The pass housekeeps the node and
clears its flag, so every ``mark_as_structuraly_dirty`` re-checks the node
and the edges on its pins, and a pass that raises leaves the flag clear.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.node.node_wrapper import NodeWrapper, NodeWrapperState

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _wrapper(on_mark: Any) -> NodeWrapper:
    """A registered wrapper whose graph runs ``on_mark(wrapper)`` as its validation pass."""
    wrapper: Any = object.__new__(NodeWrapper)
    wrapper._node_id = "n1"
    wrapper._lock = threading.RLock()
    wrapper._state = NodeWrapperState(is_registered=True)
    wrapper._node_instance = MagicMock()
    wrapper._is_dirty_structural = False
    validation = SimpleNamespace(
        lock=threading.RLock(), mark_node_dirty=lambda node_id, reason: on_mark(wrapper)
    )
    wrapper._graph = SimpleNamespace(_validation=validation)
    return wrapper


def test_the_flag_clears_after_an_inline_pass() -> None:
    wrapper = _wrapper(lambda w: w._housekeeping())

    wrapper.mark_as_structuraly_dirty()

    assert wrapper._is_dirty_structural is False


def test_every_change_reaches_the_validation_pass() -> None:
    passes: list[str] = []

    def _inline(w: NodeWrapper) -> None:
        passes.append("pass")
        w._housekeeping()

    wrapper = _wrapper(_inline)

    wrapper.mark_as_structuraly_dirty()
    wrapper.mark_as_structuraly_dirty()

    assert passes == ["pass", "pass"]
    assert wrapper._node_instance._housekeeping.call_count == 2  # type: ignore[union-attr]


@pytest.mark.integration
def test_edges_waiting_on_pins_added_one_after_another_validate(library_system) -> None:
    """On a real graph that validates inline, each added pin revalidates the edges waiting on it.

    The edges exist before their pins, as after a load or an undo, and no other pass runs
    between the two additions: a flag left set by the first would swallow the second.
    """
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    from haywire.barn.builtin.types import FLOAT
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    from tests.conftest import make_node

    graph = BaseGraph(filestem="inline", validation_scheduler=SyncScheduler())
    try:
        key = TestAddFloatNode.class_identity.registry_key
        source, sink = make_node(graph, key), make_node(graph, key)
        assert isinstance(sink.node, TestAddFloatNode)
        graph.force_validation()

        pins = ["late_0", "late_1"]
        edges = [graph.create_edge_wrapper(source.node_id, "result", sink.node_id, pin) for pin in pins]
        assert all(edge is not None and not edge.is_valid() for edge in edges)

        for index, pin in enumerate(pins):
            sink.node.add(FLOAT.as_inlet(pin, label=f"Late {index}"))

        assert [edge.is_valid() for edge in edges if edge is not None] == [True, True]
        assert sink._is_dirty_structural is False
    finally:
        graph.cleanup()


def test_a_pass_that_raises_leaves_the_flag_clear() -> None:
    def _boom(_w: NodeWrapper) -> None:
        raise RuntimeError("validation failed")

    wrapper = _wrapper(_boom)

    with pytest.raises(RuntimeError):
        wrapper.mark_as_structuraly_dirty()

    assert wrapper._is_dirty_structural is False
