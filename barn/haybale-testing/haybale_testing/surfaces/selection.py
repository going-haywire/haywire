"""Test-only selection menu surface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from haywire.core.session.context import SessionContext
from haywire.ui.surface import Surface


@runtime_checkable
class TestSelectionActions(Protocol):
    __test__: bool = False

    def test_copy_selection(self) -> None: ...
    def test_paste_at_click(self) -> None: ...


class TestSelectionMenu(Surface):
    __test__: bool = False

    id = "test_selection"
    order = 130
    provides = TestSelectionActions

    @classmethod
    def poll(cls, ctx: SessionContext) -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        edit = ctx.data[EditState]
        return bool(edit.selected_nodes) or bool(edit.selected_edges)
