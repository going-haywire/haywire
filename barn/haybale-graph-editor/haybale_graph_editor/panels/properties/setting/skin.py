# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/setting/skin.py
"""NodeSkinSettingsPanel — the default skins' geometry, on the ``CanvasSettingsSurface`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.settings.node_skin_settings import NodeSkinSettings
from haywire.api.workbench import BasePanel, CanvasSettingsSurface, PanelLayout, hui, panel, render_schema

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=CanvasSettingsSurface,
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
        ctx: SessionContext,
        layout: PanelLayout,
    ) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, NodeSkinSettings, registry)
