# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/skin.py
"""NodeSkinSettingsPanel — the default skins' geometry, on the ``CanvasSettings`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.barn.builtin.surfaces import CanvasSettings as CanvasSurface
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from ....settings.node_skin_settings import NodeSkinSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=CanvasSurface,
    label="Skin",
    description="Skin Configuration:Node dimensions, typography and label visibility.",
    icon=hui.icon.skin,
    order=20,
    default_open=False,
)
class NodeSkinSettingsPanel(BasePanel):
    """Node dimensions, typography and label visibility."""

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, NodeSkinSettings, registry)
