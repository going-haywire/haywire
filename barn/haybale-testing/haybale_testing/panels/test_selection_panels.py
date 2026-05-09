"""Test-only selection action panels for haybale_testing.

Phase 1.5: action=TestSelectionContextActions, focus=TestSelectionFocus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.state.edit_state import EditState
from haybale_testing.test_actions import TestSelectionContextActions
from haybale_testing.test_focuses import TestSelectionFocus
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    action=TestSelectionContextActions,
    focus=TestSelectionFocus,
    label="Copy Selection",
    icon=hui.icon.copy,
    order=10,
)
class TestCopySelectionPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes.value or edit.selected_edges.value)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestSelectionContextActions,
    ) -> None:
        layout.button(
            "Copy Selection",
            icon=hui.icon.copy,
            on_click=actions.test_copy_selection,
        )


@panel(
    action=TestSelectionContextActions,
    focus=TestSelectionFocus,
    label="Paste",
    icon=hui.icon.paste,
    order=20,
)
class TestPasteSelectionPanel(BasePanel):
    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].clipboard.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: TestSelectionContextActions,
    ) -> None:
        layout.button(
            "Paste",
            icon=hui.icon.paste,
            on_click=actions.test_paste_at_click,
        )
