"""Library settings panel for the Marketplace library, on the ``Barns`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.barn.builtin.surfaces import Barns
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_marketplace.settings.marketplace_settings import MarketplaceSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=Barns,
    label="Marketplace",
    description="How libraries are installed: which PyTorch build they fetch.",
    icon=hui.icon.library,
    order=10,
    default_open=False,
)
class MarketplaceSettingsPanel(BasePanel):
    """How libraries are installed: which PyTorch build they fetch."""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, MarketplaceSettings, registry)
