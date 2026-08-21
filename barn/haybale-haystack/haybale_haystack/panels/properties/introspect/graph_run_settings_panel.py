# barn/haybale-haystack/haybale_haystack/panels/graph_run_settings_panel.py
"""GraphRunSettingsPanel — renders run policy settings for the active graph.

Appears under GraphFocus, showing the GraphRunSettings bag (autorestart, etc.)
for whichever graph is currently active in the editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.signals import ActiveGraphMoved, GraphDataMutated
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_settings

from haybale_graph_editor.focuses import GraphFocus
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import GraphAppState

from haybale_haystack.graph_entry import GraphEntry

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=GraphFocus,
    label="Run Settings",
    icon=hui.icon.execution,
    order=20,
    default_open=True,
    redraw_on=(ActiveGraphMoved, GraphDataMutated),
)
class GraphRunSettingsPanel(BasePanel):
    """Renders the GraphRunSettings for the currently active graph."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        graph = ctx.data[EditState].active_graph
        if graph is None:
            return False
        entry = ctx.app_data[GraphAppState].get_by_graph(graph)
        return isinstance(entry, GraphEntry)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        graph = ctx.data[EditState].active_graph
        if graph is None:
            return
        entry = ctx.app_data[GraphAppState].get_by_graph(graph)
        if not isinstance(entry, GraphEntry):
            return

        with layout:
            render_settings(entry.run_settings)
