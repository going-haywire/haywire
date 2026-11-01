"""Library settings panel for the Models library, on the ``Barns`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.barn.builtin.surfaces import Barns
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_schema

from haybale_models.settings.models_settings import ModelsSettings

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=Barns,
    label="Models",
    description="Model download behaviour: how many files download in parallel.",
    icon=hui.icon.models,
    order=10,
    default_open=False,
)
class ModelsSettingsPanel(BasePanel):
    """Model download behaviour: how many files download in parallel."""

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        registry = ctx.app.library_service.get_settings_registry()
        render_schema(ctx, ModelsSettings, registry)
