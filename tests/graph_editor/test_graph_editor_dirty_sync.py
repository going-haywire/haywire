"""Regression: GraphEditor must refresh its header chrome on GraphDataMutated.

The editor's header carries the dirty dot (``●``), the tab dirty marker and
the undo/redo enablement — all derived from ``entry.unsaved`` /
``editor.can_undo()``. Those only change when graph *contents* change, which
is signalled by ``GraphDataMutated``. The editor used to subscribe to no
signals at all, so an in-place edit left the dot and buttons stale until the
next ``draw`` / ``on_focus`` / save. These tests pin the subscription so the
wiring can't silently regress.

We assert the contract structurally (via ``discover_handlers``) rather than
booting a NiceGUI client: the bug was purely a missing subscription, and the
dispatch machinery that turns a discovered ``react_on`` binding into a live
bus subscription is covered by the editor-wrapper tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from haywire.core.session.handlers import discover_handlers
from haywire.core.session.signals import GraphDataMutated

from haybale_graph_editor.editors.graph_editor import GraphEditor


def test_graph_editor_subscribes_to_graph_data_mutated():
    """GraphEditor declares a handler bound to GraphDataMutated."""
    handlers = discover_handlers(GraphEditor)
    assert GraphDataMutated in handlers, (
        "GraphEditor must react to GraphDataMutated so its header dirty dot "
        "and undo/redo buttons refresh after an edit."
    )


def test_graph_data_mutated_handler_is_react_not_redraw():
    """The handler is side-effect-only (react_on), never a full redraw.

    A redraw would rebuild the canvas DOM and lose zoom/pan/selection on
    every edit — the editor only needs to refresh its header chrome.
    """
    bindings = discover_handlers(GraphEditor)[GraphDataMutated]
    assert bindings, "expected at least one GraphDataMutated binding"
    assert all(b.kind == "react_on" for b in bindings), (
        "GraphDataMutated must be handled via @react_on (no wrapper.redraw); "
        f"got kinds {[b.kind for b in bindings]}"
    )


def test_handler_refreshes_header():
    """Invoking the handler calls _update_header with the given context."""
    editor = GraphEditor.__new__(GraphEditor)  # bypass wrapper construction
    editor._update_header = MagicMock()  # type: ignore[method-assign]

    bindings = discover_handlers(GraphEditor)[GraphDataMutated]
    method = getattr(editor, bindings[0].method_name)

    context = object()
    method(context, GraphDataMutated())

    editor._update_header.assert_called_once_with(context)
