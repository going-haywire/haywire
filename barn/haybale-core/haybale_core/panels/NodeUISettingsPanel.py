from haybale_core.panels._settings_panel_base import render_schema
from haywire.ui.context import SessionContext
from haywire.ui.panel.base import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel


@panel(
    registry_id="settings_node_ui",
    editor="properties",
    scope="canvas",
    label="Nodes",
    icon="widgets",
    order=20,
    default_open=False,
)
class NodeUISettingsPanel(BasePanel):
    """Node dimensions, typography and label visibility."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return True

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        from haybale_core.settings.ui_node import NodeUISettings

        registry = context.app.library_service.get_settings_registry()
        render_schema(NodeUISettings, registry)