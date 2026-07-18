from haybale_graph_editor.focuses import ToolbarFocus
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu_actions import (
    SelectionContextActions,
    ToolbarActions,
)
from haybale_graph_editor.panels.graph.toolbar.selection import (
    CopyToolbarPanel,
    DeleteToolbarPanel,
    OverflowToolbarPanel,
)


def test_panels_target_toolbar_focus():
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, OverflowToolbarPanel):
        assert cls.class_identity.focus is ToolbarFocus


def test_copy_and_delete_target_selection_actions():
    assert CopyToolbarPanel.class_identity.action_protocol is SelectionContextActions
    assert DeleteToolbarPanel.class_identity.action_protocol is SelectionContextActions


def test_overflow_targets_toolbar_actions():
    assert OverflowToolbarPanel.class_identity.action_protocol is ToolbarActions


def test_poll_true_only_with_selection(make_ctx_with_selection):
    empty = make_ctx_with_selection(nodes=set(), edges=set())
    one = make_ctx_with_selection(nodes={"n1"}, edges=set())
    for cls in (CopyToolbarPanel, DeleteToolbarPanel, OverflowToolbarPanel):
        assert cls.poll(empty) is False
        assert cls.poll(one) is True
