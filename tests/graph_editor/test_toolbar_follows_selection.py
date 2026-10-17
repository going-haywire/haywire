"""The selection toolbar re-renders when a validation batch names a selected node or edge."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager
from haywire.core.graph.types import ChangeReason, ValidationResult


def _manager(nodes: set[str] = frozenset(), edges: set[str] = frozenset()) -> Any:  # type: ignore[assignment]
    """A GraphCanvasManager with only what ``_refresh_toolbar_for`` reads."""
    manager: Any = object.__new__(GraphCanvasManager)
    manager.selection = SimpleNamespace(selected_nodes=set(nodes), selected_edges=set(edges))
    manager._toolbar_provider = MagicMock()
    return manager


@pytest.mark.unit
def test_a_batch_naming_a_selected_node_refreshes_the_toolbar():
    manager = _manager(nodes={"a"})
    manager._refresh_toolbar_for(ValidationResult(nodes={"a": ChangeReason.NODE_VALUE_CHANGED}))
    manager._toolbar_provider.refresh.assert_called_once_with()


@pytest.mark.unit
def test_a_batch_naming_a_selected_edge_refreshes_the_toolbar():
    manager = _manager(edges={"e"})
    manager._refresh_toolbar_for(ValidationResult(edges={"e": ChangeReason.NODE_VALUE_CHANGED}))
    manager._toolbar_provider.refresh.assert_called_once_with()


@pytest.mark.unit
def test_a_batch_naming_only_other_elements_leaves_the_toolbar():
    manager = _manager(nodes={"a"}, edges={"e"})
    manager._refresh_toolbar_for(
        ValidationResult(
            nodes={"b": ChangeReason.NODE_VALUE_CHANGED}, edges={"f": ChangeReason.NODE_VALUE_CHANGED}
        )
    )
    manager._toolbar_provider.refresh.assert_not_called()


class TestEveryWriterReachesIt:
    """A route write, an undo and a redo of a selected node's setting each report that node."""

    @pytest.fixture
    def live(self, library_system):
        from haywire.core.access import LevelMode
        from haywire.core.graph.base import BaseGraph
        from haywire.core.graph.edit_route import EditRoute
        from haywire.core.graph.editor import Editor
        from haywire.core.graph.scheduler import ThreadingTimerScheduler
        from tests.conftest import make_node

        graph = BaseGraph(
            filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
        )
        editor = Editor(graph, library_system.get_node_factory())
        route = EditRoute(lambda: editor, lambda: LevelMode.EDIT)
        wrapper = make_node(graph, "haybale-testing:node:TestAddFloatNode")
        graph._validation.force_immediate_validation()
        manager = _manager(nodes={wrapper.node_id})
        graph.subscribe_to_validation(manager._refresh_toolbar_for)
        yield graph, editor, route, wrapper.node.props, manager
        graph.unsubscribe_from_validation(manager._refresh_toolbar_for)
        graph._validation.clear()
        graph.cleanup()

    def test_a_route_write_undo_and_redo_each_refresh(self, live):
        from haywire.core.access import LevelMode

        graph, editor, route, props, manager = live
        refresh = manager._toolbar_provider.refresh

        assert route.set_setting(props, "locked", True, minimum=LevelMode.EDIT)
        graph._validation.force_immediate_validation()
        assert refresh.call_count == 1

        editor.undo()
        graph._validation.force_immediate_validation()
        assert refresh.call_count == 2

        editor.redo()
        graph._validation.force_immediate_validation()
        assert refresh.call_count == 3
