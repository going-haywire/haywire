# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/appearance.py
"""
The toolbar's Appearance dropdown — the surface ``NodeAppearance``.

Two panels, one per side of the nesting: ``AppearanceToolbarPanel`` is the
icon on ``SelectionToolbar`` that hosts the surface, and
``NodeAppearancePanel`` is what lands inside it.

A *dropdown*, not a flyout: what hangs below is a stack of editable fields,
not a list of commands. ``hui.dropdown`` opens on click and never
``auto-close``s, because a menu's auto-close dismisses on any click inside it
— the first click into a field would shut the panel. See
``haywire.ui.elements.flyout.DropdownIcon``.

For one node, the fields are the *live* ``appearance`` category of its own props bag
(``skin``, ``layout_direction``, ``body_color``, ``border_color``,
``border_thickness``, ``border_roundness``) — the same rows, the same
reset chrome and the same subscriptions the properties editor renders, sliced
by ``render_settings(categories=...)`` rather than copied. Editing one here
and in the Node Properties panel is the same write. For several nodes they are a
neutral form whose changes go to every selected node (see ``_selection_forms``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.panels._selection_forms import disabled_icon, node_appearance_subject, render_form
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_graph_editor.surfaces import NodeAppearance, SelectionActions, SelectionToolbar
from haybale_graph_editor.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext

# The one category of NodeProperties this surface owns. Declared once here so
# the panel and its tests cannot disagree about which slice is on show.
APPEARANCE_CATEGORY = "appearance"


@panel(
    surface=SelectionToolbar,
    hosts=(NodeAppearance,),
    label="Appearance",
    description="The ⧉ icon that drops the appearance fields above the toolbar.",
    icon=hui.icon.theme,
    order=200,
)
class AppearanceToolbarPanel(BasePanel):
    """The ⧉ icon that drops the appearance fields above the toolbar.

    Shown for a selection of nodes only; greyed, with the reason, when the
    selected nodes cannot be styled together. See ``_selection_forms``.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return node_appearance_subject(ctx).editable

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.dropdown(hui.icon.theme, tooltip="Appearance", align="center", direction="up"):
                self.render_surface(NodeAppearance, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        subject = node_appearance_subject(ctx)
        if subject.status == "greyed":
            with layout:
                disabled_icon(hui.icon.theme, f"Appearance — {subject.reason}")


@panel(
    surface=NodeAppearance,
    label="Appearance",
    description="The selected node's appearance props, or a form applying to every selected node.",
    icon=hui.icon.theme,
    order=10,
)
class NodeAppearancePanel(BasePanel):
    """The appearance slice of the selected node's props, or a form applying to every selected node.

    The ``hw-panel`` wrapper is load-bearing. A dropdown is a ``QMenu`` and
    portals to ``<body>``, outside the toolbar popup's own ``hw-panel``, so
    without it every ``.hw-panel``-scoped field rule in the shell CSS misses
    these rows — the same portal trap that gave menus three different colours.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return node_appearance_subject(ctx).editable

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        subject = node_appearance_subject(ctx)
        if not subject.editable:
            return
        with layout:
            with ui.column().classes("hw-panel gap-0").style("min-width: 240px"):
                render_form(
                    ctx,
                    subject,
                    categories=(APPEARANCE_CATEGORY,),
                    graph=ctx.data[EditState].active_graph,
                )
