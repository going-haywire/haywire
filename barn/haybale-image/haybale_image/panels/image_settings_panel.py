"""Library settings panel for the Image library, on the ``Barns`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.barn.builtin.surfaces import Barns
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_image.settings.image_settings import ImageSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=Barns,
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
