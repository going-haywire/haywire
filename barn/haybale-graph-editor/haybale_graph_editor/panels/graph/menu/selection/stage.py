"""Stage rows of the selection menu.

``SelectionMenu`` offers Add to Stage and Remove from Stage in both views; each
polls on the selected nodes' ``on_stage`` and needs EDIT.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import SelectionActions, SelectionMenu

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _staged_flags(ctx: "SessionContext") -> list[bool]:
    """The ``on_stage`` flag of each selected node that exists in the active graph."""
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None:
        return []
    flags: list[bool] = []
    for node_id in edit.selected_nodes:
        wrapper = graph.get_node_wrapper(node_id)
        if wrapper is not None:
            flags.append(bool(wrapper.node.props.on_stage))
    return flags


def _selection_has_off_stage(ctx: "SessionContext") -> bool:
    return not all(_staged_flags(ctx))


def _selection_has_on_stage(ctx: "SessionContext") -> bool:
    return any(_staged_flags(ctx))


# SelectionMenu
#  -> AddToStageMenuPanel
#  -> RemoveFromStageMenuPanel


@panel(
    surface=SelectionMenu,
    label="Add to Stage",
    icon=hui.icon.stage_add,
    order=15,
)
class AddToStageMenuPanel(BasePanel):
    """Put the selected nodes on the stage; offered when the selection holds an off-stage node."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_has_off_stage(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row("Add to Stage", icon=hui.icon.stage_add, on_click=self.actions.add_to_stage)


@panel(
    surface=SelectionMenu,
    label="Remove from Stage",
    icon=hui.icon.stage_remove,
    order=16,
)
class RemoveFromStageMenuPanel(BasePanel):
    """Take the selected nodes off the stage; offered when the selection holds an on-stage node."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_has_on_stage(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.menu_row(
                "Remove from Stage",
                icon=hui.icon.stage_remove,
                on_click=self.actions.remove_from_stage,
            )
