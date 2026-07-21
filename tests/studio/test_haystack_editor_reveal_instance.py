"""HaystackEditor reopens a loaded-but-tabless graph on RevealGraphInstance."""

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
    from haywire.core.session.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    app_data.__getitem__.return_value.all_containers.return_value = []

    editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="webcam"))

    context.session.publish.assert_not_called()


def test_matching_container_publishes_reveal():
    from haywire.core.session.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    # GraphContainer exposes .editor (an Editor), whose .graph is the
    # BaseGraph — there is no direct container.graph shortcut.
    container = SimpleNamespace(
        editor=SimpleNamespace(graph=SimpleNamespace(graph_id="webcam")),
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
    from haywire.core.session.signals import RevealGraphInstance

    editor, context, app_data = _make_editor_and_context()
    container = SimpleNamespace(
        editor=SimpleNamespace(graph=SimpleNamespace(graph_id="other_graph")),
        binding_id="/tmp/other.haywire",
        display_name="other",
    )
    app_data.__getitem__.return_value.all_containers.return_value = [container]

    editor._on_reveal_graph_instance_reopen(context, RevealGraphInstance(graph_id="webcam"))

    context.session.publish.assert_not_called()
