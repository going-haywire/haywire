"""A user's value edit marks the graph unsaved without reassembling it.

A widget or property write changes what a save records, so the app must mark
the file unsaved; it changes no structure, so a running graph must not be
stopped and reassembled for it. ``NODE_VALUE_CHANGED`` (on the edited node) and
``GRAPH_CONTENT_CHANGED`` (on a host, for an edit inside its Subgraph) carry
exactly that: saved, never reassembled.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler, ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason, ValidationResult

from tests.conftest import make_node

_VALUE_REASONS = [ChangeReason.NODE_VALUE_CHANGED, ChangeReason.GRAPH_CONTENT_CHANGED]


def _add_float_key() -> str:
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    return TestAddFloatNode.class_identity.registry_key


# =============================================================================
# The reasons themselves
# =============================================================================


@pytest.mark.unit
@pytest.mark.parametrize("reason", _VALUE_REASONS)
def test_value_reasons_save_but_neither_repaint_nor_reassemble(reason: ChangeReason) -> None:
    assert reason.is_visual_only() is False
    assert reason.requires_graph_reassembly() is False
    assert reason.requires_redraw() is False


@pytest.mark.unit
def test_requires_reassembly_reads_every_collection() -> None:
    assert ValidationResult().requires_reassembly() is False
    assert ValidationResult(nodes={"n1": ChangeReason.NODE_ADDED}).requires_reassembly() is True
    assert ValidationResult(edges={"e1": ChangeReason.EDGE_REMOVED}).requires_reassembly() is True
    assert ValidationResult(graph=ChangeReason.GRAPH_REQUIRE_REASSEMBLY).requires_reassembly() is True


@pytest.mark.unit
def test_requires_reassembly_ignores_saved_but_structureless_changes() -> None:
    result = ValidationResult(
        nodes={"n1": ChangeReason.NODE_VALUE_CHANGED, "n2": ChangeReason.NODE_MOVED},
        edges={"e1": ChangeReason.EDGE_STYLE_CHANGED},
        graph=ChangeReason.GRAPH_CONTENT_CHANGED,
    )

    assert result.requires_save() is True
    assert result.requires_reassembly() is False


@pytest.mark.unit
def test_a_content_change_does_not_overwrite_a_pending_reassembly() -> None:
    """Both land in one debounce window when an interior edits structure, then a value."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    try:
        graph._validation.mark_graph_dirty(ChangeReason.GRAPH_REQUIRE_REASSEMBLY)
        graph._validation.mark_graph_dirty(ChangeReason.GRAPH_CONTENT_CHANGED)

        assert graph._validation._dirty_graph is ChangeReason.GRAPH_REQUIRE_REASSEMBLY
    finally:
        graph._validation.clear()


@pytest.mark.unit
def test_a_reassembly_overwrites_a_pending_content_change() -> None:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    try:
        graph._validation.mark_graph_dirty(ChangeReason.GRAPH_CONTENT_CHANGED)
        graph._validation.mark_graph_dirty(ChangeReason.GRAPH_REQUIRE_REASSEMBLY)

        assert graph._validation._dirty_graph is ChangeReason.GRAPH_REQUIRE_REASSEMBLY
    finally:
        graph._validation.clear()


# =============================================================================
# NodeWrapper.mark_value_edited
# =============================================================================


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    """A graph whose debounce never fires on its own, so a test drains it explicitly."""
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.mark.integration
def test_value_change_requires_save_not_reassembly(held_graph: BaseGraph) -> None:
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(held_graph, _add_float_key())
    assert isinstance(wrapper.node, TestAddFloatNode)
    held_graph._validation.force_immediate_validation()

    wrapper.mark_value_edited()
    result = held_graph._validation.force_immediate_validation()

    assert result is not None
    assert result.nodes == {wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}
    assert result.graph is None
    assert result.requires_save() is True
    assert result.requires_reassembly() is False


@pytest.mark.integration
def test_an_unregistered_node_marks_nothing(held_graph: BaseGraph) -> None:
    wrapper = make_node(held_graph, _add_float_key())
    held_graph._validation.force_immediate_validation()
    wrapper.set_as_registered(False)

    wrapper.mark_value_edited()

    assert held_graph._validation.force_immediate_validation() is None


@pytest.mark.integration
def test_set_property_marks_unsaved(library_system) -> None:
    from haywire.core.graph.editor import Editor
    from haywire.core.undo.config import UndoConfig

    graph = BaseGraph(filestem="g", validation_scheduler=SyncScheduler())
    config = UndoConfig(enable_auto_grouping=False, enable_action_merging=False)
    editor = Editor(graph, library_system.get_node_factory(), undo_config=config)
    try:
        wrapper = make_node(graph, _add_float_key())
        seen: list[ValidationResult] = []
        graph.subscribe_to_validation(seen.append)

        assert editor.set_property(wrapper.node_id, "value_a", 3.0) is True
        assert [r.nodes for r in seen] == [{wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}]
        assert seen[-1].requires_save() is True
        assert seen[-1].requires_reassembly() is False

        seen.clear()
        assert editor.undo() is True
        assert [r.nodes for r in seen] == [{wrapper.node_id: ChangeReason.NODE_VALUE_CHANGED}]
    finally:
        graph.cleanup()
