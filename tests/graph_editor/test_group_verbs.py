"""The Group verbs: the Editor's collapse/expand, and what gates the menu rows."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor

from tests.conftest import make_node

_PRINT = "haybale-testing:node:TestPrintNode"
_CARD = "haywire-core:node:GraphNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


@pytest.fixture
def graph(library_system) -> BaseGraph:
    """A graph with the library system loaded, validating inline.

    ``tests/core`` has this as ``graph_with_library_system``; this package has
    no such fixture, and the Group verbs need real nodes.
    """
    from haywire.core.graph.scheduler import SyncScheduler

    return BaseGraph(filestem="Group Verbs", validation_scheduler=SyncScheduler())


def _editor(graph: BaseGraph, library_system) -> Editor:
    return Editor(graph, library_system.get_node_factory())


def _collapse(editor: Editor, node_ids, label: str = "Group"):
    return editor.collapse_to_group(
        node_ids=list(node_ids),
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label=label,
    )


@pytest.mark.integration
class TestEditorVerbs:
    def test_collapse_returns_the_new_cards_id(self, graph: BaseGraph, library_system):
        a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        editor = _editor(graph, library_system)

        card_id, reason = _collapse(editor, [a.node_id, b.node_id])

        assert reason is None
        assert card_id is not None
        assert graph.get_node_wrapper(card_id) is not None

    def test_collapse_is_undoable_through_the_editor(self, graph: BaseGraph, library_system):
        a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        editor = _editor(graph, library_system)
        before = set(graph.node_wrappers)

        _collapse(editor, [a.node_id, b.node_id])

        assert editor.can_undo()
        editor.undo()

        assert set(graph.node_wrappers) == before
        assert graph.subgraphs == {}

    def test_a_non_convex_collapse_reports_a_reason_naming_the_node(self, graph: BaseGraph, library_system):
        """The reason is written to be shown to the user."""
        a, b, c = (make_node(graph, _PRINT) for _ in range(3))
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")
        editor = _editor(graph, library_system)

        card_id, reason = _collapse(editor, [a.node_id, c.node_id])

        assert card_id is None
        assert reason is not None
        assert b.node_id in reason
        assert "Add them to the selection" in reason

    def test_a_refused_collapse_records_no_undo_step(self, graph: BaseGraph, library_system):
        a, b, c = (make_node(graph, _PRINT) for _ in range(3))
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")
        editor = _editor(graph, library_system)

        _collapse(editor, [a.node_id, c.node_id])
        editor.history_manager.add_fence()

        assert editor.can_undo() is False

    def test_expand_undoes_a_collapse_as_its_own_step(self, graph: BaseGraph, library_system):
        a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        editor = _editor(graph, library_system)
        before = set(graph.node_wrappers)

        card_id, _ = _collapse(editor, [a.node_id, b.node_id])
        assert card_id is not None

        assert editor.expand_group(card_id) is True
        assert set(graph.node_wrappers) == before

    def test_expanding_a_plain_node_reports_failure(self, graph: BaseGraph, library_system):
        node = make_node(graph, _PRINT)
        editor = _editor(graph, library_system)

        assert editor.expand_group(node.node_id) is False


@pytest.mark.integration
class TestDiscovery:
    def test_all_three_classes_resolve_from_the_registry(self, library_system):
        """The verbs name no concrete node — they discover it by identity flag."""
        factory = library_system.get_node_factory()

        assert factory.get_graph_node() is not None
        assert factory.get_subgraph_input_node() is not None
        assert factory.get_subgraph_output_node() is not None

    def test_the_card_is_the_one_flagged_is_graph_node(self, library_system):
        from haywire.barn.builtin.nodes.graph_node import GraphNode

        assert library_system.get_node_factory().get_graph_node() is GraphNode


@pytest.mark.unit
class TestMenuGating:
    """Which rows the selection menu offers."""

    def _ctx(self, *, active_node=None, selected: set[str] | None = None):
        from haybale_graph_editor.state.edit_state import EditState

        edit = MagicMock()
        edit.active_node = active_node
        edit.selected_nodes = selected or set()
        edit.selected_edges = set()

        ctx = MagicMock()
        ctx.data = {EditState: edit}
        return ctx

    def _node(self, *, is_graph_node: bool):
        wrapper = MagicMock()
        wrapper.node.identity._is_graph_node = is_graph_node
        return wrapper

    def test_group_rows_show_only_on_a_graph_node(self):
        from haybale_graph_editor.panels._gating import is_graph_node

        assert is_graph_node(self._ctx(active_node=self._node(is_graph_node=True))) is True
        assert is_graph_node(self._ctx(active_node=self._node(is_graph_node=False))) is False

    def test_group_rows_are_hidden_with_nothing_selected(self):
        from haybale_graph_editor.panels._gating import is_graph_node

        assert is_graph_node(self._ctx()) is False

    def test_collapse_needs_at_least_two_nodes(self):
        from haybale_graph_editor.panels._gating import is_collapsible_selection

        assert is_collapsible_selection(self._ctx(selected=set())) is False
        assert is_collapsible_selection(self._ctx(selected={"a"})) is False
        assert is_collapsible_selection(self._ctx(selected={"a", "b"})) is True

    def _placement(self, *, is_macro: bool):
        """A card whose CLASS identity carries the macro flag."""

        class _Node:
            class class_identity:
                _is_macro_node = is_macro

        wrapper = MagicMock()
        wrapper.node = _Node()
        return wrapper

    def test_the_macro_row_shows_only_on_a_placement(self):
        from haybale_graph_editor.panels._gating import is_macro_placement

        assert is_macro_placement(self._ctx(active_node=self._placement(is_macro=True))) is True
        assert is_macro_placement(self._ctx(active_node=self._placement(is_macro=False))) is False

    def test_the_macro_row_is_hidden_with_nothing_selected(self):
        from haybale_graph_editor.panels._gating import is_macro_placement

        assert is_macro_placement(self._ctx()) is False

    def test_a_placement_is_not_offered_the_group_rows(self):
        """MacroNode clears _is_graph_node so the two gates stay disjoint."""
        from haywire.barn.builtin.nodes.macro_node import MacroNode

        assert MacroNode.class_identity._is_graph_node is False
        assert MacroNode.class_identity._is_macro_node is True
