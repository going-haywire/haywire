import haywire.core.graph.editor  # noqa: F401

from haybale_graph_editor.focuses import ToolbarFocus, SelectionFocus
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import ToolbarActions


def test_toolbar_focus_has_distinct_id():
    assert ToolbarFocus.id == "toolbar"
    assert ToolbarFocus.id != SelectionFocus.id


def test_toolbar_focus_available_mirrors_selection(make_ctx_with_selection):
    # available() is True iff there is a non-empty selection (any node/edge).
    ctx_empty = make_ctx_with_selection(nodes=set(), edges=set())
    ctx_one = make_ctx_with_selection(nodes={"n1"}, edges=set())
    assert ToolbarFocus.available(ctx_empty) is False
    assert ToolbarFocus.available(ctx_one) is True


def test_toolbar_actions_is_runtime_checkable_protocol():
    # ToolbarActions declares the overflow verb.
    assert hasattr(ToolbarActions, "open_overflow_menu")
