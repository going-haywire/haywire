"""GraphEditor's self-matching handler for RevealGraphInstance.

The editor answers for every level it has open, not just the one on screen, and
opens a level for a Subgraph of this document that has none yet.
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def _make_editor(*graphs, active: int = 0):
    """A GraphEditor with one level per graph, the ``active``-th on screen."""
    from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL, GraphEditor, _Level
    from haywire.ui.editor.wrapper import EditorWrapper

    # A plain object() rejects attribute assignment at runtime (cast() is a
    # mypy-only no-op) — use a SimpleNamespace so we can set _binding_id.
    wrapper = SimpleNamespace(_binding_id="/tmp/webcam.haywire")
    editor = GraphEditor(cast(EditorWrapper, wrapper))

    keys = [DOCUMENT_LEVEL, *(f"sg_{i}" for i in range(1, len(graphs)))][: len(graphs)]
    for key, graph in zip(keys, graphs, strict=True):
        container = SimpleNamespace(
            editor=SimpleNamespace(graph=graph, history_manager=MagicMock()),
            display_name=graph.filestem,
            path=None,
        )
        editor._levels[key] = _Level(key=key, container=cast(Any, container))
    if graphs:
        editor._active_level = keys[active]
    editor._switch_level = MagicMock()  # type: ignore[method-assign]
    return editor


def _graph(graph_id: str, **kwargs):
    return SimpleNamespace(graph_id=graph_id, filestem=graph_id, subgraphs={}, **kwargs)


def _context():
    edit_stub = SimpleNamespace(active_node=None, active_edge=None)
    data = MagicMock()
    data.__getitem__.return_value = edit_stub
    return SimpleNamespace(data=data, session=MagicMock(), app_data=MagicMock()), edit_stub


def test_no_levels_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor()
    context, _edit = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    context.session.publish.assert_not_called()


def test_graph_id_in_no_level_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor(_graph("other_graph"))
    context, _edit = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    context.session.publish.assert_not_called()


def test_matching_graph_id_selects_node_and_publishes():
    from haywire.core.signals import RevealGraphInstance

    node_wrapper = MagicMock()
    graph = _graph("webcam", get_node_wrapper=MagicMock(return_value=node_wrapper))
    editor = _make_editor(graph)
    context, edit_stub = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    graph.get_node_wrapper.assert_called_once_with("n1")
    assert edit_stub.active_node is node_wrapper
    assert context.session.publish.call_count == 2  # Reveal + SelectionMoved


def test_matching_graph_id_selects_edge():
    from haywire.core.signals import RevealGraphInstance

    edge_wrapper = MagicMock()
    graph = _graph("webcam", edge_wrappers={"a[o]->b[i]": edge_wrapper})
    editor = _make_editor(graph)
    context, edit_stub = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", edge_id="a[o]->b[i]"))

    assert edit_stub.active_edge is edge_wrapper
    assert context.session.publish.call_count == 2


def test_node_gone_is_noop():
    from haywire.core.signals import RevealGraphInstance

    graph = _graph("webcam", get_node_wrapper=MagicMock(return_value=None))
    editor = _make_editor(graph)
    context, _edit = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="gone"))

    context.session.publish.assert_not_called()


def test_a_match_on_a_background_level_switches_to_it():
    """The graph named may be a Group the user is not looking at."""
    from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL
    from haywire.core.signals import RevealGraphInstance

    document = _graph("webcam")
    inside = _graph("group_graph", get_node_wrapper=MagicMock(return_value=MagicMock()))
    editor = _make_editor(document, inside, active=0)
    context, _edit = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="group_graph", node_id="n1"))

    editor._switch_level.assert_called_once_with(context, "sg_1")
    assert editor._active_level == DOCUMENT_LEVEL  # the stub does not move it


def test_a_match_on_the_level_already_on_screen_does_not_switch():
    from haywire.core.signals import RevealGraphInstance

    graph = _graph("webcam", get_node_wrapper=MagicMock(return_value=MagicMock()))
    editor = _make_editor(graph)
    context, _edit = _context()

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    editor._switch_level.assert_not_called()


class TestOpeningALevelForIt:
    """A Subgraph of this document with no level open yet gets one."""

    def test_a_subgraph_of_the_document_is_opened(self):
        from haybale_graph_editor.editors.graph_editor import DOCUMENT_LEVEL
        from haywire.core.signals import RevealGraphInstance

        definition = _graph("group_graph", key="sg_a", label="Filter")
        definition.get_node_wrapper = MagicMock(return_value=MagicMock())
        document = _graph("webcam")
        document.subgraphs = {"sg_a": definition}

        editor = _make_editor(document)
        editor._project_state = cast(Any, SimpleNamespace(node_factory=MagicMock()))
        opened: list = []
        editor._open_level = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda _ctx, container: opened.append(container)
        )
        context, _edit = _context()

        editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="group_graph", node_id="n1"))

        assert len(opened) == 1
        assert opened[0].definition is definition
        assert opened[0].host is editor._levels[DOCUMENT_LEVEL].container

    def test_a_graph_in_no_document_of_ours_opens_nothing(self):
        from haywire.core.signals import RevealGraphInstance

        editor = _make_editor(_graph("webcam"))
        editor._project_state = cast(Any, SimpleNamespace(node_factory=MagicMock()))
        editor._open_level = MagicMock()  # type: ignore[method-assign]
        context, _edit = _context()

        editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="stranger", node_id="n1"))

        editor._open_level.assert_not_called()
        context.session.publish.assert_not_called()
