"""Which GraphEditor's level the session's graph state describes, with two editors shown at once.

Split panes show two graph editors side by side, each the focused tab of its
own slot. The session's ``active_graph`` / ``active_locked`` are what the
panels gate on, so they must describe the graph the selection lives in: the
editor a pointer-down lands in claims the session, and an editor the user is
not working in never does.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor
from haybale_graph_editor.protocols import SubgraphContainer
from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import _REACT_ON_ATTR
from haywire.core.signals import SelectionMoved

from .test_graph_editor_levels import _assert_selection_dropped, _select, _two_tabs
from .test_graph_editor_placement_levels import _PLACEMENT_KEY, _open_placement, _placement_definition

pytestmark = pytest.mark.unit


def _binding(editor: GraphEditor, binding_id: str) -> str:
    """Give ``editor`` the editor binding id its root carries as ``data-hw-binding``; return it."""
    cast(Any, editor.wrapper).editor_binding_id = binding_id
    return binding_id


def _retarget(context: Any, binding_id: str, *editors: GraphEditor) -> None:
    """Point the session's target at ``binding_id`` and dispatch the change as the session bus does."""
    context.target_binding_id = binding_id
    for editor in editors:
        editor._on_target_moved(context, None)


def _published(context: Any) -> list[type]:
    return [type(call.args[0]) for call in context.session.publish.call_args_list]


def _split_panes() -> tuple[GraphEditor, GraphEditor, Any, Any]:
    """Editor A on an unlocked document, editor B inside a locked macro placement; A holds the session.

    Returns A, B, the session context and the session's EditState, which holds
    a node of A's document as its selection.
    """
    a, b, context, _b_document = _two_tabs()
    _binding(a, "graph::/tmp/graphs/main.haywire")
    _binding(b, "graph::/tmp/graphs/other.haywire")
    _open_placement(b, context)
    edit_state = _select(a, context, MagicMock(name="a_node"))
    context.target_binding_id = a.wrapper.editor_binding_id
    return a, b, context, edit_state


def _interior_graph(editor: GraphEditor) -> Any:
    return editor._levels[_PLACEMENT_KEY].container.editor.graph


class TestTheEditorAClickLandsInClaims:
    def test_the_editor_reacts_to_the_target_moving(self):
        assert getattr(GraphEditor._on_target_moved, _REACT_ON_ATTR, ()) == (
            SessionContext.target_binding_id,
        )

    def test_a_pointer_down_on_the_other_pane_moves_the_session_to_its_level(self):
        a, b, context, edit_state = _split_panes()

        _retarget(context, b.wrapper.editor_binding_id, a, b)

        assert edit_state.active_graph is _interior_graph(b)
        assert edit_state.active_locked is True
        _assert_selection_dropped(context, edit_state)

    def test_the_click_selection_lands_after_the_claim_and_stays(self):
        a, b, context, edit_state = _split_panes()
        b_node = MagicMock(name="b_interior_node")

        _retarget(context, b.wrapper.editor_binding_id, a, b)
        edit_state.active_node = b_node  # the canvas's selection event, which follows the pointer-down
        _retarget(context, b.wrapper.editor_binding_id, a, b)

        assert edit_state.active_node is b_node
        assert edit_state.active_graph is _interior_graph(b)
        assert edit_state.active_locked is True

    def test_clicking_back_in_the_first_pane_drops_the_other_panes_selection(self):
        a, b, context, edit_state = _split_panes()
        _retarget(context, b.wrapper.editor_binding_id, a, b)
        edit_state.active_node = MagicMock(name="b_interior_node")
        context.session.publish.reset_mock()

        _retarget(context, a.wrapper.editor_binding_id, a, b)

        assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
        assert edit_state.active_locked is False
        _assert_selection_dropped(context, edit_state)

    def test_a_pointer_down_in_another_editor_claims_nothing(self):
        a, b, context, edit_state = _split_panes()
        a_node = edit_state.active_node
        context.session.publish.reset_mock()

        _retarget(context, "studio:editors:Shortcuts", a, b)

        assert edit_state.active_graph is a._levels[DOCUMENT_LEVEL].container.editor.graph
        assert edit_state.active_node is a_node
        context.session.publish.assert_not_called()


class TestABackgroundEditorLeavesTheSessionAlone:
    """A level change in an editor the session is not on updates that editor only."""

    def test_a_reload_repointing_a_background_level_keeps_the_session(self):
        a, b, context, edit_state = _split_panes()
        a_graph, a_node = edit_state.active_graph, edit_state.active_node
        context.session.publish.reset_mock()
        reloaded = _placement_definition(_PLACEMENT_KEY)
        b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded

        b._prune_dead_levels(context)

        container = b._levels[_PLACEMENT_KEY].container
        assert isinstance(container, SubgraphContainer)
        assert container.definition is reloaded
        assert b._active_level == _PLACEMENT_KEY
        assert edit_state.active_graph is a_graph
        assert edit_state.active_locked is False
        assert edit_state.active_node is a_node
        assert SelectionMoved not in _published(context)

    def test_closing_a_background_editors_level_keeps_the_session(self):
        a, b, context, edit_state = _split_panes()
        a_graph, a_node = edit_state.active_graph, edit_state.active_node
        context.session.publish.reset_mock()
        del b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY]

        b._prune_dead_levels(context)

        assert list(b._levels) == [DOCUMENT_LEVEL]
        assert b._active_level == DOCUMENT_LEVEL
        assert edit_state.active_graph is a_graph
        assert edit_state.active_node is a_node
        assert SelectionMoved not in _published(context)

    def test_the_background_editor_claims_its_new_level_when_focused(self):
        _a, b, context, edit_state = _split_panes()
        reloaded = _placement_definition(_PLACEMENT_KEY)
        b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded
        b._prune_dead_levels(context)

        b.on_focus(context)

        assert edit_state.active_graph is reloaded
        assert edit_state.active_locked is True

    def test_the_editor_the_session_is_on_still_follows_its_reload(self):
        _a, b, context, edit_state = _split_panes()
        _retarget(context, b.wrapper.editor_binding_id, b)
        reloaded = _placement_definition(_PLACEMENT_KEY)
        b._levels[DOCUMENT_LEVEL].container.editor.graph.subgraphs[_PLACEMENT_KEY] = reloaded

        b._prune_dead_levels(context)

        assert edit_state.active_graph is reloaded
        assert edit_state.active_locked is True
