"""GraphEditor's self-matching handler for RevealGraphInstance."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def _make_editor():
    from haybale_graph_editor.editors.graph_editor import GraphEditor
    from haywire.ui.editor.wrapper import EditorWrapper

    # A plain object() rejects attribute assignment at runtime (cast() is a
    # mypy-only no-op) — use a SimpleNamespace so we can set _binding_id.
    wrapper = SimpleNamespace(_binding_id="/tmp/webcam.haywire")
    editor = GraphEditor(cast(EditorWrapper, wrapper))
    return editor


def test_no_canvas_manager_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor()
    editor._canvas_manager = None
    context = SimpleNamespace(data=MagicMock(), session=MagicMock())

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    context.session.publish.assert_not_called()


def test_graph_id_mismatch_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor()
    editor._canvas_manager = SimpleNamespace(graph=SimpleNamespace(graph_id="other_graph"))
    context = SimpleNamespace(data=MagicMock(), session=MagicMock())

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    context.session.publish.assert_not_called()


def test_matching_graph_id_selects_node_and_publishes():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor()
    node_wrapper = MagicMock()
    graph = SimpleNamespace(
        graph_id="webcam", name="Webcam", get_node_wrapper=MagicMock(return_value=node_wrapper)
    )
    editor._canvas_manager = SimpleNamespace(graph=graph)

    edit_stub = SimpleNamespace(active_node=None, active_edge=None)
    data = MagicMock()
    data.__getitem__.return_value = edit_stub
    context = SimpleNamespace(data=data, session=MagicMock())

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    graph.get_node_wrapper.assert_called_once_with("n1")
    assert edit_stub.active_node is node_wrapper
    assert context.session.publish.call_count == 2  # Reveal + SelectionMoved


def test_matching_graph_id_selects_edge():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor()
    edge_wrapper = MagicMock()
    graph = SimpleNamespace(
        graph_id="webcam",
        name="Webcam",
        edge_wrappers={"edge::o@a>>i@b": edge_wrapper},
    )
    editor._canvas_manager = SimpleNamespace(graph=graph)

    edit_stub = SimpleNamespace(active_node=None, active_edge=None)
    data = MagicMock()
    data.__getitem__.return_value = edit_stub
    context = SimpleNamespace(data=data, session=MagicMock())

    editor._on_reveal_graph_instance(
        context, RevealGraphInstance(graph_id="webcam", edge_id="edge::o@a>>i@b")
    )

    assert edit_stub.active_edge is edge_wrapper
    assert context.session.publish.call_count == 2


def test_node_gone_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor = _make_editor()
    graph = SimpleNamespace(graph_id="webcam", name="Webcam", get_node_wrapper=MagicMock(return_value=None))
    editor._canvas_manager = SimpleNamespace(graph=graph)
    context = SimpleNamespace(data=MagicMock(), session=MagicMock())

    editor._on_reveal_graph_instance(context, RevealGraphInstance(graph_id="webcam", node_id="gone"))

    context.session.publish.assert_not_called()
