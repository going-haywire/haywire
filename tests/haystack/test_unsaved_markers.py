"""The unsaved markers follow ``GraphUnsavedChanged``, which no Properties panel redraws on."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_editor import GraphEditor
from haybale_haystack.editors.haystack_editor import HaystackEditor
from haywire.core.session.handlers import HandlerBinding, discover_handlers
from haywire.core.signals import GraphUnsavedChanged

pytestmark = pytest.mark.unit


def test_the_graph_editor_header_refreshes_on_the_unsaved_flip():
    bindings = discover_handlers(GraphEditor)[GraphUnsavedChanged]
    assert [binding.kind for binding in bindings] == ["react_on"]

    editor = GraphEditor(MagicMock())
    editor._update_header = MagicMock()  # type: ignore[method-assign]
    context = MagicMock()
    getattr(editor, bindings[0].method_name)(context, GraphUnsavedChanged())

    editor._update_header.assert_called_once_with(context)


def test_the_haystack_list_redraws_on_the_unsaved_flip():
    bindings = discover_handlers(HaystackEditor)[GraphUnsavedChanged]
    assert bindings == [HandlerBinding("_refresh_on_state_move", "redraw_on")]
