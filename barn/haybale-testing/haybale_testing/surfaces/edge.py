"""Test-only edge menu surface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from haywire.core.session.context import SessionContext
from haywire.ui.surface import Surface


@runtime_checkable
class TestEdgeActions(Protocol):
    __test__: bool = False

    def test_delete_edge(self, edge_id: str) -> None: ...
    def test_inspect_edge(self, edge_id: str) -> None: ...


class TestEdgeMenu(Surface):
    __test__: bool = False

    id = "test_edge"
    order = 120
    provides = TestEdgeActions

    @classmethod
    def poll(cls, ctx: SessionContext) -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_edge is not None
