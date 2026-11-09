"""Library settings panel for the flow meters, on the ``Barns`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.barn.builtin.surfaces import Barns
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_haystack.settings.flow_meter_settings import FlowMeterSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=Barns,
    label="Flow meters",
    description="Meters on the haystack rows of running graphs.",
    icon="speed",
    order=20,
    default_open=False,
)
class FlowMeterSettingsPanel(BasePanel):
    """Turns the flow meters on the haystack rows on or off."""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, FlowMeterSettings, registry)
