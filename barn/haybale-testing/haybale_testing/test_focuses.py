"""Test-specific Focus classes.

Mirror NodeFocus/EdgeFocus/etc. with test-specific ids so test
fixtures don't appear under production focus tabs.
"""

from __future__ import annotations

from haybale_studio.state.edit_state import EditState
from haywire.ui.context import SessionContext
from haywire.ui.panel.focus import Focus


class TestCanvasFocus(Focus):
    id = "test_canvas"
    label = "Test Canvas"
    icon = "grid_on"
    order = 100

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class TestNodeFocus(Focus):
    id = "test_node"
    label = "Test Node"
    icon = "account_tree"
    order = 110

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_node.value is not None


class TestEdgeFocus(Focus):
    id = "test_edge"
    label = "Test Edge"
    icon = "cable"
    order = 120

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_edge.value is not None


class TestSelectionFocus(Focus):
    id = "test_selection"
    label = "Test Selection"
    icon = "select_all"
    order = 130

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes.value) or bool(edit.selected_edges.value)
