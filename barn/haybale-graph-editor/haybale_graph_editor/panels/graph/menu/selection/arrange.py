"""The "Arrange" row of the selection menu and its four stacking-order verbs.

``SelectionMenu`` offers Arrange in both views; each verb acts on the selected nodes in the view
the menu opened in, and needs EDIT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.graph.stacking import Restack
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import SelectionActions, SelectionArrangeMenu, SelectionMenu

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _selection_has_a_node(ctx: "SessionContext") -> bool:
    """Whether the selection holds a node that exists in the active graph."""
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None:
        return False
    return any(graph.get_node_wrapper(node_id) is not None for node_id in edit.selected_nodes)


# SelectionMenu
#  -> ArrangeSelectionMenuPanel
#     -> SelectionArrangeMenu
#        -> BringToFrontMenuPanel
#        -> BringForwardMenuPanel
#        -> SendBackwardMenuPanel
#        -> SendToBackMenuPanel


@panel(
    surface=SelectionMenu,
    hosts=(SelectionArrangeMenu,),
    label="Arrange",
    description='The "Arrange" row: a submenu over the stacking-order verbs.',
    icon=hui.icon.arrange,
    order=420,
)
class ArrangeSelectionMenuPanel(BasePanel):
    """The "Arrange" row: a submenu over the stacking-order verbs.

    Moves the selected nodes up or down the order they paint in, in the view the menu opened in.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_has_a_node(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Arrange", icon=hui.icon.arrange):
                self.render_surface(SelectionArrangeMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — a row that does not expand."""
        with layout:
            hui.submenu_row("Arrange", icon=hui.icon.arrange, enabled=False)


class _RestackMenuPanel(BasePanel):
    """A menu row that applies one ``Restack`` verb to the selection."""

    actions: SelectionActions
    how: Restack
    row_label: str
    row_icon: str

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_has_a_node(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(self.row_label, icon=self.row_icon, on_click=self._restack)

    def _restack(self) -> None:
        self.actions.restack_selection(self.how)


@panel(
    surface=SelectionArrangeMenu,
    label="Bring to Front",
    description="Paint the selected nodes above every other node in this view.",
    icon=hui.icon.bring_to_front,
    order=10,
)
class BringToFrontMenuPanel(_RestackMenuPanel):
    """Paint the selected nodes above every other node in this view."""

    how = Restack.FRONT
    row_label = "Bring to Front"
    row_icon = hui.icon.bring_to_front


@panel(
    surface=SelectionArrangeMenu,
    label="Bring Forward",
    description="Move each selected node one step up: above the next node over it.",
    icon=hui.icon.bring_forward,
    order=20,
)
class BringForwardMenuPanel(_RestackMenuPanel):
    """Move each selected node one step up: above the next node over it."""

    how = Restack.FORWARD
    row_label = "Bring Forward"
    row_icon = hui.icon.bring_forward


@panel(
    surface=SelectionArrangeMenu,
    label="Send Backward",
    description="Move each selected node one step down: below the next node under it.",
    icon=hui.icon.send_backward,
    order=30,
)
class SendBackwardMenuPanel(_RestackMenuPanel):
    """Move each selected node one step down: below the next node under it."""

    how = Restack.BACKWARD
    row_label = "Send Backward"
    row_icon = hui.icon.send_backward


@panel(
    surface=SelectionArrangeMenu,
    label="Send to Back",
    description="Paint the selected nodes below every other node in this view.",
    icon=hui.icon.send_to_back,
    order=40,
)
class SendToBackMenuPanel(_RestackMenuPanel):
    """Paint the selected nodes below every other node in this view."""

    how = Restack.BACK
    row_label = "Send to Back"
    row_icon = hui.icon.send_to_back
