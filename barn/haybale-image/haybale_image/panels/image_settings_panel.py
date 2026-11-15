"""Library settings panel for the Image library, on the ``BarnsSurface`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.api.workbench import BarnsSurface, BasePanel, PanelLayout, panel, render_schema

from haybale_image.settings.image_settings import ImageSettings

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=BarnsSurface,
    label="Image",
    description="Defaults for saving images.",
    icon="image",
    order=10,
    default_open=False,
)
class ImageSettingsPanel(BasePanel):
    """Defaults for saving images; each Save Image node can override them."""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, ImageSettings, registry)
