"""Library settings panel for the Marketplace library, on the ``BarnsSurface`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_marketplace.settings.marketplace_settings import MarketplaceSettings
from haywire.api.workbench import BarnsSurface, BasePanel, PanelLayout, hui, panel, render_schema

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=BarnsSurface,
    label="Marketplace",
    description="How libraries are installed: which PyTorch build they fetch.",
    icon=hui.icon.library,
    order=10,
    default_open=False,
)
class MarketplaceSettingsPanel(BasePanel):
    """How libraries are installed: which PyTorch build they fetch."""

    def draw(self, ctx: SessionContext, layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, MarketplaceSettings, registry)
