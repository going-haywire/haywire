"""Library settings panel for the Models library, on the ``BarnsSurface`` surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.api.workbench import BarnsSurface, BasePanel, PanelLayout, hui, panel, render_schema

from haybale_models.settings.models_settings import ModelsSettings

if TYPE_CHECKING:
    from haywire.api.workbench import SessionContext


@panel(
    surface=BarnsSurface,
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
