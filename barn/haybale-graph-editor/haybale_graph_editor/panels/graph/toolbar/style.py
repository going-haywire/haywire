# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/style.py
"""The toolbar's edge Style dropdown — hosts the surface ``EdgeStyle``.

The edge counterpart of the node Appearance dropdown: a content surface hung
from an icon, opened on click, never auto-closing. Its body is
``EdgeStyleBodyPanel``, the same panel the edge context menu's Style flyout
renders, so both edit through one rule (see ``_selection_forms``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.panels._selection_forms import disabled_icon, edge_style_subject

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_graph_editor.surfaces import EdgeStyle, SelectionActions, SelectionToolbar

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=SelectionToolbar,
    hosts=(EdgeStyle,),
    label="Style",
    description="The icon that drops the selected edges' colour, line and arrow heads above the toolbar.",
    icon=hui.icon.theme,
    order=210,
)
class EdgeStyleToolbarPanel(BasePanel):
    """The icon that drops the selected edges' colour, line and arrow heads above the toolbar.

    Shown for a selection of styled edges only; greyed, with the reason, when
    the selected edges cannot be styled together.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return edge_style_subject(ctx).editable

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.dropdown(hui.icon.theme, tooltip="Style", align="center", direction="up"):
                self.render_surface(EdgeStyle, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        subject = edge_style_subject(ctx)
        if subject.status == "greyed":
            with layout:
                disabled_icon(hui.icon.theme, f"Style — {subject.reason}")
