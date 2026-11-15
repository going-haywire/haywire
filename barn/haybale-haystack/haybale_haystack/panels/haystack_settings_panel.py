"""Library settings panel for the haystack library, on the ``BarnsSurface`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.api.workbench import BarnsSurface, BasePanel, PanelLayout, hui, panel, render_schema

from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=BarnsSurface,
    label="Haystack",
    description="Settings of the haystack library.",
    icon=hui.icon.haystack,
    order=20,
    default_open=False,
)
class HaystackSettingsPanel(BasePanel):
    """Settings of the haystack library; today whether running graphs show flow meters."""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, FlowMeterSettings, registry)
