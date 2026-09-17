"""GraphEditor's levels: one document per tab, the Groups inside it on a row of its own.

The editor owns its levels, which is what lets it close one the moment its
Subgraph stops existing — expanded, deleted, or the collapse that made it undone.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor, level_key_for
from haybale_graph_editor.protocols import GraphContainer, SubgraphContainer

pytestmark = pytest.mark.unit


class _FakeDocument(GraphContainer):
    """A document container, standing in for a haystack entry."""

    def __init__(self, binding_id: str = "/tmp/graphs/main.haywire"):
        self._binding_id = binding_id
        self.editor = MagicMock()
        self.editor.graph = _FakeGraph("doc_graph")
        self.path = Path(binding_id)
        self.unsaved = False

    @property
    def binding_id(self) -> str:
        return self._binding_id

    @property
    def display_name(self) -> str:
        return "main.haywire"

    def save(self, save_as: Path | None = None) -> str | None:
        return None


class _FakeGraph:
    """The parts of a graph the level machinery touches."""

    def __init__(self, graph_id: str):
        self.graph_id = graph_id
        self.filestem = graph_id
        self.node_wrappers: dict[str, Any] = {}
        self.subgraphs: dict[str, Any] = {}

    def get_node_wrapper(self, node_id: str):
        return self.node_wrappers.get(node_id)

    def get_subgraph(self, key: str):
        return self.subgraphs.get(key)


def _definition(key: str = "sg_1", label: str = "Filter") -> Any:
    """A Subgraph that is bound to a card and sits in its host's table."""
    definition = _FakeGraph(f"graph_of_{key}")
    definition.key = key  # type: ignore[attr-defined]
    definition.label = label  # type: ignore[attr-defined]
    # One card object for the life of the stub: the editor watches its props
    # bag by identity, to tell a rebuilt card from the one it already follows.
    card = MagicMock()
    definition.graph_node_wrapper = lambda: card  # type: ignore[attr-defined]
    return definition


def _stub(method: Any) -> Any:
    """A method replaced by a MagicMock, typed as one again."""
    return cast(Any, method)


def _card(definition) -> Any:
    """A Graph-node wrapper resolving to ``definition`` (``None`` for a plain node)."""
    wrapper = MagicMock()
    wrapper.node.resolve_definition.return_value = definition
    return wrapper


def _editor(document: _FakeDocument | None = None) -> tuple[GraphEditor, Any, _FakeDocument]:
    """A GraphEditor holding ``document`` as its only level, drawn far enough to switch."""
    from haywire.ui.editor.wrapper import EditorWrapper
    from haybale_graph_editor.editors.graph_editor import _Level

    document = document or _FakeDocument()
    wrapper = MagicMock()
    wrapper._binding_id = document.binding_id
    editor = GraphEditor(cast(EditorWrapper, wrapper))
    editor._project_state = cast(Any, SimpleNamespace(node_factory=MagicMock()))
    editor._levels[DOCUMENT_LEVEL] = _Level(key=DOCUMENT_LEVEL, container=document)

    # Nothing is mounted in a unit test, so the DOM-touching half is stubbed;
    # what is under test is which levels exist and which one is on screen.
    editor._mount_level = MagicMock()  # type: ignore[method-assign]
    editor._teardown_level = MagicMock()  # type: ignore[method-assign]
    editor._render_level_bar = MagicMock()  # type: ignore[method-assign]
    editor._update_header = MagicMock()  # type: ignore[method-assign]
    editor._claim_session_state = MagicMock()  # type: ignore[method-assign]

    context = SimpleNamespace(app_data=MagicMock(), session=MagicMock(), data=MagicMock())
    return editor, context, document


def _descend(editor: GraphEditor, context, definition, node_id: str = "GraphNode_1") -> bool:
    """Put a card for ``definition`` in the level on screen, then step into it."""
    entry = editor._levels[editor._active_level].container
    graph = entry.editor.graph
    graph.node_wrappers[node_id] = _card(definition)
    if definition is not None:
        graph.subgraphs[definition.key] = definition
    return editor.descend_into(context, node_id)


class TestLevelKeys:
    def test_a_document_is_the_document_level(self):
        assert level_key_for(_FakeDocument()) == DOCUMENT_LEVEL

    def test_a_group_is_keyed_by_its_subgraph_key(self):
        container = SubgraphContainer(_FakeDocument(), _definition(key="sg_a"), MagicMock())

        assert level_key_for(container) == "sg_a"

    def test_nesting_stacks_the_keys(self):
        """Prefix-addressable, so closing a level can find what is nested inside it."""
        outer = SubgraphContainer(_FakeDocument(), _definition(key="sg_a"), MagicMock())
        inner = SubgraphContainer(outer, _definition(key="sg_b"), MagicMock())

        assert level_key_for(inner) == "sg_a#sg_b"

    def test_it_does_not_change_with_the_documents_binding_id(self):
        """A save-as re-keys the document; the open levels must not move."""
        definition = _definition(key="sg_a")
        before = level_key_for(SubgraphContainer(_FakeDocument("/tmp/a.haywire"), definition, MagicMock()))
        after = level_key_for(SubgraphContainer(_FakeDocument("/tmp/b.haywire"), definition, MagicMock()))

        assert before == after == "sg_a"


class TestDescending:
    def test_it_opens_a_level_and_shows_it(self):
        editor, context, document = _editor()
        definition = _definition(key="sg_a")

        assert _descend(editor, context, definition) is True

        assert editor._active_level == "sg_a"
        container = editor._levels["sg_a"].container
        assert isinstance(container, SubgraphContainer)
        assert container.definition is definition
        assert container.host is document

    def test_re_entering_keeps_the_level_already_open(self):
        """The same container, so the Group keeps its canvas, viewport and undo state."""
        editor, context, _document = _editor()
        definition = _definition(key="sg_a")

        _descend(editor, context, definition)
        first = editor._levels["sg_a"].container
        editor.ascend(context)
        _descend(editor, context, definition)

        assert editor._levels["sg_a"].container is first
        assert editor._active_level == "sg_a"

    def test_descending_twice_nests(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        _descend(editor, context, _definition(key="sg_b"))

        assert list(editor._levels) == [DOCUMENT_LEVEL, "sg_a", "sg_a#sg_b"]

    def test_a_node_with_no_subgraph_is_refused(self):
        editor, context, _document = _editor()

        assert _descend(editor, context, None) is False
        assert list(editor._levels) == [DOCUMENT_LEVEL]

    def test_an_unknown_node_is_refused(self):
        editor, context, _document = _editor()

        assert editor.descend_into(context, "nobody") is False


class TestAscending:
    def test_it_shows_the_level_above(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        _descend(editor, context, _definition(key="sg_b"))

        assert editor.ascend(context) is True
        assert editor._active_level == "sg_a"

    def test_the_level_it_left_stays_open(self):
        """Going back up does not close what is below — that is the point of the row."""
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))

        editor.ascend(context)

        assert "sg_a" in editor._levels

    def test_the_document_has_nowhere_to_ascend_to(self):
        editor, context, _document = _editor()

        assert editor.ascend(context) is False


class TestClosingALevel:
    def test_it_closes_the_level(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))

        editor._close_level(context, "sg_a")

        assert list(editor._levels) == [DOCUMENT_LEVEL]
        assert editor._active_level == DOCUMENT_LEVEL

    def test_it_closes_every_level_nested_inside_it(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        _descend(editor, context, _definition(key="sg_b"))

        editor._close_level(context, "sg_a")

        assert list(editor._levels) == [DOCUMENT_LEVEL]

    def test_closing_a_background_level_leaves_the_one_on_screen_alone(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        editor._switch_level(context, DOCUMENT_LEVEL)
        _descend(editor, context, _definition(key="sg_b"))

        editor._close_level(context, "sg_a")

        assert editor._active_level == "sg_b"
        assert list(editor._levels) == [DOCUMENT_LEVEL, "sg_b"]

    def test_the_document_level_cannot_be_closed(self):
        editor, context, _document = _editor()

        editor._close_level(context, DOCUMENT_LEVEL)

        assert list(editor._levels) == [DOCUMENT_LEVEL]


class TestPruningDeadLevels:
    """What the editor owning its levels buys: a level dies with its Subgraph."""

    def test_a_subgraph_dropped_from_its_host_closes_its_level(self):
        """Expanding the Group, or undoing the collapse that made it."""
        editor, context, document = _editor()
        definition = _definition(key="sg_a")
        _descend(editor, context, definition)

        del document.editor.graph.subgraphs["sg_a"]
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]
        assert editor._active_level == DOCUMENT_LEVEL

    def test_a_card_deleted_closes_its_level(self):
        editor, context, _document = _editor()
        definition = _definition(key="sg_a")
        _descend(editor, context, definition)

        definition.graph_node_wrapper = lambda: None
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]

    def test_the_levels_nested_inside_go_too(self):
        editor, context, document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        _descend(editor, context, _definition(key="sg_b"))

        del document.editor.graph.subgraphs["sg_a"]
        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL]

    def test_a_live_level_is_left_alone(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))

        editor._prune_dead_levels(context)

        assert list(editor._levels) == [DOCUMENT_LEVEL, "sg_a"]

    def test_it_runs_on_every_graph_mutation(self):
        """The signal every collapse, expand and delete already publishes."""
        from haywire.core.signals import GraphDataMutated

        editor, context, document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        editor._recover_stale_binding_id = MagicMock()  # type: ignore[method-assign]
        del document.editor.graph.subgraphs["sg_a"]

        editor._on_graph_data_mutated(context, GraphDataMutated())

        assert list(editor._levels) == [DOCUMENT_LEVEL]


class TestUndoIsTheDocuments:
    """One file, one history — at every level."""

    def test_undo_goes_to_the_documents_editor_from_inside_a_group(self):
        from haywire.core.signals import GraphDataMutated

        editor, context, document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        document_editor = cast(Any, document.editor)
        document_editor.can_undo.return_value = True

        editor._do_undo(context)

        document_editor.undo.assert_called_once_with()
        assert isinstance(context.session.publish.call_args[0][0], GraphDataMutated)

    def test_redo_goes_to_the_documents_editor_from_inside_a_group(self):
        editor, context, document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        document_editor = cast(Any, document.editor)
        document_editor.can_redo.return_value = True

        editor._do_redo(context)

        document_editor.redo.assert_called_once_with()

    def test_save_goes_to_the_document_from_inside_a_group(self, monkeypatch):
        from haybale_graph_editor.editors import graph_editor as graph_editor_mod

        monkeypatch.setattr(graph_editor_mod.ui, "notify", lambda *a, **k: None)
        editor, context, document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        document.save = MagicMock(return_value=None)  # type: ignore[method-assign]

        editor._save_graph(context)

        document.save.assert_called_once_with()


class TestFirstActivation:
    """A slot calls ``on_focus`` before it draws a wrapper, so that is first in."""

    def _editor_and_context(self):
        from haybale_graph_editor.state.graph_app_state import GraphAppState
        from haywire.ui.editor.wrapper import EditorWrapper

        document = _FakeDocument()
        app_state = GraphAppState()
        app_state.register(document)

        wrapper = MagicMock()
        wrapper._binding_id = document.binding_id
        editor = GraphEditor(cast(EditorWrapper, wrapper))

        app_data = MagicMock()
        app_data.__getitem__.return_value = app_state
        edit_stub = SimpleNamespace(active_graph=None, active_graph_path=None)
        data = MagicMock()
        data.__getitem__.return_value = edit_stub
        context = SimpleNamespace(app_data=app_data, session=MagicMock(), data=data)
        return editor, context, document, edit_stub

    def test_it_opens_the_document_level_with_nothing_drawn(self):
        editor, context, document, edit_stub = self._editor_and_context()

        editor.on_focus(cast(Any, context))

        assert list(editor._levels) == [DOCUMENT_LEVEL]
        assert edit_stub.active_graph is document.editor.graph

    def test_a_document_that_no_longer_resolves_closes_the_tab(self):
        editor, context, _document, _edit = self._editor_and_context()
        editor.wrapper._binding_id = "/tmp/gone.haywire"

        editor.on_focus(cast(Any, context))

        editor.wrapper.force_close.assert_called_once_with()
        assert editor._levels == {}


class TestFollowingTheName:
    """A Group is named by renaming its card, which raises no signal of its own."""

    def _watched(self, editor: GraphEditor, key: str):
        return editor._levels[key].watched_props

    def test_opening_a_level_follows_its_cards_label(self):
        editor, context, _document = _editor()
        definition = _definition(key="sg_a")
        _descend(editor, context, definition)

        card = definition.graph_node_wrapper()
        assert self._watched(editor, "sg_a") is card.node.props
        card.node.props._subscribe_field.assert_called_once_with("label", editor._on_level_renamed)

    def test_a_rename_repaints_the_bar_and_the_breadcrumb(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        editor._context = context
        editor._update_breadcrumb = MagicMock()  # type: ignore[method-assign]
        bar, breadcrumb = _stub(editor._render_level_bar), _stub(editor._update_breadcrumb)
        bar.reset_mock()

        editor._on_level_renamed("Filter", "")

        bar.assert_called_once_with(context)
        breadcrumb.assert_called_once_with(context)

    def test_a_rename_before_the_first_draw_is_a_noop(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        bar = _stub(editor._render_level_bar)
        bar.reset_mock()

        editor._on_level_renamed("Filter", "")  # _context is still None

        bar.assert_not_called()

    def test_closing_a_level_stops_following_it(self):
        editor, context, _document = _editor()
        definition = _definition(key="sg_a")
        _descend(editor, context, definition)
        props = definition.graph_node_wrapper().node.props
        editor._teardown_level = GraphEditor._teardown_level.__get__(editor)  # type: ignore[method-assign]

        editor._close_level(context, "sg_a")

        props._unsubscribe.assert_called_once_with(editor._on_level_renamed)

    def test_a_document_level_has_no_card_to_follow(self):
        editor, _context, _document = _editor()

        assert self._watched(editor, DOCUMENT_LEVEL) is None

    def test_a_rebuilt_card_is_followed_instead(self):
        """Pruning runs on every mutation, and re-binds what it finds."""
        editor, context, _document = _editor()
        definition = _definition(key="sg_a")
        _descend(editor, context, definition)
        rebuilt = MagicMock()
        definition.graph_node_wrapper = lambda: rebuilt

        editor._prune_dead_levels(context)

        assert self._watched(editor, "sg_a") is rebuilt.node.props


class TestEdgesSurviveAHiddenCanvas:
    """A level that was not on screen was not rendered, so its canvas is new.

    The canvas asks for its own edges as it mounts — see
    ``VisualLayerHandlers.process_canvas_mounted`` — which is why nothing here
    pushes them on the switch. Proven end-to-end in
    ``tests/ui/harness/test_graph_hidden_level_edges.py``.
    """

    def test_switching_shows_the_level_and_does_not_push_edges_at_it(self):
        editor, context, _document = _editor()
        _descend(editor, context, _definition(key="sg_a"))
        for level in editor._levels.values():
            level.canvas_manager = MagicMock()
        shown = _stub(editor._levels[DOCUMENT_LEVEL].canvas_manager)

        editor._switch_level(context, DOCUMENT_LEVEL)

        assert editor._active_level == DOCUMENT_LEVEL
        shown.resync_edges.assert_not_called()
