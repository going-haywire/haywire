"""HaystackEditor brings forward the document holding a revealed graph, opening its tab if needed."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def _make_editor_and_context():
    from haybale_haystack.editors.haystack_editor import HaystackEditor
    from haywire.ui.editor.wrapper import EditorWrapper

    editor = HaystackEditor(cast(EditorWrapper, object()))
    session = SimpleNamespace(session_id="sess-1", publish=MagicMock())
    app_data = MagicMock()
    context = SimpleNamespace(app=None, session=session, app_data=app_data, data=MagicMock())
    return editor, context, app_data


def test_no_matching_container_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    app_data.__getitem__.return_value.all_containers.return_value = []

    editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="webcam"))

    context.session.publish.assert_not_called()


def test_matching_container_publishes_reveal():
    from haywire.core.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    # GraphContainer exposes .editor (an Editor), whose .graph is the
    # BaseGraph — there is no direct container.graph shortcut.
    container = SimpleNamespace(
        editor=SimpleNamespace(graph=SimpleNamespace(graph_id="webcam", subgraphs={})),
        binding_id="/tmp/webcam.haywire",
        display_name="webcam",
    )
    app_data.__getitem__.return_value.all_containers.return_value = [container]

    editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="webcam", node_id="n1"))

    assert context.session.publish.call_count == 1
    published = context.session.publish.call_args[0][0]
    assert published.binding_id == "/tmp/webcam.haywire"
    assert published.label == "webcam"


def test_non_matching_container_is_noop():
    from haywire.core.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    container = SimpleNamespace(
        editor=SimpleNamespace(graph=SimpleNamespace(graph_id="other_graph", subgraphs={})),
        binding_id="/tmp/other.haywire",
        display_name="other",
    )
    app_data.__getitem__.return_value.all_containers.return_value = [container]

    editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="webcam"))

    context.session.publish.assert_not_called()


def _document_with_interior():
    """A document ``webcam`` holding a Group whose interior holds a nested Group ``deep``."""
    deep = SimpleNamespace(graph_id="deep", subgraphs={})
    group = SimpleNamespace(graph_id="group", subgraphs={"sg_deep": deep})
    return SimpleNamespace(
        editor=SimpleNamespace(graph=SimpleNamespace(graph_id="webcam", subgraphs={"sg_group": group})),
        binding_id="/tmp/webcam.haywire",
        display_name="webcam",
    )


def test_a_graph_inside_a_closed_interior_reveals_its_document():
    from haywire.core.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    app_data.__getitem__.return_value.all_containers.return_value = [_document_with_interior()]

    editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="deep", node_id="n1"))

    assert context.session.publish.call_count == 1
    assert context.session.publish.call_args[0][0].binding_id == "/tmp/webcam.haywire"


def test_the_reveal_waits_in_edit_state_only_while_the_tab_opens():
    from haywire.core.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    app_data.__getitem__.return_value.all_containers.return_value = [_document_with_interior()]
    edit_state = SimpleNamespace(pending_reveal=None)
    context.data = MagicMock()
    context.data.__getitem__.return_value = edit_state
    seen: list = []
    context.session.publish.side_effect = lambda _signal: seen.append(edit_state.pending_reveal)
    event = RevealGraphInstance(graph_id="deep", node_id="n1")

    editor._on_reveal_graph_instance_reopen(context, event)

    assert seen == [event]
    assert edit_state.pending_reveal is None


def test_a_failing_reveal_still_clears_the_waiting_reveal():
    from haywire.core.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    app_data.__getitem__.return_value.all_containers.return_value = [_document_with_interior()]
    edit_state = SimpleNamespace(pending_reveal=None)
    context.data = MagicMock()
    context.data.__getitem__.return_value = edit_state
    context.session.publish.side_effect = RuntimeError("slot gone")

    with pytest.raises(RuntimeError):
        editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="deep", node_id="n1"))

    assert edit_state.pending_reveal is None
