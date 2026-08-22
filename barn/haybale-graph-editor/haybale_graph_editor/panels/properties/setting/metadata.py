# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/metadata.py
"""
GraphMetadataPanel — renders the active graph's document metadata (graph.meta).

Sibling of GraphSettingsPanel (graph.props): both are GraphSettings bags, so
both delegate the entire editing surface to ``render_settings``. That is why
this panel carries no commit path of its own — the settings framework owns
commit-on-blur, event wiring and change propagation.

The framework-written fields (filestem, created_at, modified_at) belong to
GraphInfoPanel instead: they have no setter, and a bag renderer draws every
field as editable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.access import AccessTier
from haywire.core.signals import ActiveGraphMoved, GraphSaved
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
    label="Graph Metadata",
    icon=hui.icon.graph,
    order=15,  # between GraphInfoPanel (10) and GraphSettingsPanel (20)
    default_open=False,
    access=AccessTier.EDIT,
    # Deliberately NOT GraphDataMutated: that means "nodes/edges/props
    # changed", and metadata is not content. Subscribing to it to catch a
    # save would redraw on every node edit, risking a mid-typing rebuild
    # (.insights/feedback_nicegui_outbox_updatevalue_stomp.md).
    redraw_on=(ActiveGraphMoved, GraphSaved),
)
class GraphMetadataPanel(BasePanel):
    """Renders ``graph.meta`` for the active graph."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        graph_obj = ctx.data[EditState].active_graph
        return graph_obj is not None and getattr(graph_obj, "meta", None) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        graph_obj = ctx.data[EditState].active_graph
        if graph_obj is None:
            return
        with layout:
            render_settings(graph_obj.meta)
