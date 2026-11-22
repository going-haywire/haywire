# barn/haybale-haystack/haybale_haystack/panels/graph_run_settings_panel.py
"""GraphRunSettingsPanel — renders run policy settings for the active graph.

Appears on GraphInspector, showing the GraphRunSettings bag (autorestart, etc.)
for whichever graph is currently active in the editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.states.edit_state import EditState
from haybale_graph_editor.states.graph_app_state import GraphAppState
from haybale_haystack.graph_entry import GraphEntry
from haywire.api.workbench import (
    ActiveGraphMoved,
    BasePanel,
    ExecutionInspectorSurface,
    GraphDataMutated,
    PanelLayout,
    hui,
    panel,
    render_settings,
)

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=ExecutionInspectorSurface,
    label="Graph Settings",
    description="Renders the GraphRunSettings for the currently active graph.",
    icon=hui.icon.graph,
    order=20,
    default_open=True,
    redraw_on=(ActiveGraphMoved, GraphDataMutated),
)
class GraphRunSettingsPanel(BasePanel):
    """Renders the GraphRunSettings for the currently active graph."""

    @classmethod
    def poll(cls, ctx: SessionContext) -> bool:
        graph = ctx.data[EditState].active_graph
        if graph is None:
            return False
        entry = ctx.app_data[GraphAppState].get_by_graph(graph)
        return isinstance(entry, GraphEntry)

    def draw(
        self,
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        graph = ctx.data[EditState].active_graph
        if graph is None:
            return
        entry = ctx.app_data[GraphAppState].get_by_graph(graph)
        if not isinstance(entry, GraphEntry):
            return

        with layout:
            hui.info_row("Graph", entry.display_name)
            render_settings(ctx, entry.run_settings, route=None)
