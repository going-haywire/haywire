"""Restore or discard the active node's previous setup.

The panel body shared by the right-click menu and the Node inspector, so every
node can be resolved whatever skin draws it. See ADR 0062.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.node.previous_setup import PREVIOUS_SETUP_WARNING
from haywire.ui import elements as hui
from haywire.ui.access_stamp import stamp_requires
from haywire.ui.panel.layout import PanelLayout

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import route_for

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.session.context import SessionContext

HEADING = "Settings reset by a code change"

ACTIONS = (
    (
        "Restore",
        hui.icon.undo,
        "Bring back the earlier settings, including any the code change was meant to replace",
        True,
    ),
    ("Discard", hui.icon.delete, "Keep the defaults and drop the earlier settings", False),
)
"""Label, icon, tooltip and whether it restores, for the two commands."""


def holds_previous_setup(ctx: "SessionContext") -> bool:
    """True when the active node holds a previous setup."""
    node = ctx.data[EditState].active_node
    return node is not None and node.previous_setup is not None


def draw_previous_setup(ctx: "SessionContext", layout: PanelLayout, *, in_menu: bool) -> None:
    """Draw the message and Restore | Discard for the active node.

    Args:
        in_menu: Draw the commands as menu rows (a menu surface) rather than
            buttons (a panel surface), as the design guide requires.
    """
    node = ctx.data[EditState].active_node
    if node is None or node.previous_setup is None:
        return
    node_id = node.node_id
    route = route_for(ctx)
    with layout:
        ui.label(PREVIOUS_SETUP_WARNING).classes("text-sm hw-text-body whitespace-normal")
        with ui.row().classes("w-full no-wrap gap-1"):
            for label, icon, tooltip, restore in ACTIONS:

                def on_click(restore: bool = restore) -> None:
                    resolve_previous_setup(route, node_id, restore=restore)

                command: ui.element
                if in_menu:
                    command = hui.menu_row(label, icon=icon, tooltip=tooltip, on_click=on_click)
                    # Side by side: each row takes half the line instead of all of it.
                    command.classes(remove="w-full", add="flex-1")
                else:
                    command = hui.button(label, icon=icon, tooltip=tooltip, on_click=on_click)
                    command.classes(remove="w-full", add="flex-1")
                stamp_requires(command, LevelMode.EDIT)


def resolve_previous_setup(route: "EditRoute | None", node_id: str, *, restore: bool) -> None:
    """Restore or discard the node's previous setup through the route's editor; nothing below edit."""
    editor = route.editor() if route is not None else None
    if editor is None:
        return
    if restore:
        editor.apply_previous_setup([node_id])
    else:
        editor.dismiss_previous_setup([node_id])
