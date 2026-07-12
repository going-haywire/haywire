# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/graph.py
"""
GraphSettingsPanel — renders the active graph's settings bag (graph.props).

The graph-scope section of the properties editor (ADR 0022): shown under
GraphFocus (graph itself in focus, no node selected). Reuses the generic
bag renderer; the setting-row menu offers no promote entries because a
GraphSettings bag has ``_node is None`` (structural guard in
``_build_row_menu``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.session.signals import ActiveGraphMoved, GraphDataMutated
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_settings

from ....focuses import GraphFocus
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=GraphFocus,
    label="Graph Settings",
    icon=hui.icon.graph,
    order=20,
    default_open=True,
    redraw_on=(ActiveGraphMoved, GraphDataMutated),
)
class GraphSettingsPanel(BasePanel):
    """Renders ``graph.props`` for the active graph."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        graph_obj = ctx.data[EditState].active_graph
        return graph_obj is not None and getattr(graph_obj, "props", None) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        graph_obj = ctx.data[EditState].active_graph
        if graph_obj is None:
            return
        with layout:
            render_settings(graph_obj.props)
