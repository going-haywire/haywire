"""
Tests for haybale-core context menu action panels.

Verifies registration metadata and poll() contracts for:
- Node panels: DeleteNode, CopyNode, RedrawNode, RevalidateNode, ResetNode
- Edge panels: DeleteEdge, InspectEdge, EdgeErrors, EdgeWarnings, EdgeConnectionPath
- Selection panels: CopySelection, PasteSelection
"""

import pytest
from unittest.mock import MagicMock

from haywire.ui.panel.base import BasePanel
from haywire.ui.context import SessionContext

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


def make_context(active_node=None, active_edge=None, clipboard=None) -> SessionContext:
    ctx = SessionContext(session_id="test", app=FakeApp())
    ctx.session = MagicMock()
    ctx.active_node = active_node
    ctx.active_edge = active_edge
    if clipboard is not None:
        ctx.metadata["clipboard"] = clipboard
    return ctx


# ---------------------------------------------------------------------------
# Node action panels — registration metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [
    DeleteNodePanel, CopyNodePanel, RedrawNodePanel, RevalidateNodePanel, ResetNodePanel,
])
def test_node_action_panel_editor_is_context_menu(panel_cls):
    assert panel_cls.class_identity.editor_keys == ["test_inspector"]


@pytest.mark.parametrize("panel_cls", [
    DeleteNodePanel, CopyNodePanel, RedrawNodePanel, RevalidateNodePanel, ResetNodePanel,
])
def test_node_action_panel_scope_is_node(panel_cls):
    assert "test_node" in panel_cls.class_identity.scopes


@pytest.mark.parametrize("panel_cls", [
    DeleteNodePanel, CopyNodePanel, RedrawNodePanel, RevalidateNodePanel, ResetNodePanel,
])
def test_node_action_panels_are_base_panel_subclasses(panel_cls):
    assert issubclass(panel_cls, BasePanel)


# ---------------------------------------------------------------------------
# Node action panels — poll()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [
    DeleteNodePanel, CopyNodePanel, RedrawNodePanel, RevalidateNodePanel, ResetNodePanel,
])
def test_node_action_panel_poll_true_when_node_active(panel_cls):
    ctx = make_context(active_node=MagicMock())
    assert panel_cls.poll(ctx) is True


@pytest.mark.parametrize("panel_cls", [
    DeleteNodePanel, CopyNodePanel, RedrawNodePanel, RevalidateNodePanel, ResetNodePanel,
])
def test_node_action_panel_poll_false_when_no_node(panel_cls):
    ctx = make_context(active_node=None)
    assert panel_cls.poll(ctx) is False


# ---------------------------------------------------------------------------
# Edge action panels — registration metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_editor_is_context_menu(panel_cls):
    assert panel_cls.class_identity.editor_keys == ["test_inspector"]


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_scope_is_edge(panel_cls):
    assert "test_edge" in panel_cls.class_identity.scopes


# ---------------------------------------------------------------------------
# Edge action panels — poll()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_poll_true_when_edge_active(panel_cls):
    ctx = make_context(active_edge=MagicMock())
    assert panel_cls.poll(ctx) is True


@pytest.mark.parametrize("panel_cls", [DeleteEdgePanel, InspectEdgePanel])
def test_edge_action_panel_poll_false_when_no_edge(panel_cls):
    ctx = make_context(active_edge=None)
    assert panel_cls.poll(ctx) is False


# ---------------------------------------------------------------------------
# EdgeErrorsPanel
# ---------------------------------------------------------------------------


def test_edge_errors_panel_editor_is_context_menu():
    assert EdgeErrorsPanel.class_identity.editor_keys == ["test_inspector"]


def test_edge_errors_panel_scope_is_edge():
    assert "test_edge" in EdgeErrorsPanel.class_identity.scopes


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


def test_edge_errors_panel_poll_true_when_state_has_error():
    ctx = make_context(active_edge=_make_edge_wrapper(error=Exception("type mismatch")))
    assert EdgeErrorsPanel.poll(ctx) is True


def test_edge_errors_panel_poll_false_when_no_error():
    ctx = make_context(active_edge=_make_edge_wrapper(error=None))
    assert EdgeErrorsPanel.poll(ctx) is False


def test_edge_errors_panel_poll_false_when_no_edge():
    ctx = make_context(active_edge=None)
    assert EdgeErrorsPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# EdgeWarningsPanel
# ---------------------------------------------------------------------------


def test_edge_warnings_panel_editor_is_context_menu():
    assert EdgeWarningsPanel.class_identity.editor_keys == ["test_inspector"]


def test_edge_warnings_panel_scope_is_edge():
    assert "test_edge" in EdgeWarningsPanel.class_identity.scopes


def test_edge_warnings_panel_poll_true_when_warnings_present():
    ctx = make_context(active_edge=_make_edge_wrapper(warnings=["slow adapter"]))
    assert EdgeWarningsPanel.poll(ctx) is True


def test_edge_warnings_panel_poll_false_when_no_warnings():
    ctx = make_context(active_edge=_make_edge_wrapper(warnings=[]))
    assert EdgeWarningsPanel.poll(ctx) is False


def test_edge_warnings_panel_poll_false_when_no_edge():
    ctx = make_context(active_edge=None)
    assert EdgeWarningsPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# EdgeConnectionPathPanel
# ---------------------------------------------------------------------------


def test_edge_connection_path_panel_editor_is_context_menu():
    assert EdgeConnectionPathPanel.class_identity.editor_keys == ["test_inspector"]


def test_edge_connection_path_panel_scope_is_edge():
    assert "test_edge" in EdgeConnectionPathPanel.class_identity.scopes


def test_edge_connection_path_panel_poll_true_when_edge_with_data():
    ctx = make_context(active_edge=_make_edge_wrapper())
    assert EdgeConnectionPathPanel.poll(ctx) is True


def test_edge_connection_path_panel_poll_false_when_no_edge():
    ctx = make_context(active_edge=None)
    assert EdgeConnectionPathPanel.poll(ctx) is False


def test_edge_connection_path_panel_poll_false_when_edge_has_no_data():
    ctx = make_context(active_edge=_make_edge_wrapper(has_edge=False))
    assert EdgeConnectionPathPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# Selection action panels — registration metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("panel_cls", [CopySelectionPanel, PasteSelectionPanel])
def test_selection_action_panel_editor_is_context_menu(panel_cls):
    assert panel_cls.class_identity.editor_keys == ["test_inspector"]


@pytest.mark.parametrize("panel_cls", [CopySelectionPanel, PasteSelectionPanel])
def test_selection_action_panel_scope_is_selection(panel_cls):
    assert "test_selection" in panel_cls.class_identity.scopes


# ---------------------------------------------------------------------------
# Selection action panels — poll()
# ---------------------------------------------------------------------------


def test_copy_selection_poll_true_when_nodes_selected():
    ctx = make_context()
    ctx.selected_nodes = {"n1"}
    assert CopySelectionPanel.poll(ctx) is True


def test_copy_selection_poll_false_when_nothing_selected():
    ctx = make_context()
    ctx.selected_nodes = set()
    ctx.selected_edges = set()
    assert CopySelectionPanel.poll(ctx) is False


def test_paste_selection_poll_true_when_clipboard_has_content():
    clipboard = MagicMock()
    clipboard.nodes = ["n1"]
    ctx = make_context(clipboard=clipboard)
    assert PasteSelectionPanel.poll(ctx) is True


def test_paste_selection_poll_false_when_clipboard_empty():
    ctx = make_context(clipboard=None)
    assert PasteSelectionPanel.poll(ctx) is False
