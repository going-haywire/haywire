"""
Tests for haybale-testing context menu action panels.

Verifies registration metadata (action+focus) and poll() contracts for:
- Node panels: TestDeleteNode, TestCopyNode, TestRedrawNode, TestRevalidateNode, TestResetNode
- Edge panels: TestDeleteEdge, TestInspectEdge, TestEdgeErrors, TestEdgeWarnings, TestEdgeConnectionPath
- Selection panels: TestCopySelection, TestPasteSelection
"""

import pytest
from unittest.mock import MagicMock

from haywire.core.state import LibraryStateContainer, LibraryStateRegistry
from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.core.session.context import SessionContext
from haywire.ui.panel import BasePanel

from haybale_testing.test_actions import (
    TestEdgeContextActions,
    TestNodeContextActions,
    TestSelectionContextActions,
)
from haybale_testing.test_focuses import TestEdgeFocus, TestNodeFocus, TestSelectionFocus
from haybale_testing.panels.test_node_panels import (
    TestDeleteNodePanel as DeleteNodePanel,
    TestCopyNodePanel as CopyNodePanel,
    TestRedrawNodePanel as RedrawNodePanel,
    TestRevalidateNodePanel as RevalidateNodePanel,
    TestResetNodePanel as ResetNodePanel,
)
from haybale_testing.panels.test_edge_panels import (
    TestDeleteEdgePanel as DeleteEdgePanel,
    TestInspectEdgePanel as InspectEdgePanel,
    TestEdgeErrorsPanel as EdgeErrorsPanel,
    TestEdgeWarningsPanel as EdgeWarningsPanel,
    TestEdgeConnectionPathPanel as EdgeConnectionPathPanel,
)
from haybale_testing.panels.test_selection_panels import (
    TestCopySelectionPanel as CopySelectionPanel,
    TestPasteSelectionPanel as PasteSelectionPanel,
)


class FakeApp:
    workspace_root = "/tmp"
    library_service = None

    def __init__(self) -> None:
        self.library_state_container = LibraryStateContainer(LibraryStateRegistry())


def make_context(
    register_edit_state, active_node=None, active_edge=None, clipboard=None
) -> tuple[SessionContext, type]:
    """Build a SessionContext with EditState registered and seeded.

    Returns ``(ctx, EditState)`` so callers can resolve
    ``ctx.data[EditState]`` against the same class reference the
    container saw (survives library hot-reloads).
    """
    app = FakeApp()
    sid = "test"
    EditStateCls = register_edit_state(app.library_state_container, sid)
    ctx = SessionContext(session_id=sid, app=app)
    ctx.session = MagicMock()
    edit = ctx.data[EditStateCls]
    edit.active_node.value = active_node
    edit.active_edge.value = active_edge
    if clipboard is not None:
        edit.clipboard.value = clipboard
    return ctx, EditStateCls


# ---------------------------------------------------------------------------
# Node action panels — registration metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "panel_cls",
    [
        DeleteNodePanel,
        CopyNodePanel,
        RedrawNodePanel,
        RevalidateNodePanel,
        ResetNodePanel,
    ],
)
def test_node_action_panel_action_is_test_node_context_actions(panel_cls):
    assert panel_cls.class_identity.action is TestNodeContextActions


@pytest.mark.parametrize(
    "panel_cls",
    [
        DeleteNodePanel,
        CopyNodePanel,
        RedrawNodePanel,
        RevalidateNodePanel,
        ResetNodePanel,
    ],
)
def test_node_action_panel_focus_is_test_node_focus(panel_cls):
    assert panel_cls.class_identity.focus is TestNodeFocus


@pytest.mark.parametrize(
    "panel_cls",
    [
        DeleteNodePanel,
        CopyNodePanel,
        RedrawNodePanel,
        RevalidateNodePanel,
        ResetNodePanel,
    ],
)
def test_node_action_panels_are_panel_subclasses(panel_cls):
    assert issubclass(panel_cls, BasePanel)


# ---------------------------------------------------------------------------
# Node action panels — poll()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "panel_cls",
    [
        DeleteNodePanel,
        CopyNodePanel,
        RedrawNodePanel,
        RevalidateNodePanel,
        ResetNodePanel,
    ],
)
def test_node_action_panel_poll_true_when_node_active(panel_cls, register_edit_state):
    ctx, _ = make_context(register_edit_state, active_node=MagicMock())
    assert panel_cls.poll(ctx) is True


@pytest.mark.parametrize(
    "panel_cls",
    [
        DeleteNodePanel,
        CopyNodePanel,
        RedrawNodePanel,
        RevalidateNodePanel,
        ResetNodePanel,
    ],
)
def test_node_action_panel_poll_false_when_no_node(panel_cls, register_edit_state):
    ctx, _ = make_context(register_edit_state, active_node=None)
    assert panel_cls.poll(ctx) is False


# ---------------------------------------------------------------------------
# Edge action panels — registration metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_action_is_test_edge_context_actions(panel_cls):
    assert panel_cls.class_identity.action is TestEdgeContextActions


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_focus_is_test_edge_focus(panel_cls):
    assert panel_cls.class_identity.focus is TestEdgeFocus


# ---------------------------------------------------------------------------
# Edge action panels — poll()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_poll_true_when_edge_active(panel_cls, register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=MagicMock())
    assert panel_cls.poll(ctx) is True


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_poll_false_when_no_edge(panel_cls, register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=None)
    assert panel_cls.poll(ctx) is False


# ---------------------------------------------------------------------------
# EdgeErrorsPanel
# ---------------------------------------------------------------------------


def test_edge_errors_panel_action_is_test_edge_context_actions():
    assert EdgeErrorsPanel.class_identity.action is TestEdgeContextActions


def test_edge_errors_panel_focus_is_test_edge_focus():
    assert EdgeErrorsPanel.class_identity.focus is TestEdgeFocus


def _make_edge_wrapper(error=None, warnings=None, has_edge=True):
    """Build a MagicMock EdgeWrapper with controlled state."""
    state = MagicMock()
    state.get_error.return_value = error
    state.has_warning.return_value = bool(warnings)
    state.warnings = warnings or []
    wrapper = MagicMock()
    wrapper.get_state.return_value = state
    wrapper.edge = MagicMock() if has_edge else None
    return wrapper


def test_edge_errors_panel_poll_true_when_state_has_error(register_edit_state):
    ctx, _ = make_context(
        register_edit_state, active_edge=_make_edge_wrapper(error=Exception("type mismatch"))
    )
    assert EdgeErrorsPanel.poll(ctx) is True


def test_edge_errors_panel_poll_false_when_no_error(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=_make_edge_wrapper(error=None))
    assert EdgeErrorsPanel.poll(ctx) is False


def test_edge_errors_panel_poll_false_when_no_edge(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=None)
    assert EdgeErrorsPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# EdgeWarningsPanel
# ---------------------------------------------------------------------------


def test_edge_warnings_panel_action_is_test_edge_context_actions():
    assert EdgeWarningsPanel.class_identity.action is TestEdgeContextActions


def test_edge_warnings_panel_focus_is_test_edge_focus():
    assert EdgeWarningsPanel.class_identity.focus is TestEdgeFocus


def test_edge_warnings_panel_poll_true_when_warnings_present(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=_make_edge_wrapper(warnings=["slow adapter"]))
    assert EdgeWarningsPanel.poll(ctx) is True


def test_edge_warnings_panel_poll_false_when_no_warnings(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=_make_edge_wrapper(warnings=[]))
    assert EdgeWarningsPanel.poll(ctx) is False


def test_edge_warnings_panel_poll_false_when_no_edge(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=None)
    assert EdgeWarningsPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# EdgeConnectionPathPanel
# ---------------------------------------------------------------------------


def test_edge_connection_path_panel_action_is_test_edge_context_actions():
    assert EdgeConnectionPathPanel.class_identity.action is TestEdgeContextActions


def test_edge_connection_path_panel_focus_is_test_edge_focus():
    assert EdgeConnectionPathPanel.class_identity.focus is TestEdgeFocus


def test_edge_connection_path_panel_poll_true_when_edge_with_data(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=_make_edge_wrapper())
    assert EdgeConnectionPathPanel.poll(ctx) is True


def test_edge_connection_path_panel_poll_false_when_no_edge(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=None)
    assert EdgeConnectionPathPanel.poll(ctx) is False


def test_edge_connection_path_panel_poll_false_when_edge_has_no_data(register_edit_state):
    ctx, _ = make_context(register_edit_state, active_edge=_make_edge_wrapper(has_edge=False))
    assert EdgeConnectionPathPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# Selection action panels — registration metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [CopySelectionPanel, PasteSelectionPanel])
def test_selection_action_panel_action_is_test_selection_context_actions(panel_cls):
    assert panel_cls.class_identity.action is TestSelectionContextActions


@pytest.mark.parametrize("panel_cls", [CopySelectionPanel, PasteSelectionPanel])
def test_selection_action_panel_focus_is_test_selection_focus(panel_cls):
    assert panel_cls.class_identity.focus is TestSelectionFocus


# ---------------------------------------------------------------------------
# Selection action panels — poll()
# ---------------------------------------------------------------------------


def test_copy_selection_poll_true_when_nodes_selected(register_edit_state):
    ctx, EditStateCls = make_context(register_edit_state)
    ctx.data[EditStateCls].selected_nodes.value = {"n1"}
    assert CopySelectionPanel.poll(ctx) is True


def test_copy_selection_poll_false_when_nothing_selected(register_edit_state):
    ctx, EditStateCls = make_context(register_edit_state)
    edit = ctx.data[EditStateCls]
    edit.selected_nodes.value = set()
    edit.selected_edges.value = set()
    assert CopySelectionPanel.poll(ctx) is False


def test_paste_selection_poll_true_when_clipboard_has_content(register_edit_state):
    clipboard = ClipboardData(
        nodes=["n1"],
        edges=[],
        original_to_new_ids={},
        bounding_box={"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        timestamp=0.0,
        source_session_id="test",
    )
    ctx, _ = make_context(register_edit_state, clipboard=clipboard)
    assert PasteSelectionPanel.poll(ctx) is True


def test_paste_selection_poll_false_when_clipboard_empty(register_edit_state):
    ctx, _ = make_context(register_edit_state, clipboard=None)
    assert PasteSelectionPanel.poll(ctx) is False
