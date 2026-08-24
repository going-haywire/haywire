"""Test-only node menu surface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from haywire.core.session.context import SessionContext
from haywire.ui.surface import Surface


@runtime_checkable
class TestNodeActions(Protocol):
    __test__: bool = False

    def test_delete_node(self, node_id: str) -> None: ...
    def test_copy_node(self, node_id: str) -> None: ...
    def test_redraw_node(self, node_id: str) -> None: ...
    def test_revalidate_node(self, node_id: str) -> None: ...
    def test_reset_node(self, node_id: str) -> None: ...


class TestNodeMenu(Surface):
    __test__: bool = False

    id = "test_node"
    order = 110
    provides = TestNodeActions

    @classmethod
    def poll(cls, ctx: SessionContext) -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_node is not None
