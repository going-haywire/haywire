"""A compile on its own leaves nothing running (#228).

``GraphEntry.compile()`` (Farmhand's ``compile_graph``) assembles the graph without
starting it: no runner starts and no node is retained, so ``on_startup`` and
``on_shutdown`` fire exactly as they would without the compile.
"""

from __future__ import annotations

from collections import Counter
from unittest.mock import MagicMock

import pytest

from haywire.core.graph.base import BaseGraph
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


def _graph_with_hooks(graph: BaseGraph, monkeypatch: pytest.MonkeyPatch):
    """BeginPlay -> X; return the two wrappers and the per-node hook counters."""
    from haybale_testing.nodes.testbed.begin_play_probe import BeginPlayProbeNode
    from haybale_testing.nodes.testbed.control_payload_probe import ControlPayloadProbeNode

    begin = make_node(graph, BeginPlayProbeNode.class_identity.registry_key, position=(0, 0))
    x = make_node(graph, ControlPayloadProbeNode.class_identity.registry_key, position=(300, 0))
    assert make_edge(graph, begin.node_id, "exec", x.node_id, "exec_in").state.is_valid()

    started: Counter[str] = Counter()
    shut_down: Counter[str] = Counter()
    # Override detection looks the hook up on the class, so patch the class.
    for cls in (BeginPlayProbeNode, ControlPayloadProbeNode):
        monkeypatch.setattr(cls, "on_startup", lambda self, ctx: started.update([self.node_id]))
        monkeypatch.setattr(cls, "on_shutdown", lambda self, ctx: shut_down.update([self.node_id]))
    return (begin, x), started, shut_down


def _entry(graph: BaseGraph):
    from haybale_haystack.graph_entry import GraphEntry

    return GraphEntry(graph=graph, editor=MagicMock())


def test_compile_alone_starts_no_node(graph_with_library_system: BaseGraph, library_system, monkeypatch):
    wrappers, started, shut_down = _graph_with_hooks(graph_with_library_system, monkeypatch)
    entry = _entry(graph_with_library_system)

    assert entry.compile().ok
    interpreter = entry.interpreter
    assert interpreter is not None
    try:
        assert not entry.is_executing
        assert all(group._thread is None for group in interpreter.groups)
        assert all(wrapper._run_refs == 0 for wrapper in wrappers)
        assert not started
    finally:
        interpreter.shutdown()
    assert not shut_down


def test_compile_then_start_and_stop_runs_each_lifecycle_once(
    graph_with_library_system: BaseGraph, library_system, monkeypatch
):
    wrappers, started, shut_down = _graph_with_hooks(graph_with_library_system, monkeypatch)
    entry = _entry(graph_with_library_system)

    assert entry.compile().ok
    compiled = entry.interpreter
    assert entry.start_execution().ok
    try:
        assert entry.is_executing
        assert entry.interpreter is not compiled
        assert compiled is not None
        assert compiled.current_graph is None  # the replaced interpreter was shut down
    finally:
        entry.stop_execution()

    assert entry.interpreter is None
    node_ids = {wrapper.node_id for wrapper in wrappers}
    assert started == Counter(node_ids)
    assert shut_down == Counter(node_ids)
    assert all(wrapper._run_refs == 0 for wrapper in wrappers)
