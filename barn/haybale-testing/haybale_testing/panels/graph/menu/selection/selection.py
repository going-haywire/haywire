"""Test-only selection action panels for haybale_testing.

On the ``TestSelectionMenu`` surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.state.edit_state import EditState
from haybale_testing.surfaces import TestSelectionActions, TestSelectionMenu
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=TestSelectionMenu,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class TestCopySelectionMenuPanel(BasePanel):
    actions: TestSelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes or edit.selected_edges)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        with layout:
            hui.menu_row(
                "Copy Selection",
                icon=hui.icon.copy,
                on_click=self.actions.test_copy_selection,
            )


@panel(
    surface=TestSelectionMenu,
    label="Paste",
    icon=hui.icon.paste,
    order=20,
)
class TestPasteSelectionMenuPanel(BasePanel):
    actions: TestSelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].clipboard is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        with layout:
            hui.menu_row(
                "Paste",
                icon=hui.icon.paste,
                on_click=self.actions.test_paste_at_click,
            )
