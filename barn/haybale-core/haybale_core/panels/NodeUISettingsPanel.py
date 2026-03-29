from haybale_core.panels._settings_panel_base import render_schema
from haywire.ui.context import SessionContext
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel


@panel(
    editor="properties",
    scope="canvas",
    label="Nodes",
    icon="widgets",
    order=20,
    default_open=False,
)
class NodeSkinSettingsPanel(BasePanel):
    """Node dimensions, typography and label visibility."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haybale_core.settings.node_skin_settings import NodeSkinSettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(NodeSkinSettings, registry)