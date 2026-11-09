"""Library settings panel for the haystack library, on the ``Barns`` surface."""

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
    label="Haystack",
    description="Settings of the haystack library.",
    icon="speed",
    order=20,
    default_open=False,
)
class HaystackSettingsPanel(BasePanel):
    """Settings of the haystack library; today whether running graphs show flow meters."""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, FlowMeterSettings, registry)
