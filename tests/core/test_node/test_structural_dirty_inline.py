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


def test_a_pass_that_raises_leaves_the_flag_clear() -> None:
    def _boom(_w: NodeWrapper) -> None:
        raise RuntimeError("validation failed")

    wrapper = _wrapper(_boom)

    with pytest.raises(RuntimeError):
        wrapper.mark_as_structuraly_dirty()

    assert wrapper._is_dirty_structural is False
